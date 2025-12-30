# =========================
# file: app.py
# =========================
"""
BLOOMZ CORE (The Spectral Intelligence) — Streamlit Verification Workspace
Fixed to integrate with BLUM_db.csv (499 compounds)
"""

from __future__ import annotations
import difflib
import io
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple
import pandas as pd
import streamlit as st
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

# -------------------------
# Core params (spec: ±0.005) 
# -------------------------
@dataclass(frozen=True)
class AgentParams:
    mass_tolerance: float = 0.005
    top_k_blum: int = 5
    rt_ref_tolerance: float = 0.30  
    rt_heavy_early_strength: float = 0.25  
    expected_rt_a: float = 3.0  
    expected_rt_b: float = -5.0
    w_mass: float = 0.40
    w_name: float = 0.25
    w_manual_lib: float = 0.25
    w_plaus: float = 0.10

# -------------------------
# UPDATED: Column inference for BLUM_db.csv
# -------------------------
RT_COLS = ["RT", "Retention Time", "retention_time", "rt"]
MZ_COLS = ["m/z", "mz", "Mass", "mass", "Base Peak", "base_peak", "MZ"]
INT_COLS = ["Area", "Height", "Intensity", "intensity", "area", "height"]

# Added headers found in your BLUM_db.csv
DB_NAME_COLS = ["name", "compound_name", "identifier", "Name", "Compound"]
DB_MASS_COLS = ["exact_molecular_weight", "exact_mass", "monoisotopic_mass", "mass", "Exact Mass"]
DB_CLASS_COLS = ["chemical_class", "class", "superclass", "chemical_super_class", "Class"]

RTREF_NAME_COLS = ["name", "compound_name", "Name", "Compound"]
RTREF_RT_COLS = ["expected_rt", "rt", "RT", "Retention Time", "Expected RT"]

def _pick_col(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    lookup = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lookup:
            return lookup[c.lower()]
    return None

def name_similarity(a: str, b: str) -> float:
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()

# -------------------------
# Data loading & Normalization
# -------------------------
def load_peaks_from_instrument_csv(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(file_bytes))
    rt_col = _pick_col(df, RT_COLS)
    mz_col = _pick_col(df, MZ_COLS)
    if not rt_col or not mz_col:
        raise ValueError(f"Instrument CSV must include RT and m/z columns.")
    int_col = _pick_col(df, INT_COLS)
    peaks = pd.DataFrame({
        "rt": pd.to_numeric(df[rt_col], errors="coerce"),
        "mz": pd.to_numeric(df[mz_col], errors="coerce"),
        "intensity": pd.to_numeric(df[int_col], errors="coerce") if int_col else 1.0,
    }).dropna(subset=["rt", "mz"]).reset_index(drop=True)
    peaks.index.name = "peak_id"
    return peaks.reset_index()

def normalize_blum_db(df: pd.DataFrame) -> pd.DataFrame:
    # Updated to handle Fallback to 'identifier' if 'name' is NaN
    name_col = _pick_col(df, DB_NAME_COLS)
    mass_col = _pick_col(df, DB_MASS_COLS)
    class_col = _pick_col(df, DB_CLASS_COLS)
    
    if not name_col or not mass_col:
        raise ValueError("BLUM DB must include name/identifier + mass columns.")

    # Create fallback for missing names using identifier column if available
    fallback_col = "identifier" if "identifier" in df.columns else name_col
    
    out = pd.DataFrame({
        "blum_name": df[name_col].fillna(df[fallback_col]).astype(str),
        "blum_exact_mass": pd.to_numeric(df[mass_col], errors="coerce"),
        "blum_class": df[class_col].astype(str) if class_col else "",
    }).dropna(subset=["blum_exact_mass"]).reset_index(drop=True)
    return out

def load_blum_db(uploaded: Optional[bytes]) -> pd.DataFrame:
    if uploaded:
        return normalize_blum_db(pd.read_csv(io.BytesIO(uploaded)))
    # Try both cases for the local file
    for path in ["data/blum_db.csv", "data/BLUM_db.csv"]:
        if os.path.exists(path):
            return normalize_blum_db(pd.read_csv(path))
    raise FileNotFoundError("No BLUM DB found.")

# ... [Keep rest of your mathematical functions: mass_term, rt_penalty, etc.] ...

# -------------------------
# UI Implementation
# -------------------------
def main() -> None:
    st.set_page_config(page_title="BLOOMZ CORE", page_icon="🌿", layout="wide")
    st.title("🌿 BLOOMZ CORE — The Spectral Intelligence")
    st.caption("Agentic workflow: ±0.005 m/z gate, RT penalty, and chemical plausibility[cite: 21, 248].")

    with st.sidebar:
        st.header("Agent Settings")
        params = AgentParams(
            mass_tolerance=float(st.number_input("Mass tolerance (± m/z)", value=0.005, format="%.6f")),
            # ... [Keep other sidebar param inputs] ...
        )
        st.divider()
        st.subheader("Reference Data")
        blum_upload = st.file_uploader("Upload BLUM DB CSV", type=["csv"])

    tab_upload, tab_process, tab_report = st.tabs(["🌿 Upload", "🔬 Process", "📄 Report"])

    # ... [Keep your tab logic, ensuring it uses the params and updated loaders] ...
