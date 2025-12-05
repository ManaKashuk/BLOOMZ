import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime

st.set_page_config(
    page_title="Bloomz v0.1 – Academic GC–MS Companion",
    layout="wide",
)

st.sidebar.title("Bloomz v0.1 (Academic Only)")
st.sidebar.caption("GC–MS helper for natural products – NO suppliers, NO marketplace.")

# --- Load library_318 ---
@st.cache_data
def library_318():
    data = {
        "plant_name": ["Plant A", "Plant A", "Plant B"],
        "compound_name": ["Limonene", "β-Caryophyllene", "Costunolide"],
        "mw": [136.24, 204.36, 232.28],
        "formula": ["C10H16", "C15H24", "C15H20O3"],
        "rt_min": [5.0, 7.0, 10.2],
        "rt_max": [5.4, 7.5, 10.8],
        "mz_main": [136, 204, 232],
        "class": ["Monoterpene", "Sesquiterpene", "Sesquiterpene lactone"],
        "reference": ["PubChem / lit", "PubChem / lit", "Lit – NP review"],
    }
    return pd.DataFrame(data)

library_df = library_318()
library_318 = pd.read_csv("data/bloomz_mass_318.csv")

# Simple in-memory history store (replace with DB later if needed)
if "history" not in st.session_state:
    st.session_state["history"] = pd.DataFrame(
        columns=["timestamp", "user", "sample_name", "file_name", "top_match", "confidence"]
    )

tab_analyze, tab_results, tab_library, tab_ms, tab_history, tab_admin = st.tabs(
    ["🔍 Analyze Sample", "📊 Results & Prediction", "📚 Bioactive Library",
     "⚙ MS Optimization Guide", "🕒 User Analysis History", "📌 Admin / Roadmap"]
)

# ------------------------------------------------------------------
# TAB 1 – ANALYZE SAMPLE
# ------------------------------------------------------------------
with tab_analyze:
    st.header("Analyze a New Sample")
    col1, col2 = st.columns(2)

    with col1:
        user_name = st.text_input("Your name / initials", "")
        sample_name = st.text_input("Sample name / ID", "Plant extract X")
        sample_type = st.selectbox("Sample type", ["Plant extract", "Essential oil", "Herbal product", "Other"])
        ion_mode = st.selectbox("Ionization mode", ["ESI+", "ESI−", "APCI+", "EI"])
        instr = st.text_input("Instrument (optional)", "GC–MS")

    with col2:
        uploaded = st.file_uploader(
            "Upload GC–MS peak table (CSV)",
            type=["csv"],
            help="For v0.1, use an exported table with RT and m/z columns.",
        )
        st.caption("No live connection to instruments or suppliers – local academic use only.")

    run_btn = st.button("Run Prototype Analysis")

    if run_btn:
        if uploaded is None:
            st.error("Please upload a CSV file first.")
        else:
            peaks_df = pd.read_csv(uploaded)
            st.session_state["last_peaks"] = peaks_df
            st.session_state["last_meta"] = {
                "user": user_name or "anonymous",
                "sample_name": sample_name,
                "file_name": uploaded.name,
                "sample_type": sample_type,
                "ion_mode": ion_mode,
                "instrument": instr,
            }
            st.success("Analysis started – go to 'Results & Prediction' tab.")

# ------------------------------------------------------------------
# TAB 2 – RESULTS & PREDICTION (PROTOTYPE)
# ------------------------------------------------------------------
with tab_results:
    st.header("Results & Prototype Matching")

    if "last_peaks" not in st.session_state:
        st.info("No sample analyzed yet. Upload a CSV and click 'Run Prototype Analysis' first.")
    else:
        peaks_df = st.session_state["last_peaks"].copy()

        # Very simple mock matching: join on closest m/z
        if "mz" in [c.lower() for c in peaks_df.columns]:
            # map column name
            mz_col = [c for c in peaks_df.columns if c.lower() == "mz"][0]
            peaks_df["mz"] = peaks_df[mz_col]
        else:
            st.warning("No 'mz' column detected – showing raw table only.")
            st.dataframe(peaks_df, use_container_width=True)
        # crude matching
        matches = []
        for _, row in peaks_df.iterrows():
            mz_val = row.get("mz", None)
            if mz_val is None:
                continue
            # compute simple absolute difference
            library_df["mz_diff"] = (library_df["mz_main"] - mz_val).abs()
            best = library_df.sort_values("mz_diff").iloc[0]
            matches.append(
                {
                    "mz": mz_val,
                    "predicted_compound": best["compound_name"],
                    "class": best["class"],
                    "plant_source": best["plant_name"],
                    "mz_diff": best["mz_diff"],
                }
            )
        match_df = pd.DataFrame(matches)
        if not match_df.empty:
            # naive "confidence"
            match_df["confidence_1_5"] = pd.cut(
                match_df["mz_diff"],
                bins=[-0.01, 0.1, 0.5, 1.0, 2.0, 1000],
                labels=[5, 4, 3, 2, 1],
            ).astype(int)

            st.subheader("Prototype Match Table")
            st.dataframe(match_df, use_container_width=True)

            # Save top hit to history
            meta = st.session_state.get("last_meta", {})
            if not match_df.empty:
                top = match_df.sort_values("confidence_1_5", ascending=False).iloc[0]
                new_row = {
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "user": meta.get("user", "anonymous"),
                    "sample_name": meta.get("sample_name", ""),
                    "file_name": meta.get("file_name", ""),
                    "top_match": top["predicted_compound"],
                    "confidence": int(top["confidence_1_5"]),
                }
                st.session_state["history"] = pd.concat(
                    [st.session_state["history"], pd.DataFrame([new_row])],
                    ignore_index=True,
                )

            st.download_button(
                "Download match table (CSV)",
                data=match_df.to_csv(index=False),
                file_name="bloomz_match_results.csv",
                mime="text/csv",
            )
        else:
            st.warning("No matches could be generated with the current prototype logic.")

# ------------------------------------------------------------------
# TAB 3 – INTERNAL BIOACTIVE LIBRARY
# ------------------------------------------------------------------
with tab_library:
    st.header("Internal Bioactive Library (Academic Only)")
    st.caption("Curated from open-access data and your own GC–MS runs. No supplier links, no commercial catalog data.")
    st.dataframe(library_df, use_container_width=True)

# ------------------------------------------------------------------
# TAB 4 – MS OPTIMIZATION GUIDE
# ------------------------------------------------------------------
with tab_ms:
    st.header("MS Optimization Guide (Teaching Prototype)")
    ms_settings = pd.DataFrame({
        "sample_type": ["Alkaloids", "Flavonoids", "Essential oils"],
        "suggested_ion_mode": ["ESI+", "ESI− or APCI", "EI"],
        "resolution": ["High", "Medium", "High"],
        "fragmentation_voltage": ["35 V", "25 V", "70 eV"],
        "notes": ["For plant alkaloids", "Phenolic/flavonoid-rich extracts", "Volatile components"],
    })
    st.dataframe(ms_settings, use_container_width=True)

# ------------------------------------------------------------------
# TAB 5 – USER ANALYSIS HISTORY
# ------------------------------------------------------------------
with tab_history:
    st.header("User Analysis History (Session-Level Prototype)")
    if st.session_state["history"].empty:
        st.info("No analyses recorded yet.")
    else:
        st.dataframe(st.session_state["history"], use_container_width=True)
        st.download_button(
            "Download history (CSV)",
            data=st.session_state["history"].to_csv(index=False),
            file_name="bloomz_history.csv",
            mime="text/csv",
        )

# ------------------------------------------------------------------
# TAB 6 – ADMIN / ROADMAP
# ------------------------------------------------------------------
with tab_admin:
    st.header("Admin / Roadmap – Academic Prototype")
    st.markdown(
        """
**Scope of this version (v0.1):**
- Internal academic use only at TSU (or similar labs).
- No integration with suppliers, vendors, or commercial catalogs.
- Manual / heuristic matching only – *not* a regulated or validated identification engine.
- Uses internal + open-access data (e.g., PubChem, literature) curated into the Bloomz library.

**Future directions:**
- Better matching logic (RT + m/z + fragmentation).
- Larger internal library based on your plant projects.
- Optional connection to institutional LIMS (still research-only).
- AI scoring and structure suggestion, still without any supplier marketplace.
"""
    )
