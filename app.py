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
        col_map = {"exact_molecular_weight": "exact_mass", "chemical_class": "class"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "name" not in df.columns and "identifier" in df.columns: df["name"] = df["identifier"]
        if "plant_source" not in df.columns: df["plant_source"] = "Jordanian Native"
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
        [data-testid="stSidebar"] {{ background-color: white; border-right: 1px solid #eee; padding-top: 0; }}
        .hero {{ text-align:left; margin-bottom: 0.5rem; }}
        .hero h1 {{ font-size:2.1rem; font-weight:1000; color:#222; margin:0; }}
        .hero p {{ font-size:1.1rem; color:{BLOOMZ_GREEN}; font-weight:500; margin-top: 5px; }}
        .divider-strong {{ border-top:5px solid #222; margin: 0.5rem 0 1.5rem 0; }}
        .stButton>button {{ border-radius: 8px; font-weight: bold; border: 1px solid {BLOOMZ_GREEN}; background: white; }}
        .report-box {{ border: 2px solid {BLOOMZ_GREEN}; padding: 20px; border-radius: 12px; background: #fff; }}
        </style>
    """, unsafe_allow_html=True)

# ------------------ MAIN APP ------------------
def main():
    st.set_page_config(page_title="BLOOMZ CORE Navigator", page_icon="🌿", layout="wide")
    apply_custom_css()
    
    if "chat" not in st.session_state: st.session_state.chat = []
    db = load_blum_hub_db()

    # ------------------ SIDEBAR (NAVIGATOR STYLE) ------------------
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=200)
        
        st.header("CORE Navigator")
        
        # NAVIGATION: The three options you wanted moved to the sidebar
        workspace = st.radio(
            "📍 Workspace Navigation",
            ["🏠 Home Hub", "🔍 Quick Discovery", "📊 Batch Ingestion", "📜 Traceability Registry"],
            label_visibility="collapsed"
        )
        
        st.divider()
        st.subheader("Discovery Setup")
        species = st.selectbox("Botanical Context", ["Nigella sativa", "Artemisia sieberi", "Boswellia sacra"])
        mass_tol = st.slider("Verification Gate (m/z)", 0.001, 0.010, 0.005, format="%.3f")
        
        st.divider()
        st.caption("BLOOMZ CORE v3.2")
        st.caption("Plant-to-Compound Intelligence Chain™")

    # ------------------ STICKY HEADER ------------------
    st.markdown(f"""
        <div class="hero">
          <h1>💡 BLOOMZ CORE: Spectral Intelligence Hub</h1>
          <p>🛡️ Trained on Jordanian botanical libraries and ±0.005 m/z precision gates.</p>
        </div>
        """, unsafe_allow_html=True)
    st.markdown('<div class="divider-strong"></div>', unsafe_allow_html=True)

    # ------------------ WORKSPACE LOGIC ------------------
    
    if "🏠 Home Hub" in workspace:
        st.subheader("System Overview")
        st.info("The intelligence engine is active. Select a mode from the sidebar to begin discovery.")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("""
                <div style='background:white; padding:20px; border-radius:12px; border:1px solid #ddd;'>
                    <h4>Active Library</h4>
                    <li><b>Compounds:</b> 499 Verified Bioactives</li>
                    <li><b>Origins:</b> Jordan (Native Species)</li>
                    <li><b>Class:</b> Natural Product Chemoinformatics</li>
                </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
                <div style='background:white; padding:20px; border-radius:12px; border:1px solid #ddd;'>
                    <h4>Intelligence Profile</h4>
                    <li><b>Target Species:</b> {species}</li>
                    <li><b>Gate Protocol:</b> ±{mass_tol} m/z</li>
                    <li><b>Status:</b> Ready for Spectral Matching</li>
                </div>
            """, unsafe_allow_html=True)

    elif "🔍 Quick Discovery" in workspace:
        col_chat, col_data = st.columns([3, 2])
        
        with col_chat:
            st.subheader("💬 Assistant")
            if not st.session_state.chat:
                st.session_state.chat.append({"role":"asst", "content": f"The hub is set to **{species}**. You can ask me to verify a mass or search for a compound name."})
            
            for msg in st.session_state.chat:
                _show_bubble(msg["content"], "", is_user=(msg["role"]=="user"))
            
            prompt = st.chat_input("Ask about Thymoquinone, p-Cymene, exact masses...")
            if prompt:
                st.session_state.chat.append({"role":"user", "content": prompt})
                st.session_state.chat.append({"role":"asst", "content": f"Searching for evidence of '{prompt}' in the {species} library..."})
                st.rerun()

        with col_data:
            st.subheader("🔬 Library Evidence")
            target = st.text_input("Filter Compounds (Live)", placeholder="Enter name...")
            if target:
                display_df = db[db["name"].str.contains(target, case=False, na=False)]
                st.dataframe(display_df[["name", "exact_mass", "class"]], use_container_width=True)
                
                if not display_df.empty and st.button("Generate Verified COA", type="primary", use_container_width=True):
                    top = display_df.iloc[0]
                    st.markdown(f"""
                        <div class="report-box">
                            <h4 style='color:{BLOOMZ_GREEN}; margin-top:0;'>Digital Certificate of Analysis</h4>
                            <b>Identity:</b> {top['name']}<br>
                            <b>Mass:</b> {top['exact_mass']} (Gate ±{mass_tol})<br>
                            <b>Class:</b> {top['class']}<br>
                            <hr>
                            <small>Source: {species} (Jordanian Native)</small>
                        </div>
                    """, unsafe_allow_html=True)

    elif "📊 Batch Ingestion" in workspace:
        st.subheader("Instrument Table Upload")
        st.write("Process raw GC-MS peak tables using the agentic precision gate.")
        uploaded_file = st.file_uploader("📎 Upload Shimadzu CSV", type=["csv"])
        if uploaded_file:
            st.success(f"Instrument data '{uploaded_file.name}' ingested. Ready for scoring.")
            st.button("Run Global Verification Hub")

    elif "📜 Traceability Registry" in workspace:
        st.subheader("Data Fingerprint History")
        st.warning("No records found in current session. Authenticated reports will appear here.")

    st.markdown("---")
    st.caption("© 2025 BLOOMZ GROUP • From Jordanian soil to the digital cloud. • Prototype Safety: Active.")

if __name__ == "__main__":
    main()
