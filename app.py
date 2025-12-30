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
            <div style='background:{bg}; padding:15px; border-radius:20px; max-width:80%; box-shadow: 0px 2px 5px rgba(0,0,0,0.05); border: 1px solid #eee;'>
                {html}
            </div>
        </div>
        """, unsafe_allow_html=True)

# ------------------ UI COMPONENTS ------------------
def render_header():
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=220)
    st.markdown(f"<h1 style='font-size:2.5rem; margin-bottom:0;'>Spectral Intelligence Hub</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:{BLOOMZ_GREEN}; font-size:1.1rem; font-weight:500;'>Plant-to-Compound Intelligence Chain™</p>", unsafe_allow_html=True)
    st.markdown("---")

# ------------------ WORKSPACES ------------------
def render_landing():
    st.markdown("### Select a Workspace")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown(f"""
            <div style='border:1px solid #ddd; padding:30px; border-radius:15px; background:white; text-align:center;'>
                <h2 style='color:{BLOOMZ_GREEN};'>🔍</h2>
                <h3>Quick Discovery</h3>
                <p>Search compounds or species directly without files.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Enter Discovery Mode", key="btn_disc"):
            st.session_state.page = "discovery"
            st.rerun()

    with c2:
        st.markdown(f"""
            <div style='border:1px solid #ddd; padding:30px; border-radius:15px; background:white; text-align:center;'>
                <h2 style='color:{BLOOMZ_GREEN};'>📊</h2>
                <h3>Batch Analysis</h3>
                <p>Upload raw GC-MS instrument tables for agentic scoring.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("Enter Batch Mode", key="btn_batch"):
            st.session_state.page = "batch"
            st.rerun()

    with c3:
        st.markdown(f"""
            <div style='border:1px solid #ddd; padding:30px; border-radius:15px; background:white; text-align:center;'>
                <h2 style='color:{BLOOMZ_GREEN};'>🛡️</h2>
                <h3>Verified COA</h3>
                <p>View previously generated certificates and data fingerprints.</p>
            </div>
        """, unsafe_allow_html=True)
        if st.button("View COA History", key="btn_coa"):
            st.session_state.page = "coa"
            st.rerun()

def render_discovery_mode(db):
    st.button("⬅ Back to Home", on_click=lambda: st.session_state.update({"page": "home"}))
    
    col_chat, col_data = st.columns([3, 2])
    
    with col_chat:
        st.subheader("💬 Intelligence Chat")
        # Chat Logic (similar to previous version)
        st.info("I am ready to discover bioactives. Enter a compound or plant name below.")
        prompt = st.chat_input("Ask about Thymoquinone mass, terpene classes...")
        if prompt:
            st.session_state["chat"].append({"role": "user", "content": prompt})
            st.session_state["chat"].append({"role": "assistant", "content": f"Analyzing library for '{prompt}' using ±0.005 m/z logic..."})

        for msg in st.session_state.get("chat", []):
            _show_bubble(msg["content"], "", is_user=(msg["role"]=="user"))

    with col_data:
        st.subheader("🔬 Data Evidence")
        target = st.text_input("Refine Search (Name/Plant)", key="disc_search")
        if target:
            display_df = db[db["name"].str.contains(target, case=False, na=False) | db["plant_source"].str.contains(target, case=False, na=False)]
            st.dataframe(display_df[["name", "exact_mass", "class"]].head(20), use_container_width=True)
            if not display_df.empty:
                if st.button("Generate COA for Best Match"):
                    st.success(f"Report for {display_df.iloc[0]['name']} ready.")

# ------------------ MAIN APP ------------------
def main():
    st.set_page_config(page_title="BLOOMZ CORE", page_icon="🌿", layout="wide")
    
    # Custom CSS for the clean look
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {BLOOMZ_LIGHT}; }}
        .stButton>button {{ width: 100%; border-radius: 8px; font-weight: bold; border: 1px solid {BLOOMZ_GREEN}; }}
        </style>
    """, unsafe_allow_html=True)

    if "page" not in st.session_state:
        st.session_state.page = "home"
    if "chat" not in st.session_state:
        st.session_state.chat = []

    db = load_blum_hub_db()

    # Sidebar for Admin/Settings ONLY
    with st.sidebar:
        st.title("Settings")
        st.file_uploader("Update Database", type=["csv"])
        st.slider("Agent precision", 0.001, 0.010, 0.005)
        st.caption("BLOOMZ CORE v3.0")

    render_header()

    if st.session_state.page == "home":
        render_landing()
    elif st.session_state.page == "discovery":
        render_discovery_mode(db)
    elif st.session_state.page == "batch":
        st.button("⬅ Back to Home", on_click=lambda: st.session_state.update({"page": "home"}))
        st.subheader("Batch Instrument Ingestion")
        st.file_uploader("Upload Lab CSV", type=["csv"])
    elif st.session_state.page == "coa":
        st.button("⬅ Back to Home", on_click=lambda: st.session_state.update({"page": "home"}))
        st.subheader("Traceability History")
        st.info("No saved reports found in this session.")

if __name__ == "__main__":
    main()
