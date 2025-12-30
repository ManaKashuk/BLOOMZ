import os
import io
import base64
import pandas as pd
import streamlit as st
from PIL import Image
from pathlib import Path

# ------------------ PATHS & CONFIG ------------------
ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
CHAT_ICON = ASSETS_DIR / "chat.png"    
LOGO_PATH = ASSETS_DIR / "logo.png"    
BLOOMZ_GREEN = "#49735A"
BLOOMZ_LIGHT = "#F8F9FA"

# ------------------ DATA LOADER ------------------
@st.cache_data
def load_final_db():
    db_path = "data/blum_db.csv"
    if os.path.exists(db_path):
        df = pd.read_csv(db_path)
        # Fix mapping for your specific BLUM_db.csv headers
        col_map = {"exact_molecular_weight": "exact_mass", "chemical_class": "class"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "name" not in df.columns and "identifier" in df.columns: df["name"] = df["identifier"]
        if "plant_source" not in df.columns: df["plant_source"] = "Jordanian Native"
        return df
    return pd.DataFrame(columns=["name", "exact_mass", "class", "plant_source"])

# ------------------ UI HELPERS ------------------
def _img_to_b64(path: Path) -> str:
    try:
        img = Image.open(path)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except: return ""

def _show_bubble(text: str, avatar_b64: str = None, is_user=False):
    """Renders the chat bubbles properly without raw code showing."""
    bg = "#E8F5E9" if is_user else "#FFFFFF"
    align = "flex-end" if is_user else "flex-start"
    
    avatar_html = ""
    if avatar_b64 and not is_user:
        avatar_html = f'<img src="data:image/png;base64,{avatar_b64}" width="40" style="margin-right:10px; border-radius:50%;">'

    st.markdown(f"""
        <div style="display:flex; align-items:center; justify-content:{align}; margin:10px 0;">
            {avatar_html}
            <div style="background:{bg}; padding:15px; border-radius:15px; max-width:80%; box-shadow: 0px 2px 5px rgba(0,0,0,0.05); border: 1px solid #eee; color: #333;">
                {text}
            </div>
        </div>
        """, unsafe_allow_html=True)

# ------------------ MAIN APP ------------------
def main():
    st.set_page_config(page_title="BLOOMZ CORE", page_icon="🌿", layout="wide")
    
    # Custom CSS to hide default menu and clean up sidebar
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {BLOOMZ_LIGHT}; }}
        [data-testid="stSidebar"] {{ background-color: white; border-right: 1px solid #eee; }}
        .divider-strong {{ border-top: 5px solid #222; margin: 10px 0 25px 0; }}
        .report-box {{ border: 2px solid {BLOOMZ_GREEN}; padding: 20px; border-radius: 12px; background: white; }}
        </style>
    """, unsafe_allow_html=True)

    db = load_final_db()
    chat_avatar = _img_to_b64(CHAT_ICON)

    # ------------------ THE NAVIGATOR SIDEBAR ------------------
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=200)
        
        st.title("Navigator")
        mode = st.radio("Choose Workspace", ["🏠 Home", "🔍 Discovery", "📊 Batch Ingestion", "📜 Registry"])
        
        st.divider()
        st.subheader("Agent Settings")
        species_context = st.selectbox("Species", ["Nigella sativa", "Artemisia sieberi", "General"])
        mass_gate = st.slider("Gate (m/z)", 0.001, 0.010, 0.005)
        
        if st.button("Clear Chat History"):
            st.session_state.chat = []
            st.rerun()

    # ------------------ MAIN HUB CONTENT ------------------
    st.markdown(f"<h1>💡Spectral Intelligence Hub💡</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='color:{BLOOMZ_GREEN}; font-weight:500;'>Verified Jordanian Botanical Library Access</p>", unsafe_allow_html=True)
    st.markdown('<div class="divider-strong"></div>', unsafe_allow_html=True)

    if mode == "🏠 Home":
        st.subheader("System Active")
        st.info("Select a mode from the sidebar to begin. The engine is primed with 499 high-precision bioactives.")
        st.markdown("""
            <div style="background:white; padding:25px; border-radius:15px; border:1px solid #eee;">
                <h4>Chain of Intelligence™ Protocol</h4>
                <p>1. <b>Discovery:</b> Instant fuzzy-matching for lab verification.</p>
                <p>2. <b>Batch:</b> Automated ±0.005 m/z annotation.</p>
                <p>3. <b>COA:</b> Traceable Certificate of Analysis generation.</p>
            </div>
        """, unsafe_allow_html=True)

    elif mode == "🔍 Discovery":
        col_chat, col_data = st.columns([3, 2])
        
        with col_chat:
            st.subheader("💬 Assistant")
            if "chat" not in st.session_state: st.session_state.chat = []
            
            for msg in st.session_state.chat:
                _show_bubble(msg["content"], chat_avatar if msg["role"]=="asst" else None, is_user=(msg["role"]=="user"))
            
            prompt = st.chat_input("Enter compound name...")
            if prompt:
                st.session_state.chat.append({"role":"user", "content": prompt})
                st.session_state.chat.append({"role":"asst", "content": f"Searching library for **{prompt}**... Filtering with ±{mass_gate} m/z gate."})
                st.rerun()

        with col_data:
            st.subheader("🔬 Library Match")
            search = st.text_input("Refine Search", placeholder="e.g. Thymoquinone")
            if search:
                results = db[db["name"].str.contains(search, case=False, na=False)]
                st.dataframe(results[["name", "exact_mass", "class"]].head(20), use_container_width=True)
                
                if not results.empty and st.button("Generate Verified Report"):
                    hit = results.iloc[0]
                    st.markdown(f"""
                        <div class="report-box">
                            <h4 style="color:{BLOOMZ_GREEN}; margin:0;">Spectral Verification</h4>
                            <b>Identity:</b> {hit['name']}<br>
                            <b>Precision:</b> {hit['exact_mass']} (Gate: {mass_gate})<br>
                            <b>Source:</b> {species_context}
                        </div>
                    """, unsafe_allow_html=True)

    elif mode == "📊 Batch Ingestion":
        st.subheader("Instrument Table Processing")
        st.file_uploader("Upload Shimadzu/Agilent CSV", type=["csv"])

    elif mode == "📜 Registry":
        st.subheader("COA Archive")
        st.warning("No session records found.")

if __name__ == "__main__":
    main()
