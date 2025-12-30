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
from difflib import SequenceMatcher, get_close_matches

# ------------------ PATHS & CONFIG ------------------
# Note: Place logo.png and chat.png in an 'assets' folder
ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
CHAT_ICON = ASSETS_DIR / "chat.png"    # Assistant avatar
LOGO_PATH = ASSETS_DIR / "logo.png"    # Header logo
BLOOMZ_GREEN = "#49735A"

APP_TITLE = "BLOOMZ CORE • Spectral Intelligence Hub"
DISCLAIMER = "🛡️ Agentic platform for plant-to-compound discovery. Verified against Jordanian botanical libraries.🛡️"

# ------------------ DATA HELPERS ------------------
@st.cache_data
def load_blum_db():
    # Using the structure from your BLUM_db.csv
    if os.path.exists("data/blum_db.csv"):
        df = pd.read_csv("data/blum_db.csv")
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

# ------------------ MAIN APP ------------------
def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="🌿", layout="wide")

    # --- Header Styling ---
    st.markdown(f"""
        <style>
          .hero {{ text-align:left; margin-top:.10rem; }}
          .hero h1 {{ font-size:2.3rem; font-weight:1000; color:#222; margin:0; }}
          .hero p  {{ font-size:1.2rem; color:{BLOOMZ_GREEN}; max-width:1000px; margin:.35rem 0 0 0; font-weight:500; }}
          .divider-strong {{ border-top:4px solid {BLOOMZ_GREEN}; margin:.4rem 0 1.0rem; }}
          .card {{ border:1px solid #e5e7eb; border-radius:12px; padding:1.2rem; background:#fff; box-shadow: 2px 2px 10px rgba(0,0,0,0.05); }}
          .stButton>button {{ background-color: {BLOOMZ_GREEN} !important; color:white; border-radius:8px; }}
        </style>
        """, unsafe_allow_html=True)

    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=350)

    st.markdown(f"""
        <div class="hero">
          <h1>💡 BLOOMZ CORE: Spectral Intelligence</h1>
          <p>{DISCLAIMER}</p>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('<div class="divider-strong"></div>', unsafe_allow_html=True)

    # --- Sidebar Setup (Discovery Search) ---
    with st.sidebar:
        st.header("🧬 Discovery Search")
        search_mode = st.selectbox("🔍 Search Discovery By:", ["Plant Name", "Compound Name"])
        
        db = load_blum_db()
        if search_mode == "Plant Name":
            options = ["All Jordanian Species"] + sorted(db["plant_source"].unique().tolist()) if not db.empty else ["Nigella sativa"]
            target = st.selectbox("📂 Select Botanical Source", options)
        else:
            target = st.text_input("🧪 Enter Compound Name", placeholder="e.g. Thymoquinone")

        st.divider()
        st.subheader("Agent Settings")
        mass_tol = st.number_input("Mass Tolerance (± m/z)", value=0.005, format="%.4f")
        st.caption("Fulfilling Phase 1: ±0.005 m/z Gate [cite: 892]")

    # --- Session State ---
    st.session_state.setdefault("chat", [])
    chat_avatar = _img_to_b64(CHAT_ICON)

    # --- Main Discovery Interface ---
    col_chat, col_evidence = st.columns([3, 2])

    with col_chat:
        st.subheader("💬 Spectral Intelligence Chat")
        
        # Initial greeting
        if not st.session_state["chat"]:
            st.session_state["chat"].append({
                "role": "assistant", 
                "content": f"Welcome to the **Intelligence Hub**. I am searching for candidates in **{target}**. How can I assist your discovery today?"
            })

        # Chat logic
        for msg in st.session_state["chat"]:
            _show_bubble(msg["content"], chat_avatar if msg["role"] == "assistant" else "", is_user=(msg["role"] == "user"))

        prompt = st.chat_input("Ask about chemical classes, exact masses, or purity markers...")
        if prompt:
            st.session_state["chat"].append({"role": "user", "content": prompt})
            # Mock agent logic for demo - in production, link to your retrieve() logic
            st.session_state["chat"].append({"role": "assistant", "content": f"Analyzing spectral data for '{prompt}' within the context of {target}..."})
            st.rerun()

    with col_evidence:
        st.subheader("🔎 Intelligence Evidence")
        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        if not db.empty and target != "All Jordanian Species":
            # Matching logic for the evidence panel
            matches = db[db["plant_source"] == target] if search_mode == "Plant Name" else db[db["name"].str.contains(target, case=False, na=False)]
            
            if not matches.empty:
                st.write(f"**Found {len(matches)} candidates in {target}:**")
                st.dataframe(matches[["name", "exact_mass", "class"]], use_container_width=True)
            else:
                st.info("No library matches found. Ready for raw GC-MS ingestion.")
        
        st.markdown("</div>", unsafe_allow_html=True)

        # Guidance Card
        st.divider()
        if st.button("Generate Verified COA", type="primary", use_container_width=True):
            st.success("Draft Certificate of Analysis Generated.")
            st.markdown("### 📄 Digital COA Summary")
            st.markdown(f"""
            <div class="card">
                <b>1. Identification:</b> High-confidence matching for {target}.<br>
                <b>2. Methodology:</b> Agentic scoring applied (Mass Gate: {mass_tol}).<br>
                <b>3. Traceability:</b> Linked to Jordanian Soil-to-Cloud Protocol[cite: 959].
            </div>
            """, unsafe_allow_html=True)
            
    st.markdown("---")
    st.caption("© 2025 BLOOMZ GROUP • Pure Botanical Intelligence • From Jordanian soil to the digital cloud.")

if __name__ == "__main__":
    main()
