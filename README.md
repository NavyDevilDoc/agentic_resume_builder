# Recruiter-Intelligence Resume Builder

A self-serve resume builder that grounds every rewrite decision in fresh, real-world recruiter intelligence rather than generic best-practice advice. The AI acts as an editor, not a ghostwriter — preserving your voice while making targeted improvements backed by what recruiters actually look for.

## What Makes This Different

Most resume tools apply the same generic advice to everyone. This tool builds a **living intelligence layer** by searching LinkedIn recruiter posts, Reddit hiring threads, and career industry content for your specific role and industry. Every edit suggestion is grounded in what recruiters are currently rewarding and penalizing.

**Key features:**

- **Tripod Intelligence Sourcing** — Pulls from LinkedIn (recruiter authority), Reddit (rejection signals), and broad career sources, with credibility assessment before anything is used
- **Voice Preservation** — Analyzes your writing style across 5 axes (formality, sentence length, structure, quantification habit, vocabulary register) and enforces it as a constraint during all rewrites
- **Three Escalation Levels** — Suggestions only (you decide), surgical edits (preserves your sentence skeletons), or full rewrite (with explicit opt-in)
- **Hallucination Verification** — Every rewrite is automatically checked against your original resume, flagging any metrics, companies, titles, or claims that weren't in the original
- **Job Description Matching** — Keyword overlap scoring against a specific JD (labeled honestly as "Job Description Match," not "ATS optimization")

## Architecture

Deterministic multi-stage pipeline with strict input/output contracts between stages. Each stage uses Pydantic v2 schemas — no shared mutable state.

```
Upload (PDF/DOCX) → Intelligence Fetch (Tavily) → Parse & Structure (Claude)
    → Style Extraction → Gap Analysis → Rewrite Engine → Keyword Scoring
    → Verification → DOCX Output
```

Built with: Python 3.11+, Streamlit, Anthropic Claude API, Tavily Search API, pdfminer.six, python-docx.

## Quick Start

### Prerequisites

- Python 3.11+
- [Anthropic API key](https://console.anthropic.com/)
- [Tavily API key](https://tavily.com/) (free Researcher tier works)

### Setup

```bash
git clone https://github.com/NavyDevilDoc/resume_builder.git
cd resume_builder
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### Run (Local)

```bash
streamlit run app.py
```

### Run (Docker)

```bash
docker build -t agentic-resume-builder .
docker run -p 8501:8501 --env-file .env agentic-resume-builder
```

Then open http://localhost:8501. The `--env-file .env` flag passes your API keys into the container without baking them into the image.

### Test

```bash
# Unit tests (no API calls)
python -m pytest -v

# Integration tests (uses live APIs — consumes credits)
python -m pytest -m integration -v
```

## Project Structure

```
resume_builder/
├── app.py                      # Streamlit entry point
├── models/schemas.py           # All Pydantic v2 schemas
├── modules/
│   ├── intelligence/           # Tavily search + Claude distillation + caching
│   ├── resume/                 # Parser, structurer, style, analyzer, rewriter, verifier
│   ├── scoring/                # JD keyword matching
│   └── output/                 # DOCX rendering
├── prompts/                    # All LLM prompts as constants
├── security/sanitizer.py       # Input validation and prompt injection defense
├── pages/                      # Streamlit multi-page UI
└── tests/                      # 136 unit + 16 integration tests
```

## Testing

The test suite is comprehensive and was built milestone-by-milestone alongside the code:

| Area | Unit Tests | Integration Tests |
|------|-----------|-------------------|
| Schemas & Sanitizer | 34 | — |
| Parser & Structurer | 15 | 3 |
| Intelligence Pipeline | 21 | 3 |
| Style & Gap Analysis | 16 | 4 |
| Rewrite Engine | 10 | 3 |
| Scoring & Rendering | 17 | 1 |
| Full Pipeline E2E | 3 | 1 |
| Verification | 11 | 1 |
| **Total** | **136** | **16** |

All external API calls in unit tests are mocked. Integration tests are gated behind `@pytest.mark.integration` and excluded from default runs.

## Security

- No server-side persistence of user data — everything lives in Streamlit session state
- No logging of PII — logs capture stage outcomes and error types only
- All user content enters LLM prompts as XML-delimited data with explicit ignore-instructions directives
- File uploads validated for type, size, and MIME before processing
- Text inputs stripped of HTML/script content before any LLM call

## Cost

Each full pipeline run uses approximately 6-8 Claude Sonnet API calls and 3-6 Tavily searches. Intelligence results are cached by role/industry/week to minimize repeat costs.

## License

MIT — see [LICENSE](LICENSE).
