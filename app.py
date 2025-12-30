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
        col_map = {"exact_molecular_weight": "exact_mass", "chemical_class": "class", "identifier": "id"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "name" in df.columns:
            df["name"] = df["name"].fillna(df["id"] if "id" in df.columns else "Unknown")
        if "plant_source" not in df.columns:
            df["plant_source"] = df["chemical_sub_class"].fillna("Jordanian Native")
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
            <div style='background:{bg}; padding:15px; border-radius:15px; max-width:85%; box-shadow: 0px 2px 4px rgba(0,0,0,0.05); border: 1px solid #eee;'>
                {html}
            </div>
        </div>
        """, unsafe_allow_html=True)

# ------------------ UI STYLING ------------------
def apply_custom_css():
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {BLOOMZ_LIGHT}; }}
        [data-testid="stSidebar"] {{ background-color: white; border-right: 1px solid #eee; }}
        .hero {{ text-align:left; margin-bottom: 2rem; }}
        .hero h1 {{ font-size:2.2rem; font-weight:800; color:#222; margin:0; }}
        .hero p {{ font-size:1.1rem; color:{BLOOMZ_GREEN}; font-weight:500; }}
        .divider-strong {{ border-top:4px solid #222; margin: 0.5rem 0 1.5rem 0; }}
        .stButton>button {{ border-radius: 8px; font-weight: bold; border: 1px solid {BLOOMZ_GREEN}; }}
        .card-inner {{ border:1px solid #e5e7eb; border-radius:12px; padding:1.5rem; background:#fff; }}
        </style>
    """, unsafe_allow_html=True)

# ------------------ MAIN APP ------------------
def main():
    st.set_page_config(page_title="BLOOMZ Navigator", page_icon="🌿", layout="wide")
    apply_custom_css()
    
    # Session State
    if "chat" not in st.session_state: st.session_state.chat = []
    
    db = load_blum_hub_db()

    # ------------------ SIDEBAR (NAVIGATOR STYLE) ------------------
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=180)
        st.header("SOP Navigator")
        
        # Clickable Workspace Selection
        workspace = st.radio(
            "📂 Select Workspace",
            ["🏠 Home", "🔍 Quick Discovery", "📊 Batch Analysis", "🛡️ COA Registry"],
            index=0
        )
        
        st.divider()
        st.subheader("Agent Settings")
        species = st.selectbox("Context Species", ["Nigella sativa", "Artemisia sieberi", "Boswellia sacra"])
        mass_tol = st.slider("Precision Gate (m/z)", 0.001, 0.010, 0.005, format="%.3f")
        
        st.divider()
        st.caption("BLOOMZ CORE v3.1")
        st.caption("Jordanian Soil-to-Cloud Protocol")

    # ------------------ MAIN CONTENT AREA ------------------
    # Header (Always visible)
    st.markdown("""
        <div class="hero">
          <h1>💡 BLOOMZ CORE: Spectral Intelligence Hub</h1>
          <p>Agentic platform for plant-to-compound discovery & verification.</p>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('<div class="divider-strong"></div>', unsafe_allow_html=True)

    # WORKSPACE LOGIC
    if "🏠 Home" in workspace:
        st.markdown("### Welcome to the Intelligence Hub")
        st.info("Use the sidebar to navigate between Discovery search and Batch instrument processing.")
        st.markdown("""
            <div class='card-inner'>
                <h4>System Status: Online</h4>
                <li><b>Library:</b> 499 Verified Jordanian Bioactives</li>
                <li><b>Protocol:</b> ±0.005 m/z Accuracy Gate Active</li>
                <li><b>Target:</b> TSU Research / NOW Foods QA Integration</li>
            </div>
        """, unsafe_allow_html=True)

    elif "🔍 Quick Discovery" in workspace:
        st.subheader("Direct Compound Discovery")
        col_chat, col_data = st.columns([3, 2])
        
        with col_chat:
            st.markdown("#### 💬 Assistant")
            if not st.session_state.chat:
                st.session_state.chat.append({"role":"asst", "content": f"Ready to discover bioactives for **{species}**. Enter a compound name to verify its mass profile."})
            
            for msg in st.session_state.chat:
                _show_bubble(msg["content"], "", is_user=(msg["role"]=="user"))
            
            prompt = st.chat_input("Search Thymoquinone, Terpenes...")
            if prompt:
                st.session_state.chat.append({"role":"user", "content": prompt})
                st.session_state.chat.append({"role":"asst", "content": f"Querying BLUM database for '{prompt}' within species context..."})
                st.rerun()

        with col_data:
            st.markdown("#### 🔬 Evidence")
            query = st.text_input("Database Filter", placeholder="Type to filter results...")
            if query:
                display_df = db[db["name"].str.contains(query, case=False, na=False)]
                st.dataframe(display_df[["name", "exact_mass", "class"]], use_container_width=True)
                if st.button("Generate Verified Report", type="primary"):
                    st.success("Digital COA Ready for Export.")

    elif "📊 Batch Analysis" in workspace:
        st.subheader("Batch Instrument Ingestion")
        st.write("Upload raw instrument peak tables for agentic scoring.")
        uploaded_file = st.file_uploader("📎 Upload Shimadzu/Agilent CSV", type=["csv"])
        if uploaded_file:
            st.success("File Ingested. Ready for Agentic Analysis.")
            st.button("Run Spectral Scoring (±0.005 m/z Gate)")

    elif "🛡️ COA Registry" in workspace:
        st.subheader("Traceability Registry")
        st.write("Historic data-backed certificates generated in this session.")
        st.warning("No historic records found in the current cloud instance.")

    st.markdown("---")
    st.caption("© 2025 BLOOMZ GROUP • Bioactive Library for Mass Spectrometry • Public Repo Safe Prototype")

if __name__ == "__main__":
    main()
