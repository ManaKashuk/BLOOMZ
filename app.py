# =========================
# file: app.py
# =========================
"""
BLOOMZ CORE — The Spectral Intelligence
- Weighted agent scoring: ±0.005 m/z gate, RT penalty, class plausibility
- Export: Scored CSV + Digital Certificate of Analysis (On-screen)
- No ReportLab dependency
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

# -------------------------
# Core params (spec: ±0.005) [cite: 21]
# -------------------------
@dataclass(frozen=True)
class AgentParams:
    mass_tolerance: float = 0.005
    top_k_blum: int = 5
    rt_ref_tolerance: float = 0.30  # minutes
    rt_heavy_early_strength: float = 0.25 
    expected_rt_a: float = 3.0  
    expected_rt_b: float = -5.0
    w_mass: float = 0.40
    w_name: float = 0.25
    w_manual_lib: float = 0.25
    w_plaus: float = 0.10

# -------------------------
# Column inference helpers
# -------------------------
RT_COLS = ["RT", "Retention Time", "retention_time", "rt"]
MZ_COLS = ["m/z", "mz", "Mass", "mass", "Base Peak", "base_peak", "MZ"]
INT_COLS = ["Area", "Height", "Intensity", "intensity", "area", "height"]
DB_NAME_COLS = ["name", "identifier", "Name", "Compound"]
DB_MASS_COLS = ["exact_molecular_weight", "exact_mass", "mass", "Exact Mass"]
DB_CLASS_COLS = ["chemical_class", "class", "superclass", "Class"]

def _pick_col(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    lookup = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lookup:
            return lookup[c.lower()]
    return None

def name_similarity(a: str, b: str) -> float:
    a, b = (a or "").strip().lower(), (b or "").strip().lower()
    if not a or not b: return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()

# -------------------------
# Data loading
# -------------------------
def load_peaks_from_instrument_csv(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(file_bytes))
    rt_col, mz_col = _pick_col(df, RT_COLS), _pick_col(df, MZ_COLS)
    if not rt_col or not mz_col:
        raise ValueError("Instrument CSV must include RT and m/z columns.")
    int_col = _pick_col(df, INT_COLS)
    peaks = pd.DataFrame({
        "rt": pd.to_numeric(df[rt_col], errors="coerce"),
        "mz": pd.to_numeric(df[mz_col], errors="coerce"),
        "intensity": pd.to_numeric(df[int_col], errors="coerce") if int_col else 1.0,
    }).dropna(subset=["rt", "mz"]).reset_index(drop=True)
    peaks.index.name = "peak_id"
    return peaks.reset_index()

def normalize_blum_db(df: pd.DataFrame) -> pd.DataFrame:
    name_col, mass_col = _pick_col(df, DB_NAME_COLS), _pick_col(df, DB_MASS_COLS)
    if not name_col or not mass_col:
        raise ValueError("BLUM DB must include name + mass columns.")
    class_col = _pick_col(df, DB_CLASS_COLS)
    out = pd.DataFrame({
        "blum_name": df[name_col].fillna(df.get("identifier", "Unknown")).astype(str),
        "blum_exact_mass": pd.to_numeric(df[mass_col], errors="coerce"),
        "blum_class": df[class_col].astype(str) if class_col else "",
    }).dropna(subset=["blum_exact_mass"]).reset_index(drop=True)
    return out

def load_blum_db(uploaded: Optional[bytes]) -> pd.DataFrame:
    if uploaded: return normalize_blum_db(pd.read_csv(io.BytesIO(uploaded)))
    for path in ["data/blum_db.csv", "data/BLUM_db.csv"]:
        if os.path.exists(path): return normalize_blum_db(pd.read_csv(path))
    raise FileNotFoundError("No BLUM DB found.")

# -------------------------
# Scoring model [cite: 19-25]
# -------------------------
def mass_term(sample_mz: float, ref_mz: float, tol: float) -> float:
    err = abs(sample_mz - ref_mz)
    return math.exp(-(err / max(tol, 1e-12))) if err <= tol else 0.0

def rt_penalty(peak_rt: float, candidate_mass: float, params: AgentParams) -> Tuple[float, float]:
    expected = params.expected_rt_a * math.log(max(candidate_mass, 1e-9)) + params.expected_rt_b
    delta = float(peak_rt - expected)
    penalty = min(0.5, abs(delta) * params.rt_heavy_early_strength) if delta < 0 else 0.0
    return penalty, delta

DEFAULT_SPECIES_RULES: Dict[str, Dict[str, Any]] = {
    "Nigella sativa": {"plausible_class_keywords": ["quinone", "thymo", "terpene", "phenolic", "alkaloid"]},
    "Artemisia sieberi": {"plausible_class_keywords": ["terpene", "sesquiterpene", "monoterpene", "flavonoid"]},
    "Boswellia sacra": {"plausible_class_keywords": ["triterpene", "boswellic", "terpene", "resin"]},
}

def plausibility_score(species: str, blum_class: str, keyword_csv: str) -> float:
    cls = (blum_class or "").lower()
    keywords = [k.strip().lower() for k in (keyword_csv or "").split(",") if k.strip()]
    return 1.0 if any(k in cls for k in keywords) else 0.5

def agent_score_row(row: pd.Series, blum: pd.DataFrame, species: str, plaus_keywords_csv: str, params: AgentParams) -> Dict[str, Any]:
    sample_mz, peak_rt = float(row["mz"]), float(row["rt"])
    manual_name = str(row.get("manual_hit_name", "") or "")
    
    # Filter candidates within ±0.005 m/z gate [cite: 21]
    lo, hi = sample_mz - params.mass_tolerance, sample_mz + params.mass_tolerance
    cands = blum[(blum["blum_exact_mass"] >= lo) & (blum["blum_exact_mass"] <= hi)].copy()
    
    if cands.empty: return {"confidence": 0.0, "agent_grade": "Flagged", "best_blum_name": "None"}

    cands["mass_term"] = cands["blum_exact_mass"].apply(lambda m: mass_term(sample_mz, float(m), params.mass_tolerance))
    cands["name_sim"] = cands["blum_name"].apply(lambda n: name_similarity(manual_name, str(n)))
    cands["plaus"] = cands["blum_class"].apply(lambda c: plausibility_score(species, str(c), plaus_keywords_csv))
    
    best = cands.sort_values("mass_term", ascending=False).iloc[0]
    penalty, rt_delta = rt_penalty(peak_rt, float(best["blum_exact_mass"]), params)
    
    conf = (params.w_mass * best["mass_term"] + params.w_name * best["name_sim"] + params.w_plaus * best["plaus"] - penalty)
    conf = max(0.0, min(1.0, conf))
    grade = "High Confidence" if conf >= 0.90 else "Probable" if conf >= 0.70 else "Possible" if conf >= 0.50 else "Flagged"

    return {
        "best_blum_name": str(best["blum_name"]),
        "best_blum_class": str(best["blum_class"]),
        "confidence": round(conf, 3),
        "agent_grade": grade,
        "rt_delta": round(rt_delta, 3),
        "rt_penalty": round(penalty, 3)
    }

# -------------------------
# UI Implementation
# -------------------------
def main():
    st.set_page_config(page_title="BLOOMZ CORE", page_icon="🌿", layout="wide")
    st.title("🌿 BLOOMZ CORE — The Spectral Intelligence")
    st.caption("Agentic workflow: ±0.005 m/z gate, RT penalty, and chemical plausibility. [cite: 8]")

    with st.sidebar:
        st.header("Agent Settings")
        params = AgentParams(
            mass_tolerance=float(st.number_input("Mass tolerance (± m/z)", value=0.005, format="%.6f")),
            w_mass=float(st.slider("Weight: mass", 0.0, 1.0, 0.40))
        )
        st.divider()
        blum_upload = st.file_uploader("Upload BLUM DB CSV", type=["csv"])

    tab_upload, tab_process, tab_report = st.tabs(["🌿 Upload", "🔬 Process", "📄 Export"])

    with tab_upload:
        peaks_file = st.file_uploader("Instrument Export CSV", type=["csv"])
        species = st.selectbox("Species Context", options=list(DEFAULT_SPECIES_RULES.keys()))
        plaus_keywords = st.text_input("Plausibility keywords", value=", ".join(DEFAULT_SPECIES_RULES[species]["plausible_class_keywords"]))
        if peaks_file:
            st.session_state["peaks"] = load_peaks_from_instrument_csv(peaks_file.read())
            st.session_state["meta"] = {"species": species, "plaus_keywords": plaus_keywords}
            st.dataframe(st.session_state["peaks"].head(10))

    with tab_process:
        if "peaks" not in st.session_state: st.warning("Upload data first.")
        else:
            blum = load_blum_db(blum_upload.read() if blum_upload else None)
            if st.button("Activate Spectral Intelligence", type="primary"):
                scored = st.session_state["peaks"].apply(lambda r: pd.Series(agent_score_row(r, blum, st.session_state["meta"]["species"], st.session_state["meta"]["plaus_keywords"], params)), axis=1)
                st.session_state["scored"] = pd.concat([st.session_state["peaks"], scored], axis=1)
                st.success("Analysis Complete.")
                st.dataframe(st.session_state["scored"])

    with tab_report:
        if "scored" in st.session_state:
            st.markdown("### Digital Certificate of Analysis")
            st.caption("Verified by BLOOMZ CORE Agentic Scoring [cite: 248]")
            st.table(st.session_state["scored"][st.session_state["scored"]["confidence"] >= 0.70][["peak_id", "rt", "mz", "best_blum_name", "confidence", "agent_grade"]])
            
            csv = st.session_state["scored"].to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Scored CSV", data=csv, file_name="bloomz_core_report.csv", mime="text/csv")

if __name__ == "__main__": main()
