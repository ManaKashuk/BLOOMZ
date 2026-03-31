# =========================
# file: app.py
# =========================
"""
BLOOMZ Analyzer (Pitch-Day Demo)
- Single shared password gate via Streamlit Secrets (no SQLite, no registration).
- Set Streamlit Secrets:
  DEMO_PASSWORD="123"
  DEMO_LABEL="TSU Demo Access"
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

# ------------------ PATHS & CONFIG ------------------
ROOT_DIR = Path(__file__).parent
ASSETS_DIR = ROOT_DIR / "assets"
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

CHAT_ICON = ASSETS_DIR / "chat.png"
LOGO_PATH = ASSETS_DIR / "logo.png"

BLOOMZ_GREEN = "#49735A"
BLOOMZ_LIGHT = "#F8F9FA"

APP_NAME = "BLOOMZ Analyzer"
APP_TAGLINE = "Mass Spectrometry Tools Built for Under-Resourced Labs"
APP_MISSION = "Because at HBCUs, talent already exists — the right tools help it bloom."

# ------------------ DATA LOADER ------------------
@st.cache_data
def load_final_db() -> pd.DataFrame:
    db_path = DATA_DIR / "blum_db.csv"
    if db_path.exists():
        df = pd.read_csv(db_path)
        col_map = {"exact_molecular_weight": "exact_mass", "chemical_class": "class"}
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        if "name" not in df.columns and "identifier" in df.columns:
            df["name"] = df["identifier"]
        if "plant_source" not in df.columns:
            df["plant_source"] = "Native Library"
        return df
    return pd.DataFrame(columns=["name", "exact_mass", "class", "plant_source"])


# ------------------ UI HELPERS ------------------
def _img_to_b64(path: Path) -> str:
    try:
        img = Image.open(path)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return ""


def _show_bubble(text: str, avatar_b64: str | None = None, is_user: bool = False) -> None:
    bg = BLOOMZ_GREEN if is_user else "#FFFFFF"
    color = "white" if is_user else "#333"
    align = "flex-end" if is_user else "flex-start"

    avatar_html = ""
    if avatar_b64 and not is_user:
        avatar_html = (
            f'<img src="data:image/png;base64,{avatar_b64}" width="40" '
            'style="margin-right:10px; border-radius:50%;">'
        )

    st.markdown(
        f"""
        <div style="display:flex; align-items:center; justify-content:{align}; margin:10px 0;">
            {avatar_html}
            <div style="background:{bg}; padding:15px; border-radius:15px; max-width:80%;
                        box-shadow: 0px 2px 5px rgba(0,0,0,0.05); border: 1px solid #eee; color: {color};">
                {text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ------------------ DEMO AUTH (single password) ------------------
def _get_demo_password() -> str:
    return str(st.secrets.get("DEMO_PASSWORD", "")).strip()


def _get_demo_label() -> str:
    label = str(st.secrets.get("DEMO_LABEL", "")).strip()
    return label or "Demo Access"


def login_screen_demo() -> None:
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=220)

    st.markdown(f"<h1>{APP_NAME}</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='color:{BLOOMZ_GREEN}; font-weight:600; font-size:1.1rem;'>{APP_TAGLINE}</p>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<p>{APP_MISSION}</p>", unsafe_allow_html=True)

    demo_label = _get_demo_label()
    st.subheader(demo_label)

    if not _get_demo_password():
        st.error("DEMO_PASSWORD is not set in Streamlit Secrets.")
        st.stop()

    with st.form("demo_login"):
        pwd = st.text_input("Password", type="password", placeholder="Enter demo password")
        submit = st.form_submit_button("Enter", use_container_width=True)

    if submit:
        if pwd == _get_demo_password():
            st.session_state.authenticated = True
            st.session_state.user_name = demo_label
            st.session_state.user_role = "demo"
            st.success("Access granted.")
            st.rerun()
        else:
            st.error("Invalid password.")


def logout() -> None:
    for key in ["authenticated", "user_name", "user_role", "chat"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


# ------------------ MAIN APP ------------------
def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="🌿", layout="wide")

    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {BLOOMZ_LIGHT}; }}
        [data-testid="stSidebar"] {{ background-color: white; border-right: 1px solid #eee; }}
        .divider-strong {{ border-top: 5px solid #222; margin: 10px 0 25px 0; }}
        .report-box {{ border: 2px solid {BLOOMZ_GREEN}; padding: 20px; border-radius: 12px; background: white; }}
        .stChatInputContainer {{ border-radius: 10px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        login_screen_demo()
        st.stop()

    db = load_final_db()
    chat_avatar = _img_to_b64(CHAT_ICON)

    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=200)

        st.title(APP_NAME)
        st.caption(APP_TAGLINE)
        st.success(f"Logged in as {st.session_state.get('user_name', 'Demo')}")
        st.caption(f"Role: {st.session_state.get('user_role', 'demo')}")

        mode_options = ["🏠 Home", "🔍 Discovery", "📊 Batch Upload", "📜 Registry"]
        mode = st.radio("Choose Workspace", mode_options)

        st.divider()
        st.subheader("Analysis Settings")
        species_context = st.selectbox("Species", ["Nigella sativa", "Artemisia sieberi", "General"])
        mass_gate = st.slider("Mass Tolerance (m/z)", 0.001, 0.010, 0.005, format="%.3f")

        st.divider()
        if st.button("Clear Chat History", use_container_width=True):
            st.session_state.chat = []
            st.rerun()
        if st.button("Logout", use_container_width=True):
            logout()

    st.markdown(f"<h1>{APP_NAME}</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='color:{BLOOMZ_GREEN}; font-weight:600; font-size:1.2rem;'>Turn Mass Spectrometry Data Into Discovery.</p>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<p style='font-size:1rem;'>{APP_MISSION}</p>", unsafe_allow_html=True)
    st.markdown('<div class="divider-strong"></div>', unsafe_allow_html=True)

    if mode == "🏠 Home":
        st.subheader("System Status: Ready")
        st.info("BLOOMZ is ready. Choose a workspace from the sidebar to begin analysis.")

        st.markdown(
            f"""
            <div style="background:white; padding:25px; border-radius:15px; border:1px solid #eee;">
                <h4 style="color:{BLOOMZ_GREEN};">What BLOOMZ Does</h4>
                <p><b>BLOOMZ Analyzer</b> helps research labs turn mass spectrometry data into ranked compound candidates and clean, usable reports faster.</p>
                <p>Built from lived HBCU research experience, it is designed to help under-resourced labs move from data to answers with more speed, confidence, and independence.</p>
                <hr>
                <li><b>Library:</b> Demo Reference Compounds</li>
                <li><b>Mass Tolerance:</b> ±{mass_gate} m/z</li>
                <li><b>Context:</b> {species_context}</li>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif mode == "🔍 Discovery":
        col_chat, col_data = st.columns([3, 2])

        with col_chat:
            st.subheader("💬 BLOOMZ Assistant (Demo)")
            if "chat" not in st.session_state:
                st.session_state.chat = []

            for msg in st.session_state.chat:
                _show_bubble(
                    msg["content"],
                    chat_avatar if msg["role"] == "asst" else None,
                    is_user=(msg["role"] == "user"),
                )

            prompt = st.chat_input("Enter a compound name or class...")
            if prompt:
                st.session_state.chat.append({"role": "user", "content": prompt})
                st.session_state.chat.append(
                    {
                        "role": "asst",
                        "content": (
                            f"Reviewing **{prompt}** against the demo reference library. "
                            f"Current mass tolerance is ±{mass_gate} m/z. "
                            "I’ll help you narrow likely candidates and move toward a usable result."
                        ),
                    }
                )
                st.rerun()

        with col_data:
            st.subheader("🔬 Ranked Matches")
            search = st.text_input("Search the Library", placeholder="Enter a compound name or class...")
            if search:
                results = db[db["name"].astype(str).str.contains(search, case=False, na=False)]
                st.dataframe(results[["name", "exact_mass", "class"]].head(25), use_container_width=True)

                if not results.empty and st.button("Generate Analysis Summary", use_container_width=True):
                    hit = results.iloc[0]
                    st.markdown(
                        f"""
                        <div class="report-box">
                            <h4 style="color:{BLOOMZ_GREEN}; margin:0;">BLOOMZ Analysis Summary</h4>
                            <b>Candidate:</b> {hit['name']}<br>
                            <b>Exact Mass:</b> {hit['exact_mass']}<br>
                            <b>Mass Tolerance:</b> ±{mass_gate} m/z<br>
                            <b>Context:</b> {species_context}<br>
                            <b>Status:</b> Ranked for follow-up review
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

    elif mode == "📊 Batch Upload":
        st.subheader("Batch Upload")
        st.write("Upload peak tables for batch analysis and faster compound candidate review.")
        st.file_uploader("📎 Upload CSV File", type=["csv"])

    elif mode == "📜 Registry":
        st.subheader("Analysis Registry")
        st.warning("No analysis records have been created in this session yet.")

    st.markdown("---")
    st.caption("© 2028 BLOOMZ.io • Mass spectrometry tools built for under-resourced labs.")


if __name__ == "__main__":
    main()
