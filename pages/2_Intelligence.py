"""Stage 2: Intelligence Fetch — Show recruiter intelligence brief."""

import streamlit as st
from dotenv import load_dotenv

from modules.intelligence.distiller import distill_intelligence

load_dotenv()

st.set_page_config(page_title="Recruiter Intelligence", page_icon="🔍", layout="wide")
st.title("Step 2: Recruiter Intelligence")

# ── Guard: require Step 1 completion ───────────────────────────────────

if "user_input" not in st.session_state:
    st.warning("Please complete Step 1 (Upload) first.")
    st.stop()

user_input = st.session_state["user_input"]
role_category = user_input["role_category"]
industry = user_input["industry"]

st.markdown(
    f"Fetching current recruiter intelligence for **{role_category}** "
    f"roles in **{industry}**..."
)

# ── Fetch or retrieve cached intelligence ──────────────────────────────

if "intelligence_brief" not in st.session_state:
    with st.spinner("Searching recruiter sources and distilling insights..."):
        brief = distill_intelligence(role_category, industry)
        st.session_state["intelligence_brief"] = brief

        # Update pipeline status
        status = st.session_state.get("pipeline_status", {})
        status["intelligence"] = "complete" if brief else "degraded"
        st.session_state["pipeline_status"] = status

brief = st.session_state["intelligence_brief"]

# ── Display ────────────────────────────────────────────────────────────

if brief is None:
    st.warning(
        "We couldn't fetch recruiter intelligence right now. "
        "Your resume will be analyzed without it. You can still proceed."
    )
else:
    # Source legs indicator
    legs = brief.legs_populated
    leg_labels = {"linkedin": "LinkedIn", "reddit": "Reddit", "broad": "Broad Web"}
    cols = st.columns(3)
    for i, (key, label) in enumerate(leg_labels.items()):
        with cols[i]:
            if key in legs:
                st.success(f"{label}: Active")
            else:
                st.info(f"{label}: No data")

    st.divider()

    # What recruiters reward
    if brief.what_recruiters_reward:
        st.subheader("What Recruiters Reward")
        for point in brief.what_recruiters_reward:
            st.markdown(f"- {point}")

    # What recruiters skip
    if brief.what_recruiters_skip:
        st.subheader("What Recruiters Skip")
        for point in brief.what_recruiters_skip:
            st.markdown(f"- {point}")

    # Red flags
    if brief.red_flags:
        st.subheader("Red Flags")
        for point in brief.red_flags:
            st.markdown(f"- {point}")

    # Format preferences
    if brief.format_preferences:
        st.subheader("Format Preferences")
        for point in brief.format_preferences:
            st.markdown(f"- {point}")

    # ATS notes
    if brief.current_ats_notes:
        st.subheader("Current ATS Notes")
        for point in brief.current_ats_notes:
            st.markdown(f"- {point}")

    # Source credibility
    with st.expander("Source Credibility Notes"):
        st.write(brief.source_credibility_notes or "No credibility notes available.")

st.markdown("---")
st.info("Proceed to **Step 3: Analysis** when ready.")
