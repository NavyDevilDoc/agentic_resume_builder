"""Streamlit entry point and page routing."""

import streamlit as st
from dotenv import load_dotenv
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()

REQUIRED_ENV_VARS = ["ANTHROPIC_API_KEY"]


def validate_env() -> None:
    """Fail loudly if required environment variables are missing."""
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        st.error(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Please set them in your .env file."
        )
        st.stop()


def _render_pipeline_status() -> None:
    """Show a subtle status indicator for completed pipeline stages."""
    status = st.session_state.get("pipeline_status", {})
    if not status:
        return

    stage_labels = {
        "input_collection": "Upload",
        "parse": "Parse",
        "intelligence": "Intelligence",
        "style": "Style",
        "gap_analysis": "Gap Analysis",
        "rewrite": "Rewrite",
    }

    icons = {"complete": "✅", "degraded": "⚠️"}

    cols = st.columns(len(stage_labels))
    for i, (key, label) in enumerate(stage_labels.items()):
        with cols[i]:
            state = status.get(key)
            if state:
                st.caption(f"{icons.get(state, '⬜')} {label}")
            else:
                st.caption(f"⬜ {label}")


def main() -> None:
    st.set_page_config(
        page_title="Resume Builder — Recruiter Intelligence",
        page_icon="📄",
        layout="wide",
    )
    validate_env()

    st.title("Recruiter-Intelligence Resume Builder")
    st.markdown(
        "Upload your resume, optionally paste a job posting, and get "
        "recruiter-grounded rewrite suggestions that preserve your voice."
    )

    # Initialize session state for pipeline status tracking
    if "pipeline_status" not in st.session_state:
        st.session_state.pipeline_status = {}

    _render_pipeline_status()

    st.divider()

    st.markdown(
        """
        ### How it works

        1. **Upload** — Upload your resume (PDF or DOCX) and optionally paste a job description
        2. **Intelligence** — We fetch current recruiter insights for your target role and industry
        3. **Analysis** — Your writing style is profiled and gaps are identified against the JD
        4. **Output** — Choose a rewrite level, review changes side-by-side, and download your revised resume

        Use the sidebar to navigate between steps.
        """
    )


if __name__ == "__main__":
    main()
