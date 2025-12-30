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
    rt_ref_tolerance: float = 0.30  # minutes (only if RT reference is provided)
    rt_heavy_early_strength: float = 0.25  # heuristic penalty weight (0..0.5-ish)
    expected_rt_a: float = 3.0  # heuristic expected RT = a*ln(mass)+b
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

DB_NAME_COLS = ["name", "compound_name", "Name", "Compound"]
DB_MASS_COLS = ["exact_mass", "monoisotopic_mass", "mass", "Exact Mass", "MonoisotopicMass"]
DB_CLASS_COLS = ["class", "superclass", "chemical_class", "Class"]

RTREF_NAME_COLS = ["name", "compound_name", "Name", "Compound"]
RTREF_RT_COLS = ["expected_rt", "rt", "RT", "Retention Time", "Expected RT"]


def _pick_col(df: pd.DataFrame, candidates: Iterable[str]) -> Optional[str]:
    lookup = {c.lower(): c for c in df.columns}
    for c in candidates:
        if c.lower() in lookup:
            return lookup[c.lower()]
    return None


# -------------------------
# Similarity (RapidFuzz optional)
# -------------------------
def name_similarity(a: str, b: str) -> float:
    a = (a or "").strip().lower()
    b = (b or "").strip().lower()
    if not a or not b:
        return 0.0
    try:
        from rapidfuzz.fuzz import token_set_ratio  # type: ignore

        return float(token_set_ratio(a, b)) / 100.0
    except Exception:
        return difflib.SequenceMatcher(None, a, b).ratio()


# -------------------------
# Data loading
# -------------------------
def load_peaks_from_instrument_csv(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(file_bytes))
    rt_col = _pick_col(df, RT_COLS)
    mz_col = _pick_col(df, MZ_COLS)
    if not rt_col or not mz_col:
        raise ValueError(f"Instrument CSV must include RT and m/z columns. Found: {list(df.columns)}")

    int_col = _pick_col(df, INT_COLS)

    peaks = pd.DataFrame(
        {
            "rt": pd.to_numeric(df[rt_col], errors="coerce"),
            "mz": pd.to_numeric(df[mz_col], errors="coerce"),
            "intensity": pd.to_numeric(df[int_col], errors="coerce") if int_col else 1.0,
        }
    ).dropna(subset=["rt", "mz"]).reset_index(drop=True)

    peaks.index.name = "peak_id"
    peaks = peaks.reset_index()
    return peaks


def normalize_blum_db(df: pd.DataFrame) -> pd.DataFrame:
    name_col = _pick_col(df, DB_NAME_COLS)
    mass_col = _pick_col(df, DB_MASS_COLS)
    if not name_col or not mass_col:
        raise ValueError(f"BLUM DB must include name + exact mass columns. Found: {list(df.columns)}")
    class_col = _pick_col(df, DB_CLASS_COLS)

    out = pd.DataFrame(
        {
            "blum_name": df[name_col].astype(str),
            "blum_exact_mass": pd.to_numeric(df[mass_col], errors="coerce"),
            "blum_class": df[class_col].astype(str) if class_col else "",
        }
    ).dropna(subset=["blum_exact_mass"]).reset_index(drop=True)
    return out


def load_blum_db(uploaded: Optional[bytes]) -> pd.DataFrame:
    if uploaded:
        return normalize_blum_db(pd.read_csv(io.BytesIO(uploaded)))

    if os.path.exists("data/blum_db.csv"):
        return normalize_blum_db(pd.read_csv("data/blum_db.csv"))

    raise FileNotFoundError("No BLUM DB found. Upload one or place it at data/blum_db.csv")


def normalize_rt_reference(df: pd.DataFrame) -> pd.DataFrame:
    name_col = _pick_col(df, RTREF_NAME_COLS)
    rt_col = _pick_col(df, RTREF_RT_COLS)
    if not name_col or not rt_col:
        raise ValueError(f"RT Reference must include name + expected_rt. Found: {list(df.columns)}")

    out = pd.DataFrame(
        {
            "rt_ref_name": df[name_col].astype(str),
            "rt_ref_expected_rt": pd.to_numeric(df[rt_col], errors="coerce"),
        }
    ).dropna(subset=["rt_ref_expected_rt"]).reset_index(drop=True)
    return out


def load_rt_reference(uploaded: Optional[bytes]) -> Optional[pd.DataFrame]:
    if uploaded:
        return normalize_rt_reference(pd.read_csv(io.BytesIO(uploaded)))
    if os.path.exists("data/blum_rt_ref.csv"):
        return normalize_rt_reference(pd.read_csv("data/blum_rt_ref.csv"))
    return None


# -------------------------
# Plausibility rules (editable)
# -------------------------
DEFAULT_SPECIES_RULES: Dict[str, Dict[str, Any]] = {
    "Nigella sativa": {
        "plausible_class_keywords": ["quinone", "thymo", "terpene", "phenolic", "alkaloid"],
        "notes": "Boost expected natural-product-like classes for this species.",
    },
    "Artemisia sieberi": {
        "plausible_class_keywords": ["terpene", "sesquiterpene", "monoterpene", "flavonoid", "phenolic"],
        "notes": "Often terpene-rich; deprioritize unrelated industrial-like chemicals.",
    },
    "Boswellia sacra": {
        "plausible_class_keywords": ["triterpene", "boswellic", "terpene", "resin", "phenolic"],
        "notes": "Resin signatures; boost triterpene/resin classes when available.",
    },
}


def plausibility_score(species: str, blum_class: str, keyword_csv: str) -> float:
    cls = (blum_class or "").lower()
    keywords = [k.strip().lower() for k in (keyword_csv or "").split(",") if k.strip()]
    if not keywords:
        return 0.5
    return 1.0 if any(k in cls for k in keywords) else 0.25


# -------------------------
# Scoring model
# -------------------------
def mass_term(sample_mz: float, ref_mz: float, tol: float) -> float:
    err = abs(sample_mz - ref_mz)
    if err > tol:
        return 0.0
    return math.exp(-(err / max(tol, 1e-12)))


def expected_rt_from_mass(mass: float, a: float, b: float) -> float:
    return a * math.log(max(mass, 1e-9)) + b


def rt_penalty(
    peak_rt: float,
    candidate_mass: float,
    rt_ref_expected: Optional[float],
    params: AgentParams,
) -> Tuple[float, float]:
    if rt_ref_expected is not None and not math.isnan(rt_ref_expected):
        delta = float(peak_rt - rt_ref_expected)
        over = max(0.0, abs(delta) - params.rt_ref_tolerance)
        penalty = min(0.5, over * 0.20)
        return penalty, delta

    expected = expected_rt_from_mass(candidate_mass, params.expected_rt_a, params.expected_rt_b)
    delta = float(peak_rt - expected)
    penalty = 0.0
    if delta < 0:
        penalty = min(0.5, abs(delta) * params.rt_heavy_early_strength)
    return penalty, delta


def normalize_manual_lib_score(raw: Any) -> float:
    try:
        x = float(raw)
    except Exception:
        return 0.5
    if x <= 1.0:
        return max(0.0, min(1.0, x))
    if x <= 100.0:
        return max(0.0, min(1.0, x / 100.0))
    return max(0.0, min(1.0, x / 1000.0))


def pick_best_blum_candidate(
    peak_mz: float,
    manual_hit_name: str,
    blum: pd.DataFrame,
    species: str,
    plaus_keywords_csv: str,
    params: AgentParams,
) -> Tuple[Optional[pd.Series], pd.DataFrame]:
    lo = peak_mz - params.mass_tolerance
    hi = peak_mz + params.mass_tolerance
    candidates = blum[(blum["blum_exact_mass"] >= lo) & (blum["blum_exact_mass"] <= hi)].copy()

    if candidates.empty:
        return None, candidates

    candidates["mass_term"] = candidates["blum_exact_mass"].apply(
        lambda m: mass_term(peak_mz, float(m), params.mass_tolerance)
    )
    candidates["name_sim"] = candidates["blum_name"].apply(lambda n: name_similarity(manual_hit_name, str(n)))
    candidates["plaus"] = candidates["blum_class"].apply(
        lambda c: plausibility_score(species, str(c), plaus_keywords_csv)
    )
    candidates["internal_rank"] = 0.55 * candidates["mass_term"] + 0.35 * candidates["name_sim"] + 0.10 * candidates["plaus"]
    candidates = candidates.sort_values("internal_rank", ascending=False)

    topk = candidates.head(params.top_k_blum).reset_index(drop=True)
    best = candidates.iloc[0] if len(candidates) else None
    return best, topk


def agent_score_row(
    row: pd.Series,
    blum: pd.DataFrame,
    rt_ref: Optional[pd.DataFrame],
    species: str,
    plaus_keywords_csv: str,
    params: AgentParams,
) -> Dict[str, Any]:
    sample_mz = float(row["mz"])
    peak_rt = float(row["rt"])

    manual_hit_name = str(row.get("manual_hit_name", "") or "")
    manual_hit_mz = row.get("manual_hit_mz", None)
    manual_score_raw = row.get("manual_lib_score", None)

    manual_mz_val: Optional[float] = None
    try:
        if manual_hit_mz is not None and str(manual_hit_mz).strip() != "":
            manual_mz_val = float(manual_hit_mz)
    except Exception:
        manual_mz_val = None

    manual_norm = normalize_manual_lib_score(manual_score_raw)

    mass_gate = False
    if manual_mz_val is not None:
        mass_gate = abs(sample_mz - manual_mz_val) <= params.mass_tolerance

    best_blum, topk = pick_best_blum_candidate(
        peak_mz=sample_mz,
        manual_hit_name=manual_hit_name,
        blum=blum,
        species=species,
        plaus_keywords_csv=plaus_keywords_csv,
        params=params,
    )

    cand_name = ""
    cand_mass = float("nan")
    cand_class = ""
    cand_mass_term = 0.0
    cand_name_sim = 0.0
    cand_plaus = 0.5
    cand_mass_error = float("nan")

    rt_ref_expected: Optional[float] = None

    if best_blum is not None:
        cand_name = str(best_blum["blum_name"])
        cand_mass = float(best_blum["blum_exact_mass"])
        cand_class = str(best_blum.get("blum_class", "") or "")
        cand_mass_term = float(best_blum.get("mass_term", 0.0))
        cand_name_sim = float(best_blum.get("name_sim", 0.0))
        cand_plaus = float(best_blum.get("plaus", 0.5))
        cand_mass_error = float(cand_mass - sample_mz)

        if rt_ref is not None and not rt_ref.empty:
            tmp = rt_ref.copy()
            tmp["name_sim"] = tmp["rt_ref_name"].apply(lambda n: name_similarity(cand_name, str(n)))
            best_rt = tmp.sort_values("name_sim", ascending=False).head(1)
            if not best_rt.empty and float(best_rt.iloc[0]["name_sim"]) >= 0.70:
                rt_ref_expected = float(best_rt.iloc[0]["rt_ref_expected_rt"])

    penalty, rt_delta = rt_penalty(
        peak_rt=peak_rt,
        candidate_mass=cand_mass if not math.isnan(cand_mass) else sample_mz,
        rt_ref_expected=rt_ref_expected,
        params=params,
    )

    manual_mass_term = mass_term(sample_mz, manual_mz_val, params.mass_tolerance) if manual_mz_val is not None else 0.0

    conf = (
        params.w_manual_lib * manual_norm
        + params.w_mass * max(cand_mass_term, manual_mass_term)
        + params.w_name * cand_name_sim
        + params.w_plaus * cand_plaus
        - penalty
    )
    conf = max(0.0, min(1.0, conf))

    if conf >= 0.90:
        grade = "High Confidence"
    elif conf >= 0.70:
        grade = "Probable"
    elif conf >= 0.50:
        grade = "Possible"
    else:
        grade = "Flagged"

    return {
        "mass_gate": "✅" if mass_gate else ("⚠️" if manual_mz_val is None else "❌"),
        "manual_score_norm": round(manual_norm, 3),
        "best_blum_name": cand_name,
        "best_blum_exact_mass": None if math.isnan(cand_mass) else round(cand_mass, 6),
        "best_blum_class": cand_class,
        "blum_mass_error": None if math.isnan(cand_mass_error) else round(cand_mass_error, 6),
        "name_similarity": round(cand_name_sim, 3),
        "plausibility": round(cand_plaus, 3),
        "rt_ref_expected_rt": None if rt_ref_expected is None else round(rt_ref_expected, 3),
        "rt_delta": round(rt_delta, 3),
        "rt_penalty": round(penalty, 3),
        "confidence": round(conf, 3),
        "agent_grade": grade,
        "_topk": topk,
    }


# -------------------------
# Certificate PDF generator
# -------------------------
def wrap_text(text: str, max_chars: int) -> Iterable[str]:
    words = (text or "").split()
    cur: list[str] = []
    for w in words:
        if sum(len(x) for x in cur) + len(cur) + len(w) > max_chars:
            yield " ".join(cur)
            cur = [w]
        else:
            cur.append(w)
    if cur:
        yield " ".join(cur)


def build_certificate_pdf(
    sample_meta: Dict[str, str],
    scored: pd.DataFrame,
    trace_note: str,
) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    w, h = LETTER

    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, h - 50, "BLOOMZ CORE — Certificate of Analysis (Draft)")

    c.setFont("Helvetica", 10)
    y = h - 80
    for k in ["species", "lab_source", "sample_id", "method_notes", "analyst"]:
        v = sample_meta.get(k, "").strip()
        if v:
            c.drawString(40, y, f"{k.replace('_', ' ').title()}: {v}")
            y -= 14

    y -= 6
    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "High-Confidence Identifications")
    y -= 16

    cols = ["peak_id", "rt", "mz", "manual_hit_name", "best_blum_name", "best_blum_class", "confidence", "agent_grade"]
    table = scored.loc[scored["agent_grade"].isin(["High Confidence", "Probable"]), cols].copy()

    if table.empty:
        c.setFont("Helvetica", 10)
        c.drawString(40, y, "No High-Confidence / Probable hits in this run.")
        y -= 14
    else:
        c.setFont("Helvetica", 8)
        c.drawString(40, y, " | ".join(cols))
        y -= 12
        c.line(40, y + 6, w - 40, y + 6)
        for _, r in table.iterrows():
            line = " | ".join(
                [
                    str(r["peak_id"]),
                    f'{float(r["rt"]):.3f}',
                    f'{float(r["mz"]):.5f}',
                    str(r.get("manual_hit_name", ""))[:24],
                    str(r.get("best_blum_name", ""))[:24],
                    str(r.get("best_blum_class", ""))[:18],
                    str(r.get("confidence", "")),
                    str(r.get("agent_grade", ""))[:14],
                ]
            )
            c.drawString(40, y, line)
            y -= 12
            if y < 110:
                c.showPage()
                y = h - 60

    y -= 10
    c.setFont("Helvetica-Bold", 10)
    c.drawString(40, y, "Traceability Note")
    y -= 14
    c.setFont("Helvetica", 9)
    for part in wrap_text(trace_note, max_chars=100):
        c.drawString(40, y, part)
        y -= 12
        if y < 70:
            c.showPage()
            y = h - 60

    c.showPage()
    c.save()
    return buf.getvalue()


# -------------------------
# UI
# -------------------------
def main() -> None:
    st.set_page_config(page_title="BLOOMZ CORE", page_icon="🌿", layout="wide")
    st.title("🌿 BLOOMZ CORE — Spectral Intelligence (Prototype)")
    st.caption("Public-repo safe prototype: vendor-neutral inputs, manual library verification, weighted agent scoring.")

    with st.sidebar:
        st.header("Agent Settings")
        params = AgentParams(
            mass_tolerance=float(
                st.number_input("Mass tolerance (± m/z)", value=0.005, min_value=0.000001, format="%.6f")
            ),
            top_k_blum=int(st.slider("Top BLUM suggestions", 1, 10, 5)),
            rt_ref_tolerance=float(st.number_input("RT tolerance (min)", value=0.30, min_value=0.0, format="%.2f")),
            rt_heavy_early_strength=float(
                st.number_input("Heavy-too-early penalty strength", value=0.25, min_value=0.0, max_value=1.0, format="%.2f")
            ),
            expected_rt_a=float(st.number_input("Expected RT a (heuristic)", value=3.0, format="%.2f")),
            expected_rt_b=float(st.number_input("Expected RT b (heuristic)", value=-5.0, format="%.2f")),
            w_mass=float(st.number_input("Weight: mass", value=0.40, min_value=0.0, max_value=1.0, format="%.2f")),
            w_name=float(
                st.number_input("Weight: name similarity", value=0.25, min_value=0.0, max_value=1.0, format="%.2f")
            ),
            w_manual_lib=float(
                st.number_input("Weight: manual library score", value=0.25, min_value=0.0, max_value=1.0, format="%.2f")
            ),
            w_plaus=float(
                st.number_input("Weight: plausibility", value=0.10, min_value=0.0, max_value=1.0, format="%.2f")
            ),
        )

        st.divider()
        st.subheader("Reference Data (Prototype)")
        blum_upload = st.file_uploader("Upload BLUM DB CSV (optional)", type=["csv"])
        rt_ref_upload = st.file_uploader("Upload RT Reference CSV (optional)", type=["csv"])

    tab_upload, tab_process, tab_report = st.tabs(["🌿 Upload", "🔬 Process", "📄 Report"])

    with tab_upload:
        st.subheader("Step A — Data Ingestion")
        st.caption("Upload an instrument export CSV (vendor-neutral).")

        peaks_file = st.file_uploader("Instrument Export CSV", type=["csv"], key="peaks_uploader")

        col1, col2 = st.columns(2)
        with col1:
            species = st.selectbox("Species Context Tag", options=list(DEFAULT_SPECIES_RULES.keys()), index=0)
        with col2:
            lab_source = st.selectbox("Lab Context Tag", options=["Lab A", "Lab B", "Lab C", "Other"], index=0)

        sample_id = st.text_input("Sample ID (optional)", value="")
        analyst = st.text_input("Analyst (optional)", value="")
        method_notes = st.text_area("Method notes (optional)", value="", height=80)

        rules = DEFAULT_SPECIES_RULES.get(species, {})
        plaus_keywords = st.text_input(
            "Plausible class keywords (comma-separated)",
            value=", ".join(rules.get("plausible_class_keywords", [])),
            help="Used to boost chemically plausible classes for the chosen species.",
        )
        st.caption(rules.get("notes", ""))

        if peaks_file:
            peaks = load_peaks_from_instrument_csv(peaks_file.read())
            st.session_state["peaks"] = peaks
            st.session_state["meta"] = {
                "species": species,
                "lab_source": lab_source,
                "sample_id": sample_id,
                "analyst": analyst,
                "method_notes": method_notes,
                "plaus_keywords": plaus_keywords,
            }
            st.success(f"Loaded {len(peaks):,} peaks.")
            st.dataframe(peaks.head(50), use_container_width=True)
        else:
            st.info("Upload a CSV to begin.")

    with tab_process:
        st.subheader("Step B — Agentic Analysis")
        st.caption("Manual Library Verification: paste hit name / reference m/z / match score per peak.")

        peaks = st.session_state.get("peaks")
        meta = st.session_state.get("meta", {})
        if peaks is None:
            st.warning("Go to Upload tab and upload your instrument CSV first.")
        else:
            blum = load_blum_db(blum_upload.read() if blum_upload else None)
            rt_ref = load_rt_reference(rt_ref_upload.read() if rt_ref_upload else None)

            st.caption(f"BLUM DB loaded: {len(blum):,} entries")
            if rt_ref is not None:
                st.caption(f"RT Reference loaded: {len(rt_ref):,} entries")

            workspace = peaks.copy()
            for col in ["manual_hit_name", "manual_hit_mz", "manual_lib_score"]:
                if col not in workspace.columns:
                    workspace[col] = ""

            edited = st.data_editor(
                workspace,
                use_container_width=True,
                num_rows="fixed",
                column_config={
                    "manual_hit_name": st.column_config.TextColumn("Manual Hit Name"),
                    "manual_hit_mz": st.column_config.TextColumn("Reference m/z"),
                    "manual_lib_score": st.column_config.TextColumn("Match Score"),
                },
            )

            if st.button("Run BLOOMZ CORE Scoring", type="primary"):
                scored_rows = []
                topk_map: Dict[int, pd.DataFrame] = {}
                for _, r in edited.iterrows():
                    out = agent_score_row(
                        row=r,
                        blum=blum,
                        rt_ref=rt_ref,
                        species=str(meta.get("species", "")),
                        plaus_keywords_csv=str(meta.get("plaus_keywords", "")),
                        params=params,
                    )
                    topk_map[int(r["peak_id"])] = out.pop("_topk")
                    scored_rows.append({**dict(r), **out})

                scored = pd.DataFrame(scored_rows)
                st.session_state["scored"] = scored
                st.session_state["topk_map"] = topk_map

            scored = st.session_state.get("scored")
            if scored is not None:
                st.success("Scoring complete.")

                show_cols = [
                    "peak_id",
                    "rt",
                    "mz",
                    "manual_hit_name",
                    "manual_hit_mz",
                    "mass_gate",
                    "manual_score_norm",
                    "best_blum_name",
                    "best_blum_exact_mass",
                    "blum_mass_error",
                    "best_blum_class",
                    "plausibility",
                    "rt_ref_expected_rt",
                    "rt_delta",
                    "rt_penalty",
                    "confidence",
                    "agent_grade",
                ]
                show = scored[show_cols].copy()

                grade_order = {"High Confidence": 0, "Probable": 1, "Possible": 2, "Flagged": 3}
                show["_grade_rank"] = show["agent_grade"].map(lambda g: grade_order.get(g, 9))
                show = show.sort_values(by=["_grade_rank", "confidence"], ascending=[True, False]).drop(columns=["_grade_rank"])

                st.dataframe(show, use_container_width=True)

                with st.expander("Inspect Top BLUM Suggestions (per peak)"):
                    pid = st.number_input(
                        "Peak ID",
                        min_value=int(show["peak_id"].min()),
                        max_value=int(show["peak_id"].max()),
                        value=int(show["peak_id"].min()),
                    )
                    topk = (st.session_state.get("topk_map") or {}).get(int(pid))
                    if topk is None or topk.empty:
                        st.info("No BLUM candidates found within tolerance for this peak.")
                    else:
                        st.dataframe(
                            topk[["blum_name", "blum_exact_mass", "blum_class", "mass_term", "name_sim", "plaus", "internal_rank"]],
                            use_container_width=True,
                        )

    with tab_report:
        st.subheader("Step C — Intelligence Export")
        scored = st.session_state.get("scored")
        meta = st.session_state.get("meta", {})
        if scored is None:
            st.info("Run scoring in the Process tab first.")
        else:
            csv_bytes = scored.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download Scored CSV", data=csv_bytes, file_name="bloomz_core_scored.csv", mime="text/csv")

            trace_note = (
                "This report was generated using the BLOOMZ Spectral Intelligence protocol: "
                "mass tolerance gate (±0.005 m/z), retention-time plausibility penalties, and "
                "molecular-class plausibility checks based on the declared species context. "
                "Manual library verification entries are recorded in the dataset."
            )

            cert_pdf = build_certificate_pdf(
                sample_meta={
                    "species": str(meta.get("species", "")),
                    "lab_source": str(meta.get("lab_source", "")),
                    "sample_id": str(meta.get("sample_id", "")),
                    "method_notes": str(meta.get("method_notes", "")),
                    "analyst": str(meta.get("analyst", "")),
                },
                scored=scored,
                trace_note=trace_note,
            )
            st.download_button(
                "⬇️ Download Certificate PDF (Draft)",
                data=cert_pdf,
                file_name="bloomz_certificate_draft.pdf",
                mime="application/pdf",
            )


if __name__ == "__main__":
    main()


# =========================
# file: requirements.txt
# =========================
# streamlit>=1.36
# pandas>=2.2
# reportlab>=4.0
# rapidfuzz>=3.9


# =========================
# file: .streamlit/config.toml
# =========================
# [theme]
# primaryColor = "#49735A"
# backgroundColor = "#F6F6F6"
# secondaryBackgroundColor = "#FFFFFF"
# textColor = "#222222"
# font = "sans serif"

