import streamlit as st
import pandas as pd
import numpy as np
import io
import math
import difflib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple

# --- BRANDING & UI CONFIG ---
st.set_page_config(
    page_title="BLOOMZ CORE | The Spectral Intelligence",
    page_icon="🌿",
    layout="wide"
)

# Custom Styling for the "Intelligence Hub"
st.markdown("""
    <style>
    .main { background-color: #F6F6F6; }
    .stButton>button { background-color: #49735A; color: white; border-radius: 6px; width: 100%; }
    .report-card { border: 1px solid #49735A; padding: 20px; border-radius: 10px; background-color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- PARAMETERS & AGENTIC LOGIC [cite: 19-25] ---
@dataclass(frozen=True)
class AgentParams:
    mass_tolerance: float = 0.005 # Critical ±0.005 m/z gate 
    rt_ref_tolerance: float = 0.30 
    rt_penalty_weight: float = 0.25 # RT Penalty logic [cite: 23]
    w_mass: float = 0.40
    w_name: float = 0.25
    w_manual_lib: float = 0.25
    w_plaus: float = 0.10 # Molecular class plausibility 

# --- DATA INFERENCE & NORMALIZATION ---
DB_NAME_COLS = ["name", "identifier", "Compound"]
DB_MASS_COLS = ["exact_molecular_weight", "exact_mass", "mass"]
DB_CLASS_COLS = ["chemical_class", "class", "chemical_super_class"]

def _pick_col(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    lookup = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lookup:
            return lookup[c.lower()]
    return None

def name_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()

# --- SCORING FUNCTIONS ---
def get_mass_score(sample_mz: float, ref_mz: float, tol: float) -> float:
    err = abs(sample_mz - ref_mz)
    return math.exp(-(err / max(tol, 1e-12))) if err <= tol else 0.0

def get_rt_penalty(peak_rt, mass, a=3.0, b=-5.0):
    # Heuristic: Expected RT = a*ln(mass) + b
    expected = a * math.log(max(mass, 1e-9)) + b
    delta = peak_rt - expected
    return min(0.5, abs(delta) * 0.25) if delta < 0 else 0.0

# --- THE AGENTIC ENGINE ---
def agent_analyze(row, blum_db, species_keywords, params):
    sample_mz = float(row["mz"])
    peak_rt = float(row["rt"])
    
    # Apply ±0.005 m/z Gate 
    candidates = blum_db[
        (blum_db["exact_mass"] >= sample_mz - params.mass_tolerance) & 
        (blum_db["exact_mass"] <= sample_mz + params.mass_tolerance)
    ].copy()

    if candidates.empty:
        return None

    # Calculate Multi-Factor Scores
    results = []
    for _, cand in candidates.iterrows():
        m_score = get_mass_score(sample_mz, cand["exact_mass"], params.mass_tolerance)
        p_penalty = get_rt_penalty(peak_rt, cand["exact_mass"])
        
        # Plausibility Check 
        is_plausible = any(k.lower() in str(cand["class"]).lower() for k in species_keywords)
        plaus_score = 1.0 if is_plausible else 0.5
        
        # Final Agentic Confidence
        conf = (params.w_mass * m_score) + (params.w_plaus * plaus_score) - p_penalty
        conf = max(0.0, min(1.0, conf))
        
        results.append({
            "name": cand["blum_name"],
            "class": cand["class"],
            "mass_error": round(cand["exact_mass"] - sample_mz, 5),
            "confidence": round(conf, 3),
            "grade": "High" if conf >= 0.85 else "Probable" if conf >= 0.65 else "Possible"
        })
    
    return sorted(results, key=lambda x: x["confidence"], reverse=True)[0]

# --- INTERFACE: THE INTELLIGENCE HUB ---
def main():
    st.sidebar.image("https://via.placeholder.com/150x50?text=BLOOMZ+CORE")
    st.sidebar.title("BLOOMZ CORE")
    st.sidebar.markdown("**The Spectral Intelligence**")
    
    params = AgentParams() # Default params
    
    tab_ingest, tab_process, tab_report = st.tabs(["🌿 Ingest", "🧠 Agentic Analyze", "📄 Export COA"])

    with tab_ingest:
        st.subheader("Data Ingestion Pipeline")
        col1, col2 = st.columns(2)
        with col1:
            species = st.selectbox("Species Context", ["Nigella sativa", "Artemisia sieberi", "Boswellia sacra"])
            keywords = ["quinone", "terpene", "phenolic"] if species == "Nigella sativa" else ["terpene"]
        with col2:
            peak_file = st.file_uploader("Upload Instrument CSV", type="csv")
            db_file = st.file_uploader("Upload Reference DB (Optional)", type="csv")

    with tab_process:
        if peak_file:
            peaks_df = pd.read_csv(peak_file)
            # Handle headers for reference DB
            raw_db = pd.read_csv(db_file) if db_file else pd.read_csv("blum_db.csv")
            
            # Normalize DB for the Agent
            name_c = _pick_col(raw_db, DB_NAME_COLS)
            mass_c = _pick_col(raw_db, DB_MASS_COLS)
            class_c = _pick_col(raw_db, DB_CLASS_COLS)
            
            blum_db = pd.DataFrame({
                "blum_name": raw_db[name_c].fillna("Unknown"),
                "exact_mass": pd.to_numeric(raw_db[mass_c], errors='coerce'),
                "class": raw_db[class_c].fillna("Unclassified")
            }).dropna(subset=["exact_mass"])

            if st.button("Activate BLOOMZ CORE Intelligence", type="primary"):
                results = []
                for _, row in peaks_df.iterrows():
                    res = agent_analyze(row, blum_db, keywords, params)
                    if res:
                        results.append({**row.to_dict(), **res})
                
                if results:
                    st.session_state["scored_df"] = pd.DataFrame(results)
                    st.success("Spectral Intelligence Analysis Complete.")
                    st.dataframe(st.session_state["scored_df"], use_container_width=True)

    with tab_report:
        if "scored_df" in st.session_state:
            st.markdown('<div class="report-card">', unsafe_allow_html=True)
            st.markdown("### Verified Certificate of Analysis (Digital COA)")
            st.write(f"**Target Species:** {species}")
            st.write(f"**Verification Protocol:** Agentic ±0.005 m/z Gate")
            
            report_df = st.session_state["scored_df"]
            st.table(report_df[report_df["confidence"] >= 0.70][["name", "class", "confidence", "grade"]])
            
            csv = report_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Verified COA (CSV)", data=csv, file_name="BLOOMZ_COA.csv", mime="text/csv")
            st.markdown('</div>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
