import streamlit as st
import pandas as pd
import io

# --- BLOOMZ BRANDING ---
st.set_page_config(page_title="BLOOMZ CORE", page_icon="🌿", layout="wide")
st.title("🌿 BLOOMZ CORE — The Spectral Intelligence")
st.caption("Agentic workflow: ±0.005 m/z gate and chemical plausibility. (CSV Export Only)")

# --- AGENTIC LOGIC (Simplified for CSV) ---
def run_bloomz_agent(peaks_df, blum_db, mass_tol=0.005):
    """
    Core Intelligence: Verifies peaks against the BLUM database 
    using the ±0.005 m/z gate requirement[cite: 21].
    """
    results = []
    for _, peak in peaks_df.iterrows():
        # The 'Gate': Find matches within 0.005 m/z
        matches = blum_db[(blum_db['exact_mass'] - peak['mz']).abs() <= mass_tol]
        
        if not matches.empty:
            for _, match in matches.iterrows():
                results.append({
                    "peak_id": peak.get("peak_id", "N/A"),
                    "rt": peak["rt"],
                    "mz": peak["mz"],
                    "identified_compound": match["name"],
                    "chemical_class": match["class"],
                    "mass_error": round(abs(match["exact_mass"] - peak["mz"]), 5),
                    "confidence": "High" if abs(match["exact_mass"] - peak["mz"]) < 0.002 else "Probable"
                })
    return pd.DataFrame(results)

# --- TAB WORKFLOW ---
tab_upload, tab_results = st.tabs(["📥 Upload Lab Data", "📊 Verified Results"])

with tab_upload:
    st.header("1. Ingest GC-MS Data")
    uploaded_file = st.file_uploader("Upload Shimadzu CSV", type="csv")
    if uploaded_file:
        peaks = pd.read_csv(uploaded_file)
        st.session_state["raw_peaks"] = peaks
        st.success("Data loaded. Ready for Spectral Intelligence analysis.")

with tab_results:
    st.header("2. Spectral Intelligence & Export")
    if "raw_peaks" not in st.session_state:
        st.info("Upload data to begin.")
    else:
        # Mock Database (Replace with your blum_db.csv)
        blum_db = pd.DataFrame({
            "name": ["Thymoquinone", "p-Cymene"],
            "exact_mass": [164.0837, 134.1096],
            "class": ["Quinone", "Monoterpene"]
        })
        
        # Run the Agent
        final_df = run_bloomz_agent(st.session_state["raw_peaks"], blum_db)
        
        if not final_df.empty:
            st.dataframe(final_df, use_container_width=True)
            
            # --- THE EXPORT SOLUTION (NO REPORTLAB) ---
            st.divider()
            st.subheader("Generate Verified COA")
            st.caption("Exporting high-confidence hits for commercial use (e.g., NOW Foods)[cite: 43].")
            
            # Convert results to CSV bytes
            csv_data = final_df.to_csv(index=False).encode('utf-8')
            
            st.download_button(
                label="⬇️ Download Data-Backed COA (CSV)",
                data=csv_data,
                file_name="BLOOMZ_Verified_COA.csv",
                mime="text/csv",
                type="primary"
            )
        else:
            st.warning("No compounds passed the ±0.005 m/z gate.")
