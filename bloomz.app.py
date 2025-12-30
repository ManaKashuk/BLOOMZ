import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# --- BLOOMZ BRANDING CONFIG ---
# Aligning with the "Intelligence Hub" visual identity [cite: 186-191]
st.set_page_config(
    page_title="BLOOMZ CORE | The Spectral Intelligence",
    page_icon="🌿",
    layout="wide",
)

# Custom CSS for Bloomz Green and Professional UI
st.markdown("""
    <style>
    .main { background-color: #F6F6F6; }
    .stButton>button { background-color: #49735A; color: white; border-radius: 8px; }
    .agent-header { color: #1A237E; font-weight: bold; border-bottom: 2px solid #49735A; }
    </style>
    """, unsafe_allow_html=True)

# --- SIDEBAR: THE INTELLIGENCE CHAIN ---
st.sidebar.image("https://via.placeholder.com/150x50?text=BLOOMZ+CORE", use_container_width=True) # Replace with your logo
st.sidebar.title("BLOOMZ CORE")
st.sidebar.markdown("**The Spectral Intelligence**")
st.sidebar.caption("Agentic Annotation & Reporting System")
st.sidebar.info("Part of the Plant-to-Compound Intelligence Chain™ [cite: 8]")

# --- THE AGENTIC BRAIN: SCORING LOGIC  ---
def agentic_scoring(row, library_df, target_plant):
    """
    This is the Agentic AI logic. It doesn't just search; it evaluates.
    1. m/z Tolerance (±0.005)
    2. RT Penalty
    3. Molecular Class Plausibility
    """
    # Filter by Strict Mass Tolerance (±0.005)
    matches = library_df[(library_df["mz_main"] - row["mz"]).abs() <= 0.005].copy()
    
    if matches.empty:
        return None

    # Calculate Individual Scores
    results = []
    for _, match in matches.iterrows():
        base_score = 100
        
        # 1. RT Penalty Logic
        # Penalty if peak RT is outside the known range for this compound
        rt_dev = 0
        if row["rt"] < match["rt_min"] or row["rt"] > match["rt_max"]:
            rt_dev = min(abs(row["rt"] - match["rt_min"]), abs(row["rt"] - match["rt_max"]))
            base_score -= (rt_dev * 20) # Significant penalty for RT mismatch
        
        # 2. Molecular Class Plausibility (The 'Botany' Brain)
        # Boost if the compound is known to be in the uploaded plant species
        plausibility_boost = 0
        if match["plant_name"].lower() == target_plant.lower():
            plausibility_boost = 15
            base_score += plausibility_boost
            
        final_score = max(0, min(100, base_score))
        
        results.append({
            "compound": match["compound_name"],
            "class": match["class"],
            "mz_error": round(abs(match["mz_main"] - row["mz"]), 5),
            "rt_status": "Valid" if rt_dev == 0 else f"Shifted ({round(rt_dev,2)}min)",
            "plausibility": "High (Native)" if plausibility_boost > 0 else "Neutral",
            "confidence": final_score
        })
    
    # Return the best candidate decided by the Agent
    return sorted(results, key=lambda x: x["confidence"], reverse=True)[0]

# --- LOAD DATA (Sample Database including Jordanian Plants) ---
@st.cache_data
def load_library():
    # Adding Jordanian context as per Phase 2 Roadmap [cite: 41]
    data = {
        "plant_name": ["Nigella sativa", "Artemisia sieberi", "Boswellia sacra", "Nigella sativa"],
        "compound_name": ["Thymoquinone", "Alpha-Thujone", "Incensole", "p-Cymene"],
        "mz_main": [164.08, 152.12, 306.25, 134.11],
        "rt_min": [8.2, 5.1, 15.4, 4.2],
        "rt_max": [8.6, 5.5, 16.0, 4.5],
        "class": ["Quinone", "Monoterpene", "Diterpene", "Monoterpene"],
    }
    return pd.DataFrame(data)

library_df = load_library()

# --- TABS: THE INTELLIGENCE HUB WORKFLOW ---
tab_ingest, tab_agent, tab_coa = st.tabs(["📥 Data Ingestion", "🧠 Agentic Workspace", "📄 Verified COA"])

# 1. DATA INGESTION (Phase 1 Deliverable) 
with tab_ingest:
    st.header("1. Ingest Shimadzu GC-MS Data")
    col1, col2 = st.columns(2)
    with col1:
        target_plant = st.selectbox("Target Botanical Species", ["Nigella sativa", "Artemisia sieberi", "Boswellia sacra", "Other"])
        user_id = st.text_input("Researcher ID (TSU/Jordan Lab)", "BLOOMZ-01")
    with col2:
        uploaded_file = st.file_uploader("Upload Raw Peak Table (CSV)", type="csv")
        st.caption("Agent expects columns: 'rt' (Retention Time) and 'mz' (Main Ion).")

    if uploaded_file:
        raw_data = pd.read_csv(uploaded_file)
        st.success(f"File '{uploaded_file.name}' ingested successfully.")
        st.dataframe(raw_data.head(), use_container_width=True)

# 2. AGENTIC WORKSPACE (The 'Spectral Intelligence' in action)
with tab_agent:
    st.header("2. Agentic Analysis & Candidate Scoring")
    if not uploaded_file:
        st.info("Please upload data in the Ingestion tab to activate the Agent.")
    else:
        st.subheader("Agent Decision Log")
        # Process peaks through the Brain
        final_results = []
        for _, row in raw_data.iterrows():
            decision = agentic_scoring(row, library_df, target_plant)
            if decision:
                decision["raw_mz"] = row["mz"]
                decision["raw_rt"] = row["rt"]
                final_results.append(decision)
        
        if final_results:
            results_df = pd.DataFrame(final_results)
            
            # Highlight high confidence hits
            st.dataframe(results_df.style.background_gradient(subset=['confidence'], cmap='Greens'), use_container_width=True)
            
            # Agent Summary
            high_conf = len(results_df[results_df["confidence"] > 80])
            st.metric("High Confidence Bioactives Detected", high_conf)
            st.session_state["results"] = results_df
        else:
            st.warning("Agent found no hits matching the strict ±0.005 m/z criteria.")

# 3. VERIFIED COA (The Commercial Output) [cite: 46]
with tab_coa:
    st.header("3. Generate Traceable Certificate of Analysis")
    if "results" not in st.session_state:
        st.info("Complete analysis to generate report.")
    else:
        st.markdown(f"### COA Report: {target_plant} Extract")
        st.write(f"**Verified by:** BLOOMZ CORE (Agentic AI)")
        st.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}")
        
        # Filter for the report
        report_data = st.session_state["results"][st.session_state["results"]["confidence"] >= 70]
        st.table(report_data[["compound", "class", "confidence", "plausibility"]])
        
        st.download_button(
            label="Download Data-Backed COA (CSV)",
            data=report_data.to_csv(index=False),
            file_name=f"BLOOMZ_COA_{target_plant.replace(' ','_')}.csv",
            mime="text/csv"
        )
        st.caption("Ready for export to partners (e.g., NOW Foods). [cite: 54]")
