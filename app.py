import os
import io
import json
import hmac
import base64
import hashlib
import sqlite3
import secrets
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
AUTH_DB = DATA_DIR / "auth.db"

BLOOMZ_GREEN = "#49735A"
BLOOMZ_LIGHT = "#F8F9FA"

APP_NAME = "BLOOMZ Analyzer"
APP_TAGLINE = "Mass Spectrometry Tools Built for Under-Resourced Labs"
APP_MISSION = "Because at HBCUs, talent already exists — the right tools help it bloom."

# ------------------ DATA LOADER ------------------
@st.cache_data
def load_final_db():
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


def _show_bubble(text: str, avatar_b64: str = None, is_user: bool = False):
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
            <div style="background:{bg}; padding:15px; border-radius:15px; max-width:80%; box-shadow: 0px 2px 5px rgba(0,0,0,0.05); border: 1px solid #eee; color: {color};">
                {text}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ------------------ AUTH HELPERS ------------------
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(AUTH_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_db():
    conn = get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'reviewer',
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored_value: str) -> bool:
    try:
        salt_hex, digest_hex = stored_value.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def get_user_by_email(email: str):
    conn = get_conn()
    user = conn.execute(
        "SELECT * FROM users WHERE email = ?", (_normalize_email(email),)
    ).fetchone()
    conn.close()
    return user


def create_user(full_name: str, email: str, password: str, role: str = "reviewer"):
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO users (full_name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (full_name.strip(), _normalize_email(email), _hash_password(password), role),
        )
        conn.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "An account with that email already exists."
    finally:
        conn.close()


def verify_login(email: str, password: str):
    user = get_user_by_email(email)
    if not user:
        return None
    if not user["is_active"]:
        return None
    if not _verify_password(password, user["password_hash"]):
        return None
    return user


def update_user_password(email: str, new_password: str):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET password_hash = ? WHERE email = ?",
        (_hash_password(new_password), _normalize_email(email)),
    )
    conn.commit()
    conn.close()


def set_user_active(email: str, is_active: bool):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET is_active = ? WHERE email = ?",
        (1 if is_active else 0, _normalize_email(email)),
    )
    conn.commit()
    conn.close()


def list_users():
    conn = get_conn()
    users = conn.execute(
        "SELECT full_name, email, role, is_active, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return users


def seed_admin_from_secrets():
    admin_email = st.secrets.get("ADMIN_EMAIL", os.getenv("ADMIN_EMAIL", "")).strip().lower()
    admin_password = st.secrets.get("ADMIN_PASSWORD", os.getenv("ADMIN_PASSWORD", ""))
    admin_name = st.secrets.get("ADMIN_NAME", os.getenv("ADMIN_NAME", "BLOOMZ Admin"))

    if admin_email and admin_password and not get_user_by_email(admin_email):
        create_user(admin_name, admin_email, admin_password, role="admin")


def require_password_rules(password: str):
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    return True, ""


def login_screen():
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), width=220)

    st.markdown(f"<h1>{APP_NAME}</h1>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='color:{BLOOMZ_GREEN}; font-weight:600; font-size:1.1rem;'>{APP_TAGLINE}</p>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<p>{APP_MISSION}</p>", unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["Login", "Register"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submit_login = st.form_submit_button("Login", use_container_width=True)

        if submit_login:
            user = verify_login(email, password)
            if user:
                st.session_state.authenticated = True
                st.session_state.user_email = user["email"]
                st.session_state.user_name = user["full_name"]
                st.session_state.user_role = user["role"]
                st.success("Login successful.")
                st.rerun()
            st.error("Invalid email or password.")

    with tab_register:
        with st.form("register_form"):
            full_name = st.text_input("Full name")
            email = st.text_input("Email address")
            password = st.text_input("Create password", type="password")
            confirm_password = st.text_input("Confirm password", type="password")
            access_code = st.text_input("Access code", type="password", help="Use the reviewer access code you share privately.")
            submit_register = st.form_submit_button("Create account", use_container_width=True)

        if submit_register:
            required_access_code = st.secrets.get("REVIEWER_ACCESS_CODE", os.getenv("REVIEWER_ACCESS_CODE", ""))
            if not full_name.strip() or not email.strip() or not password:
                st.error("Please complete all required fields.")
            elif password != confirm_password:
                st.error("Passwords do not match.")
            else:
                valid_password, password_msg = require_password_rules(password)
                if not valid_password:
                    st.error(password_msg)
                elif required_access_code and access_code != required_access_code:
                    st.error("Invalid access code.")
                else:
                    ok, msg = create_user(full_name, email, password)
                    if ok:
                        st.success("Account created. You can now log in.")
                    else:
                        st.error(msg)


def logout():
    for key in ["authenticated", "user_email", "user_name", "user_role", "chat"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()


def admin_panel():
    st.subheader("Admin Access")
    st.caption("Create reviewer accounts and manage access for website reviewers.")

    with st.expander("Create reviewer account", expanded=False):
        with st.form("admin_create_user"):
            full_name = st.text_input("Reviewer name")
            email = st.text_input("Reviewer email")
            temp_password = st.text_input("Temporary password", type="password")
            create_submit = st.form_submit_button("Create reviewer", use_container_width=True)

        if create_submit:
            if not full_name.strip() or not email.strip() or not temp_password:
                st.error("Please complete all reviewer fields.")
            else:
                valid_password, password_msg = require_password_rules(temp_password)
                if not valid_password:
                    st.error(password_msg)
                else:
                    ok, msg = create_user(full_name, email, temp_password, role="reviewer")
                    if ok:
                        st.success(f"Reviewer account created for {_normalize_email(email)}")
                    else:
                        st.error(msg)

    with st.expander("Manage users", expanded=False):
        users = list_users()
        if users:
            df = pd.DataFrame([dict(row) for row in users])
            df["is_active"] = df["is_active"].map({1: "Active", 0: "Disabled"})
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No users found.")

        with st.form("admin_manage_user"):
            target_email = st.text_input("User email to update")
            new_password = st.text_input("New password (optional)", type="password")
            status_choice = st.selectbox("Account status", ["Keep current", "Active", "Disabled"])
            manage_submit = st.form_submit_button("Apply changes", use_container_width=True)

        if manage_submit:
            target = get_user_by_email(target_email)
            if not target:
                st.error("User not found.")
            else:
                if new_password:
                    valid_password, password_msg = require_password_rules(new_password)
                    if not valid_password:
                        st.error(password_msg)
                        return
                    update_user_password(target_email, new_password)
                if status_choice == "Active":
                    set_user_active(target_email, True)
                elif status_choice == "Disabled":
                    set_user_active(target_email, False)
                st.success("User updated.")
                st.rerun()

# ------------------ MAIN APP ------------------
def main():
    st.set_page_config(page_title=APP_NAME, page_icon="🌿", layout="wide")

    st.markdown(
        f"""
        <style>
        .stApp {{ background-color: {BLOOMZ_LIGHT}; }}
        [data-testid="stSidebar"] {{ background-color: white; border-right: 1px solid #eee; }}
        .divider-strong {{ border-top: 5px solid #222; margin: 10px 0 25px 0; }}
        .report-box {{ border: 2px solid {BLOOMZ_GREEN}; padding: 20px; border-radius: 12px; background: white; }}
        .stChatInputContainer {{ border-radius: 10px; }}
        .auth-box {{ background: white; border: 1px solid #e6e6e6; border-radius: 16px; padding: 28px; }}
        </style>
        """,
        unsafe_allow_html=True,
    )

    init_auth_db()
    seed_admin_from_secrets()

    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        login_screen()
        st.stop()

    db = load_final_db()
    chat_avatar = _img_to_b64(CHAT_ICON)

    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=200)

        st.title(APP_NAME)
        st.caption(APP_TAGLINE)
        st.success(f"Logged in as {st.session_state.user_name}")
        st.caption(f"Role: {st.session_state.user_role}")

        mode_options = ["🏠 Home", "🔍 Discovery", "📊 Batch Upload", "📜 Registry"]
        if st.session_state.user_role == "admin":
            mode_options.append("🔐 Admin")

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
                <li><b>Library:</b> 499 Verified Compounds</li>
                <li><b>Mass Tolerance:</b> ±{mass_gate} m/z</li>
                <li><b>Focus:</b> Practical workflows for discovery and reporting</li>
            </div>
            """,
            unsafe_allow_html=True,
        )

    elif mode == "🔍 Discovery":
        col_chat, col_data = st.columns([3, 2])

        with col_chat:
            st.subheader("💬 BLOOMZ Assistant")
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
                        "content": f"Reviewing **{prompt}** against the BLOOMZ library. Current mass tolerance is ±{mass_gate} m/z. I’ll help you narrow likely compound candidates and move toward a usable result.",
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

    elif mode == "🔐 Admin":
        admin_panel()

    st.markdown("---")
    st.caption("© 2025 BLOOMZ • Mass spectrometry tools built for under-resourced labs.")


if __name__ == "__main__":
    main()
