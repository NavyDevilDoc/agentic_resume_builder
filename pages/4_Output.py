"""Stage 6-7: Keyword scoring, rewrite, and final output with diff view."""

import streamlit as st
from dotenv import load_dotenv

from models.schemas import RevisedResumeSchema
from modules.resume.rewriter import RewriteError, rewrite_resume
from modules.resume.verifier import VerificationError, verify_rewrite
from modules.scoring.keyword_match import ScoringError, score_keywords
from modules.output.renderer import render_docx

load_dotenv()

st.set_page_config(page_title="Resume Output", page_icon="📄", layout="wide")
st.title("Step 4: Rewrite & Output")

# ── Guard: require previous steps ─────────────────────────────────────

required_keys = ["user_input", "resume_schema", "style_profile", "gap_report"]
missing = [k for k in required_keys if k not in st.session_state]
if missing:
    st.warning("Please complete the previous steps first.")
    st.stop()

user_input = st.session_state["user_input"]
resume_schema = st.session_state["resume_schema"]
style_profile = st.session_state["style_profile"]
gap_report = st.session_state["gap_report"]
intelligence_brief = st.session_state.get("intelligence_brief")

# ── Rewrite level selector ─────────────────────────────────────────────

st.subheader("Choose Rewrite Level")

level_descriptions = {
    "suggestions": "**Level 1 — Suggestions Only:** Inline comments proposing changes. You accept or reject each one.",
    "edit": "**Level 2 — Edit Mode:** Surgical modifications to existing sentences. Preserves your phrasing patterns.",
    "full_rewrite": "**Level 3 — Full Rewrite:** Sections rewritten from scratch. Requires explicit confirmation.",
}

level = st.radio(
    "Rewrite level",
    options=["suggestions", "edit", "full_rewrite"],
    format_func=lambda x: {"suggestions": "Level 1: Suggestions", "edit": "Level 2: Edit", "full_rewrite": "Level 3: Full Rewrite"}[x],
    index=0,
)

st.markdown(level_descriptions[level])

# Full rewrite confirmation
if level == "full_rewrite":
    confirmed = st.checkbox(
        "I understand this will rewrite sections from scratch. Proceed.",
        value=False,
    )
    if not confirmed:
        st.info("Please confirm to proceed with full rewrite.")
        st.stop()

# ── Run rewrite ────────────────────────────────────────────────────────

rewrite_key = f"rewrite_result_{level}"

button_labels = {
    "suggestions": "Generate Suggestions",
    "edit": "Generate Edit",
    "full_rewrite": "Generate Rewrite",
}

if st.button(button_labels[level], type="primary"):
    # Clear any previous result for this level
    st.session_state.pop(rewrite_key, None)

    with st.spinner(f"Running {level} rewrite..."):
        try:
            result = rewrite_resume(
                resume_schema,
                style_profile,
                gap_report,
                level=level,
                intelligence_brief=intelligence_brief,
                voice_sample=user_input.get("voice_sample"),
            )
            st.session_state[rewrite_key] = result
            st.session_state["pipeline_status"] = {
                **st.session_state.get("pipeline_status", {}),
                "rewrite": "complete",
            }
        except RewriteError as e:
            st.error(str(e))
            st.stop()

if rewrite_key not in st.session_state:
    st.info("Click 'Generate Rewrite' to see results.")
    st.stop()

result = st.session_state[rewrite_key]

st.divider()

# ── Display results ────────────────────────────────────────────────────

if level == "suggestions":
    # Level 1: Show suggestions
    st.subheader("Suggestions")

    for section in result.get("sections", []):
        with st.expander(f"**{section['section_name'].replace('_', ' ').title()}**"):
            for s in section.get("suggestions", []):
                priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(s.get("priority", ""), "⚪")
                st.markdown(f"{priority_icon} **Target:** \"{s.get('target', '')[:100]}...\"")
                st.markdown(f"   **Suggestion:** {s.get('suggestion', '')}")
                st.markdown("---")

    with st.expander("Change Log"):
        for change in result.get("change_log", []):
            st.markdown(f"- {change}")

else:
    # Levels 2 & 3: Show side-by-side diff
    assert isinstance(result, RevisedResumeSchema)

    st.subheader("Side-by-Side Comparison")

    col_orig, col_revised = st.columns(2)

    with col_orig:
        st.markdown("### Original")
        if resume_schema.summary:
            st.markdown(f"**Summary:** {resume_schema.summary}")
        for exp in resume_schema.experience:
            st.markdown(f"**{exp.raw_text}**")
            if exp.bullets:
                for b in exp.bullets:
                    st.markdown(f"- {b}")

    with col_revised:
        st.markdown("### Revised")
        if result.summary:
            st.markdown(f"**Summary:** {result.summary}")
        for exp in result.experience:
            st.markdown(f"**{exp.raw_text}**")
            if exp.bullets:
                for b in exp.bullets:
                    st.markdown(f"- {b}")

    # Change rationale
    with st.expander("Why We Made These Changes"):
        for change in result.change_log:
            st.markdown(f"- {change}")

    # ── Verification ───────────────────────────────────────────────────

    st.divider()
    st.subheader("Verification")

    verification_key = f"verification_{level}"
    if verification_key not in st.session_state:
        with st.spinner("Verifying changes against original resume..."):
            try:
                verification = verify_rewrite(resume_schema, result)
                st.session_state[verification_key] = verification
            except VerificationError as e:
                st.warning(f"Verification could not complete: {e}")
                st.session_state[verification_key] = None

    verification = st.session_state.get(verification_key)

    if verification is not None:
        if verification.verified_clean:
            st.success("All changes trace back to your original resume. No fabricated content detected.")
        else:
            warnings = [f for f in verification.flags if f.severity == "warning"]
            infos = [f for f in verification.flags if f.severity == "info"]

            if warnings:
                st.warning(
                    f"{len(warnings)} item(s) need your verification. "
                    "These changes include content not found in your original resume."
                )
            if infos:
                st.info(
                    f"{len(infos)} item(s) were noted as additions that are plausibly valid."
                )

            for flag in warnings:
                with st.expander(
                    f"⚠️ [{flag.category.replace('_', ' ').title()}] {flag.revised_text[:80]}..."
                ):
                    st.markdown(f"**Category:** {flag.category.replace('_', ' ').title()}")
                    st.markdown(f"**In revision:** {flag.revised_text}")
                    if flag.original_text:
                        st.markdown(f"**Closest original:** {flag.original_text}")
                    else:
                        st.markdown("**Closest original:** *(not found in original)*")
                    st.markdown(f"**Why flagged:** {flag.explanation}")

            for flag in infos:
                with st.expander(
                    f"ℹ️ [{flag.category.replace('_', ' ').title()}] {flag.revised_text[:80]}..."
                ):
                    st.markdown(f"**Category:** {flag.category.replace('_', ' ').title()}")
                    st.markdown(f"**In revision:** {flag.revised_text}")
                    if flag.original_text:
                        st.markdown(f"**Closest original:** {flag.original_text}")
                    st.markdown(f"**Why noted:** {flag.explanation}")

    # ── Keyword scoring ────────────────────────────────────────────────

    if user_input.get("job_posting"):
        st.divider()
        st.subheader("Job Description Match")

        if "keyword_report" not in st.session_state:
            with st.spinner("Scoring keyword match..."):
                try:
                    keyword_report = score_keywords(result, user_input["job_posting"])
                    st.session_state["keyword_report"] = keyword_report
                except ScoringError as e:
                    st.warning(f"Keyword scoring failed: {e}")
                    keyword_report = None

        keyword_report = st.session_state.get("keyword_report")

        if keyword_report:
            # Match percentage
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Match", f"{keyword_report.match_pct}%")
            with col2:
                st.metric("Present", len(keyword_report.present_terms))
            with col3:
                st.metric("Missing", len(keyword_report.missing_terms))

            col_present, col_missing = st.columns(2)
            with col_present:
                st.markdown("**Present Keywords:**")
                st.markdown(", ".join(keyword_report.present_terms) or "None")
            with col_missing:
                st.markdown("**Missing Keywords:**")
                st.markdown(", ".join(keyword_report.missing_terms) or "None")

    # ── Download ───────────────────────────────────────────────────────

    st.divider()
    st.subheader("Download")

    docx_bytes = render_docx(result)
    st.download_button(
        label="Download Revised Resume (DOCX)",
        data=docx_bytes,
        file_name="revised_resume.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
