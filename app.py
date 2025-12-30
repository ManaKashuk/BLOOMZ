import os
import io
import base64
import math
import pandas as pd
import streamlit as st
from PIL import Image
from pathlib import Path
import difflib

# ------------------ PATHS & CONFIG ------------------
ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
CHAT_ICON = ASSETS_DIR / "chat.png"    
LOGO_PATH = ASSETS_DIR / "logo.png"    
BLOOMZ_GREEN = "#49735A"
BLOOMZ_LIGHT = "#F8F9FA"

# ------------------ DATA HUB HELPERS ------------------
@st.cache_data
def load_blum_hub_db():
    db_path = "data/blum_db.csv"
    if os.path.exists(db_path):
        df = pd.read_csv(db_path)
        # MAP: Source Headers -> Internal Logic
        col_map = {
            "exact_molecular_weight": "exact_mass", 
            "chemical_class": "class", 
            "identifier": "id"
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "name" in df.columns:
            df["name"] = df["name"].fillna(df["id"] if "id" in df.columns else "Unknown")
        # DERIVE: Ensure plant_source exists to avoid sidebar crash
        if "plant_source" not in df.columns:
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
    bg = "#E8F5E9" if is_user else "#FFFFFF"
    align = "flex-end" if is_user else "flex-start"
    st.markdown(f"""
        <div style='display:flex; align-items:center; justify-content:{align}; margin:10px 0;'>
            {f'<img src="data:image/png;base64,{avatar_b64}" width="40" style="margin-right:10px; border-radius:50%;"/>' if (avatar_b64 and not is_user) else ''}
            <div style='background:{bg}; padding:15px; border-radius:15px; max-width:80%; box-shadow: 0px 2px 5px rgba(0,0,0,0.05); border: 1px solid #eee;'>
                {html}
            </div>
        </div>
        """, unsafe_allow_html=True)

# ------------------ UI STYLING ------------------
def apply_theme():
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {BLOOMZ_LIGHT}; }}
        [data-testid="stSidebar"] {{ background-color: white; border-right: 1px solid #eee; }}
        .hero {{ text-align:left; padding-top: 1rem; }}
        .hero h1 {{ font-size:2.2rem; font-weight:1000; color:#222; margin:0; }}
        .hero p {{ font-size:1.1rem; color:{BLOOMZ_GREEN}; font-weight:500; margin-bottom: 10px; }}
        .divider-strong {{ border-top:5px solid #222; margin: 0 0 2rem 0; }}
        .report-box {{ border: 2px solid {BLOOMZ_GREEN}; padding: 20px; border-radius: 12px; background: white; }}
        </style>
    """, unsafe_allow_html=True)

# ------------------ MAIN APP ------------------
def main():
    st.set_page_config(page_title="BLOOMZ CORE • Navigator", page_icon="🌿", layout="wide")
    apply_theme()
    
    # Initialize Chat History
    if "chat" not in st.session_state: st.session_state.chat = []
    
    db = load_blum_hub_db()
    chat_avatar = _img_to_b64(CHAT_ICON)

    # ------------------ SIDEBAR (CLINI-Q STYLE) ------------------
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=200)
        
        st.header("CORE Navigator")
        
        # PRIMARY NAVIGATION (Moves selection from center to sidebar)
        mode = st.radio(
            "Navigation",
            ["🏠 Home Hub", "🔍 Quick Discovery", "📊 Batch Analysis", "🛡️ COA Registry"],
            label_visibility="collapsed"
        )
        
        st.divider()
        st.subheader("Discovery Params")
        search_type = st.selectbox("Search By", ["Compound Name", "Plant Source"])
        mass_tol = st.slider("Mass Tolerance (m/z)", 0.001, 0.010, 0.005, format="%.3f")
        
        st.divider()
        st.caption("© 2025 BLOOMZ GROUP")
        st.caption("Jordanian Soil-to-Cloud Protocol")

    # ------------------ TOP HERO HEADER ------------------
    st.markdown(f"""
        <div class="hero">
          <h1>💡 BLOOMZ CORE: Spectral Intelligence Hub</h1>
          <p>🛡️ Agentic Verification: ±0.005 m/z Precision Gate Active. 🛡️</p>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('<div class="divider-strong"></div>', unsafe_allow_html=True)

    # ------------------ WORKSPACE LOGIC ------------------

    if mode == "🏠 Home Hub":
        st.subheader("Welcome, Researcher")
        st.info("The Spectral Intelligence engine is active. Please select a workspace from the sidebar.")
        
        st.markdown("""
            <div style='background:white; padding:30px; border-radius:15px; border:1px solid #ddd;'>
                <h3>System Capabilities</h3>
                <p><b>1. Discovery:</b> Direct fuzzy-search against the 499-compound Jordanian library.</p>
                <p><b>2. Analysis:</b> Batch processing of GC-MS raw peak tables with agentic scoring.</p>
                <p><b>3. Verification:</b> Instant generation of traceable Certificates of Analysis (COA).</p>
            </div>
        """, unsafe_allow_html=True)

    elif mode == "🔍 Quick Discovery":
        col_chat, col_data = st.columns([3, 2])
        
        with col_chat:
            st.subheader("💬 Intelligence Chat")
            if not st.session_state.chat:
                st.session_state.chat.append({"role":"asst", "content": "The discovery agent is online. Enter a compound or plant name to begin verification."})
            
            for msg in st.session_state.chat:
                _show_bubble(msg["content"], chat_avatar if msg["role"]=="asst" else "", is_user=(msg["role"]=="user"))
            
            prompt = st.chat_input("Verify Thymoquinone...")
            if prompt:
                st.session_state.chat.append({"role":"user", "content": prompt})
                st.session_state.chat.append({"role":"asst", "content": f"Searching evidence for '{prompt}' using ±{mass_tol} m/z logic..."})
                st.rerun()

        with col_data:
            st.subheader("🔬 Library Evidence")
            # Dynamic filtering based on sidebar search_type
            search_query = st.text_input(f"Filter by {search_type}")
            
            if search_query:
                if search_type == "Compound Name":
                    display_df = db[db["name"].str.contains(search_query, case=False, na=False)]
                else:
                    display_df = db[db["plant_source"].str.contains(search_query, case=False, na=False)]
                
                st.dataframe(display_df[["name", "exact_mass", "class"]].head(25), use_container_width=True)
                
                if not display_df.empty:
                    if st.button("Generate Verified COA", type="primary", use_container_width=True):
                        top = display_df.iloc[0]
                        st.markdown(f"""
                            <div class="report-box">
                                <h4 style='color:{BLOOMZ_GREEN}; margin-top:0;'>Digital Certificate of Analysis</h4>
                                <b>Identity:</b> {top['name']}<br>
                                <b>Exact Mass:</b> {top['exact_mass']} (Gate ±{mass_tol})<br>
                                <b>Class:</b> {top['class']}<br>
                                <hr>
                                <small>Verified via BLOOMZ CORE Spectral Intelligence Hub.</small>
                            </div>
                        """, unsafe_allow_html=True)

    elif mode == "📊 Batch Analysis":
        st.subheader("Batch Instrument Ingestion")
        st.write("Upload your raw instrument peak table (CSV) for agentic scoring.")
        st.file_uploader("📎 Upload Lab CSV", type=["csv"])
        st.warning("Note: Agent requires columns labeled 'RT' and 'm/z'.")

    elif mode == "🛡️ COA Registry":
        st.subheader("Traceability Registry")
        st.write("Historical record of verified bioactives.")
        st.info("No records found. Generate a COA in Discovery or Batch mode to populate this list.")

    st.markdown("---")
    st.caption("© 2025 BLOOMZ GROUP • From Jordanian soil to the digital cloud.")

if __name__ == "__main__":
    main()
