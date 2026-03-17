"""Stage 1: Input Collection — Resume upload + job posting + role/industry."""

import logging

import requests
import streamlit as st
from dotenv import load_dotenv

from modules.resume.parser import ParseError, parse_resume
from modules.resume.structurer import StructuringError, structure_resume
from security.sanitizer import SanitizationError, sanitize_text, validate_file_upload

load_dotenv()
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Upload Resume", page_icon="📄", layout="wide")
st.title("Step 1: Upload Your Resume")

# ── Role & Industry selectors ──────────────────────────────────────────

ROLE_CATEGORIES = [
    "AI/ML Engineer",
    "Data Scientist",
    "Software Engineer",
    "DevOps / MLOps Engineer",
    "Systems Engineer",
    "Mechanical Engineer",
    "Product Manager",
    "Other",
]

INDUSTRIES = [
    "Defense / Government",
    "Technology",
    "Finance",
    "Healthcare",
    "Energy",
    "Consulting",
    "Aerospace",
    "Other",
]

col1, col2 = st.columns(2)
with col1:
    role_category = st.selectbox("Role Category", ROLE_CATEGORIES)
with col2:
    industry = st.selectbox("Industry", INDUSTRIES)

# ── Resume upload ──────────────────────────────────────────────────────

uploaded_file = st.file_uploader(
    "Upload your resume (PDF or DOCX, max 5 MB)",
    type=["pdf", "docx"],
)

# ── Job posting (optional) ─────────────────────────────────────────────

st.subheader("Job Posting (optional)")
jd_method = st.radio(
    "How would you like to provide the job posting?",
    options=["Paste text", "Paste a URL"],
    horizontal=True,
    label_visibility="collapsed",
)

job_posting_raw = ""
job_posting_url = ""

if jd_method == "Paste text":
    job_posting_raw = st.text_area(
        "Paste the job posting",
        height=200,
        placeholder="Paste the full job description here...",
    )
elif jd_method == "Paste a URL":
    job_posting_url = st.text_input(
        "Job posting URL",
        placeholder="https://example.com/jobs/12345",
    )

# ── Voice sample (optional) ────────────────────────────────────────────

st.subheader("Writing Sample (optional)")
voice_method = st.radio(
    "How would you like to provide a writing sample?",
    options=["Paste text", "Upload a file"],
    horizontal=True,
    label_visibility="collapsed",
)

voice_sample_raw = ""
voice_file = None

if voice_method == "Paste text":
    voice_sample_raw = st.text_area(
        "Paste a writing sample to preserve your voice",
        height=100,
        placeholder="Any text you've written — email, cover letter, blog post...",
    )
elif voice_method == "Upload a file":
    voice_file = st.file_uploader(
        "Upload a writing sample (PDF, DOCX, or TXT, max 5 MB)",
        type=["pdf", "docx", "txt"],
        key="voice_upload",
    )


# ── Helper: fetch JD from URL ─────────────────────────────────────────

def _fetch_jd_from_url(url: str) -> str:
    """Fetch job posting text from a URL."""
    try:
        resp = requests.get(url, timeout=15, headers={
            "User-Agent": "Mozilla/5.0 (compatible; ResumeBuilder/1.0)"
        })
        resp.raise_for_status()
    except requests.RequestException as e:
        raise SanitizationError(
            f"Could not fetch the URL: {e}. Try pasting the text directly."
        )

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove script/style elements
    for tag in soup(["script", "style", "nav", "header", "footer"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)

    if not text or len(text) < 50:
        raise SanitizationError(
            "Could not extract meaningful text from that URL. "
            "The page may require login. Try pasting the text directly."
        )

    return text


# ── Helper: extract voice sample from file ─────────────────────────────

def _extract_voice_text(uploaded) -> str:
    """Extract text from an uploaded voice sample file."""
    name = uploaded.name.lower()
    file_bytes = uploaded.getvalue()

    if name.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="replace")
    elif name.endswith(".docx"):
        from modules.resume.parser import parse_docx
        return parse_docx(file_bytes)
    elif name.endswith(".pdf"):
        from modules.resume.parser import parse_pdf
        return parse_pdf(file_bytes)
    else:
        raise SanitizationError(f"Unsupported voice sample format: {name}")


# ── Process button ─────────────────────────────────────────────────────

if st.button("Parse Resume", type="primary", disabled=uploaded_file is None):
    # Validate file
    try:
        validate_file_upload(
            uploaded_file.name,
            uploaded_file.size,
            uploaded_file.type,
        )
    except SanitizationError as e:
        st.error(str(e))
        st.stop()

    # Resolve job posting
    job_posting = None
    if jd_method == "Paste a URL" and job_posting_url.strip():
        with st.spinner("Fetching job posting from URL..."):
            try:
                fetched_text = _fetch_jd_from_url(job_posting_url.strip())
                job_posting = sanitize_text(fetched_text)
            except SanitizationError as e:
                st.error(f"Job posting: {e}")
                st.stop()
    elif jd_method == "Paste text" and job_posting_raw.strip():
        try:
            job_posting = sanitize_text(job_posting_raw)
        except SanitizationError as e:
            st.error(f"Job posting: {e}")
            st.stop()

    # Resolve voice sample
    voice_sample = None
    if voice_method == "Upload a file" and voice_file is not None:
        with st.spinner("Extracting text from writing sample..."):
            try:
                extracted = _extract_voice_text(voice_file)
                voice_sample = sanitize_text(extracted)
            except (SanitizationError, ParseError) as e:
                st.error(f"Voice sample: {e}")
                st.stop()
    elif voice_method == "Paste text" and voice_sample_raw.strip():
        try:
            voice_sample = sanitize_text(voice_sample_raw)
        except SanitizationError as e:
            st.error(f"Voice sample: {e}")
            st.stop()

    # Parse resume file
    with st.spinner("Extracting text from resume..."):
        try:
            file_bytes = uploaded_file.getvalue()
            resume_text = parse_resume(uploaded_file.name, file_bytes)
        except ParseError as e:
            st.error(str(e))
            st.stop()

    st.success("Resume text extracted successfully.")

    # Structure resume via Claude
    with st.spinner("Analyzing resume structure..."):
        try:
            resume_schema = structure_resume(resume_text)
        except StructuringError as e:
            st.error(str(e))
            st.stop()

    # Store everything in session state for downstream stages
    st.session_state["user_input"] = {
        "resume_text": resume_text,
        "job_posting": job_posting,
        "role_category": role_category,
        "industry": industry,
        "voice_sample": voice_sample,
    }
    st.session_state["resume_schema"] = resume_schema
    st.session_state["pipeline_status"] = {"input_collection": "complete", "parse": "complete"}

    st.success("Resume parsed and structured. Proceed to the Intelligence step.")

    # Preview
    with st.expander("Preview: Extracted Text"):
        st.text(resume_text[:3000])

    with st.expander("Preview: Structured Resume"):
        st.json(resume_schema.model_dump())
