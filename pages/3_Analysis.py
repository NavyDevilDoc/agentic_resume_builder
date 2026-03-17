"""Stage 3-5: Parse, Style, Gap Analysis, and Rewrite."""

import streamlit as st
from dotenv import load_dotenv

from modules.resume.analyzer import AnalysisError, analyze_gaps
from modules.resume.style import StyleExtractionError, extract_style

load_dotenv()

st.set_page_config(page_title="Resume Analysis", page_icon="🔬", layout="wide")
st.title("Step 3: Style & Gap Analysis")

# ── Guard: require Step 1 completion ───────────────────────────────────

if "user_input" not in st.session_state or "resume_schema" not in st.session_state:
    st.warning("Please complete Step 1 (Upload) first.")
    st.stop()

user_input = st.session_state["user_input"]
resume_schema = st.session_state["resume_schema"]
intelligence_brief = st.session_state.get("intelligence_brief")

# ── Style Extraction ──────────────────────────────────────────────────

if "style_profile" not in st.session_state:
    with st.spinner("Analyzing your writing style..."):
        try:
            style_profile = extract_style(
                user_input["resume_text"],
                user_input.get("voice_sample"),
            )
            st.session_state["style_profile"] = style_profile
        except StyleExtractionError as e:
            st.error(str(e))
            st.stop()

style_profile = st.session_state["style_profile"]

st.subheader("Your Writing Style Profile")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Formality", style_profile.formality_level.title())
with col2:
    st.metric("Sentence Length", style_profile.sentence_length.title())
with col3:
    st.metric("Structure", style_profile.structure_tendency.replace("_", " ").title())
with col4:
    st.metric("Quantification", style_profile.quantification_habit.title())

st.markdown(f"**Vocabulary Register:** {style_profile.vocabulary_register}")

st.divider()

# ── Gap Analysis ───────────────────────────────────────────────────────

if "gap_report" not in st.session_state:
    with st.spinner("Identifying resume gaps..."):
        try:
            gap_report = analyze_gaps(
                resume_schema,
                user_input.get("job_posting"),
                intelligence_brief,
            )
            st.session_state["gap_report"] = gap_report

            # Update pipeline status
            status = st.session_state.get("pipeline_status", {})
            status["style"] = "complete"
            status["gap_analysis"] = "complete"
            st.session_state["pipeline_status"] = status
        except AnalysisError as e:
            st.error(str(e))
            st.stop()

gap_report = st.session_state["gap_report"]

st.subheader("Gap Analysis")

if not gap_report.jd_provided:
    st.info(
        "No job description was provided. Gaps are based on recruiter "
        "intelligence and general best practices only."
    )

if not gap_report.gaps:
    st.success("No significant gaps identified. Your resume looks strong!")
else:
    # Summary counts
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    for gap in gap_report.gaps:
        severity_counts[gap.severity] += 1

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("High Priority", severity_counts["high"])
    with col2:
        st.metric("Medium Priority", severity_counts["medium"])
    with col3:
        st.metric("Low Priority", severity_counts["low"])

    st.divider()

    # Detailed gaps by severity
    severity_order = ["high", "medium", "low"]
    severity_colors = {"high": "🔴", "medium": "🟡", "low": "🟢"}

    for severity in severity_order:
        severity_gaps = [g for g in gap_report.gaps if g.severity == severity]
        if not severity_gaps:
            continue

        for gap in severity_gaps:
            with st.expander(
                f"{severity_colors[severity]} [{severity.upper()}] "
                f"{gap.category.replace('_', ' ').title()}: {gap.description[:80]}"
            ):
                st.markdown(f"**Category:** {gap.category.replace('_', ' ').title()}")
                st.markdown(f"**Issue:** {gap.description}")
                st.markdown(f"**Suggested Action:** {gap.suggested_action}")

st.markdown("---")
st.info("Proceed to **Step 4: Output** when ready.")
