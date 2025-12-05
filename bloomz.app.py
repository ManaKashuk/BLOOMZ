# bloomz_app.py
# Prototype Streamlit layout for Bloomz v0.1
# Bioactive Library for Mass Spectrometry – Natural Products GC–MS Support

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# -----------------------
# Page Configuration
# -----------------------
st.set_page_config(
    page_title="Bloomz v0.1 – GC–MS Natural Products Library",
    layout="wide",
)

# -----------------------
# Helper: Create Example Data if No File
# -----------------------
def create_example_library() -> pd.DataFrame:
    data = {
        "sample": ["Plant_A_leaf", "Plant_A_leaf", "Plant_B_root", "Herbal_mix"] * 2,
        "rt_min": [5.1, 7.3, 10.4, 12.8, 6.0, 9.2, 11.5, 14.1],
        "rt_max": [5.3, 7.5, 10.7, 13.1, 6.3, 9.5, 11.8, 14.4],
        "rt_center": [5.2, 7.4, 10.55, 12.95, 6.15, 9.35, 11.65, 14.25],
        "mz_main": [152, 204, 218, 136, 180, 196, 222, 150],
        "putative_compound": [
            "Limonene",
            "β-Caryophyllene",
            "Costunolide",
            "Puupehenone-like",
            "α-Pinene",
            "Humulene",
            "Sesquiterpene lactone X",
            "Phenolic ester Y",
        ],
        "compound_class": [
            "Monoterpene",
            "Sesquiterpene",
            "Sesquiterpene lactone",
            "Meroterpenoid",
            "Monoterpene",
            "Sesquiterpene",
            "Sesquiterpene lactone",
            "Phenolic",
        ],
        "confidence_1_5": [3, 4, 2, 1, 4, 3, 2, 1],
        "reference": [
            "NIST match + lit",
            "NIST match",
            "Predicted (lit RT)",
            "Putative, low confidence",
            "NIST match",
            "NIST match",
            "Putative (class only)",
            "Class-based",
        ],
        "notes": [
            "Major volatile",
            "Known anti-inflammatory",
            "Candidate SL – further confirmation needed",
            "Marine-like meroterpenoid; check HRMS",
            "Common needle oil monoterpene",
            "Co-elution suspected",
            "Fragmentation resembles costunolide core",
            "Broad phenolic region",
        ],
    }
    df = pd.DataFrame(data)
    return df


def load_uploaded_csv(uploaded_file: st.runtime.uploaded_file_manager.UploadedFile) -> pd.DataFrame:
    df = pd.read_csv(uploaded_file)
    # Try to infer or repair minimal columns if missing
    # Expecting at least RT + m/z, we will map into our internal schema as best as possible.
    # This is intentionally simple for v0.1.
    col_lower = [c.lower() for c in df.columns]

    # Minimal mapping
    rt_col = None
    for candidate in ["rt", "retention_time", "time"]:
        if candidate in col_lower:
            rt_col = df.columns[col_lower.index(candidate)]
            break

    mz_col = None
    for candidate in ["mz", "m_z", "mass"]:
        if candidate in col_lower:
            mz_col = df.columns[col_lower.index(candidate)]
            break

    # Create a basic Bloomz-style table
    bloomz_df = pd.DataFrame()
    bloomz_df["sample"] = df.get("sample", "Unknown_sample")
    if rt_col is not None:
        bloomz_df["rt_center"] = df[rt_col]
        bloomz_df["rt_min"] = df[rt_col] - 0.05
        bloomz_df["rt_max"] = df[rt_col] + 0.05
    else:
        bloomz_df["rt_center"] = np.nan
        bloomz_df["rt_min"] = np.nan
        bloomz_df["rt_max"] = np.nan

    if mz_col is not None:
        bloomz_df["mz_main"] = df[mz_col]
    else:
        bloomz_df["mz_main"] = np.nan

    # Placeholders for curated/annotated fields
    bloomz_df["putative_compound"] = df.get("putative_compound", "Unknown")
    bloomz_df["compound_class"] = df.get("compound_class", "Unassigned")
    bloomz_df["confidence_1_5"] = df.get("confidence_1_5", 1)
    bloomz_df["reference"] = df.get("reference", "")
    bloomz_df["notes"] = df.get("notes", "")

    return bloomz_df


# -----------------------
# Sidebar – Controls
# -----------------------
st.sidebar.title("Bloomz v0.1 Controls")

uploaded_file = st.sidebar.file_uploader(
    "Upload GC–MS peak/annotation CSV (optional)",
    type=["csv"],
    help="If not provided, an example Bloomz library will be used.",
)

if uploaded_file is not None:
    df = load_uploaded_csv(uploaded_file)
    using_example = False
else:
    df = create_example_library()
    using_example = True

st.sidebar.markdown("---")
st.sidebar.subheader("Filters")

# Sample filter
samples = sorted(df["sample"].dropna().unique().tolist())
selected_samples = st.sidebar.multiselect(
    "Samples",
    options=samples,
    default=samples,
)

# Class filter
classes = sorted(df["compound_class"].dropna().unique().tolist())
selected_classes = st.sidebar.multiselect(
    "Compound classes",
    options=classes,
    default=classes,
)

# Confidence filter
min_conf, max_conf = int(df["confidence_1_5"].min()), int(df["confidence_1_5"].max())
confidence_range = st.sidebar.slider(
    "Confidence (1 = low, 5 = high)",
    min_value=min_conf,
    max_value=max_conf,
    value=(min_conf, max_conf),
    step=1,
)

# RT range filter (if available)
if df["rt_center"].notna().any():
    rt_min = float(df["rt_center"].min())
    rt_max = float(df["rt_center"].max())
    rt_range = st.sidebar.slider(
        "Retention time window",
        min_value=round(rt_min, 2),
        max_value=round(rt_max, 2),
        value=(round(rt_min, 2), round(rt_max, 2)),
        step=0.1,
    )
else:
    rt_range = (None, None)

# -----------------------
# Apply Filters
# -----------------------
filtered = df.copy()

if selected_samples:
    filtered = filtered[filtered["sample"].isin(selected_samples)]

if selected_classes:
    filtered = filtered[filtered["compound_class"].isin(selected_classes)]

filtered = filtered[
    (filtered["confidence_1_5"] >= confidence_range[0])
    & (filtered["confidence_1_5"] <= confidence_range[1])
]

if rt_range[0] is not None:
    filtered = filtered[
        (filtered["rt_center"] >= rt_range[0])
        & (filtered["rt_center"] <= rt_range[1])
    ]

# -----------------------
# Main Layout
# -----------------------
st.title("Bloomz v0.1 – Bioactive Library for GC–MS Natural Products")

if using_example:
    st.info(
        "No file uploaded – showing example Bloomz library. "
        "Upload your own GC–MS peak/annotation CSV in the sidebar to work with real data."
    )

st.markdown(
    """
**Bloomz v0.1** is an early prototype for a GC–MS–supported natural products library.

The goals of this prototype:
- Demonstrate how GC–MS peaks and annotations can be organized.
- Support student training in compound classes and annotation logic.
- Provide a foundation for future AI-assisted matching and workflow optimization.
"""
)

# Quick metrics
col_m1, col_m2, col_m3 = st.columns(3)
with col_m1:
    st.metric("Total compounds in view", len(filtered))
with col_m2:
    st.metric("Unique samples", filtered["sample"].nunique())
with col_m3:
    st.metric("Classes represented", filtered["compound_class"].nunique())

st.markdown("---")

tab_library, tab_peaks, tab_cards, tab_admin = st.tabs(
    ["📚 Library View", "📈 Peak Explorer", "🧬 Compound Cards", "⚙ Admin / Roadmap"]
)

# -----------------------
# Tab 1 – Library View
# -----------------------
with tab_library:
    st.subheader("Current Bloomz Library Slice")
    st.caption("Filtered by sample, class, confidence, and retention time.")

    # Reorder columns for nicer display
    display_cols = [
        "sample",
        "putative_compound",
        "compound_class",
        "rt_center",
        "rt_min",
        "rt_max",
        "mz_main",
        "confidence_1_5",
        "reference",
        "notes",
    ]
    show_df = filtered[display_cols].sort_values(["sample", "rt_center"])

    st.dataframe(show_df, use_container_width=True)

    st.download_button(
        "Download current view as CSV",
        data=show_df.to_csv(index=False),
        file_name="bloomz_current_view.csv",
        mime="text/csv",
    )

# -----------------------
# Tab 2 – Peak Explorer
# -----------------------
with tab_peaks:
    st.subheader("GC–MS Peak Explorer")

    if filtered["rt_center"].notna().any():
        chart = (
            alt.Chart(filtered)
            .mark_circle(size=80)
            .encode(
                x=alt.X("rt_center", title="Retention time (min)"),
                y=alt.Y("mz_main", title="Main m/z"),
                color=alt.Color("compound_class", title="Class"),
                tooltip=[
                    "sample",
                    "putative_compound",
                    "compound_class",
                    "rt_center",
                    "mz_main",
                    "confidence_1_5",
                    "reference",
                ],
            )
            .interactive()
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.warning(
            "No retention time column detected in the data. "
            "Provide an RT column (rt/retention_time/time) in your CSV to enable the Peak Explorer."
        )

    st.markdown(
        """
**Teaching idea:**  
Use this view to explain how different compound classes appear in different RT windows and m/z regions.
"""
    )

# -----------------------
# Tab 3 – Compound Cards
# -----------------------
with tab_cards:
    st.subheader("Compound Cards")

    if filtered.empty:
        st.warning("No compounds match the current filters.")
    else:
        # Sort for consistent display
        card_df = filtered.sort_values(["sample", "rt_center"])

        for _, row in card_df.iterrows():
            with st.expander(
                f"{row['putative_compound']}  |  {row['compound_class']}  |  {row['sample']}"
            ):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.markdown(
                        f"""
**Sample:** {row['sample']}  
**Putative compound:** {row['putative_compound']}  
**Class:** {row['compound_class']}  
**Retention time (center):** {row['rt_center']:.2f} min  
**Main m/z:** {row['mz_main']}  
**Confidence (1–5):** {row['confidence_1_5']}  
**Reference:** {row['reference']}  
"""
                    )
                    st.markdown("**Notes:**")
                    st.write(row["notes"] if pd.notna(row["notes"]) else "—")
                with c2:
                    st.markdown(
                        """
*Future placeholders (v0.2+):*
- Structure preview (SMILES → 2D drawing)
- AI match score
- Similarity to known bioactive scaffolds
- Links to literature
"""
                    )

# -----------------------
# Tab 4 – Admin / Roadmap
# -----------------------
with tab_admin:
    st.subheader("Admin / Roadmap – Bloomz v0.1")

    st.markdown(
        """
This prototype is intentionally simple.

**Current capabilities (v0.1):**
- Load example or user-provided GC–MS peak/annotation tables.
- Filter compounds by sample, class, RT window, and confidence.
- Explore peaks in a retention time vs. m/z space.
- Display compounds as “cards” for teaching and manual review.
- Export the current filtered library slice.

**Planned next steps (v0.2+):**
- Add support for separate raw peak files + annotation files.
- Build internal TSU-specific natural product spectral library.
- Integrate semi-automated annotation using reference libraries.
- Add AI-assisted prioritization and similarity scoring.
- Integrate structure drawing and scaffold classification.
- Link compounds to PubChem / ChEMBL / natural product databases.

**How this supports TSU GC–MS and R1 goals:**
- Training students to think in terms of classes + RT + m/z windows.
- Creating a reusable, growing library specific to TSU projects.
- Reducing annotation time for recurring compounds.
- Providing pilot data for equipment/training grants and infrastructure proposals.
"""
    )

    if using_example:
        st.info(
            "Once integrated with TSU GC–MS data, this page can also track:\n"
            "- Number of samples processed\n"
            "- Library growth over time\n"
            "- Classes represented by project\n"
            "- Usage metrics for training and research."
        )
