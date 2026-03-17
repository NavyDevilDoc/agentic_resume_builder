# PROGRESS.md — Recruiter-Intelligence Resume Builder

Running development log. Updated after each milestone gate.

---

## Foundation — COMPLETE (2026-03-16)

### What was built
- **[models/schemas.py](models/schemas.py)** — All 10 Pydantic v2 schemas: `UserInput`, `StyleProfile`, `IntelligenceBrief`, `ResumeSection`, `ResumeSchema`, `GapItem`, `GapReport`, `KeywordReport`, `RevisedResumeSchema`
- **[security/sanitizer.py](security/sanitizer.py)** — File upload validation (MIME type, extension, size cap), text sanitization (HTML/script stripping, length cap), `wrap_user_content()` for prompt injection defense
- **[pyproject.toml](pyproject.toml)** — Pytest config with `@pytest.mark.integration` marker, integration tests excluded from default runs
- **[requirements.txt](requirements.txt)** — Pinned dependencies: `streamlit`, `anthropic`, `pydantic`, `python-dotenv`, `pdfminer.six`, `python-docx`, `tavily-python`, `pytest`, `pytest-mock`
- **[.env.example](.env.example)** / **[.gitignore](.gitignore)** — Secrets management setup

### Tests (43 passing)
- `test_schemas.py` — 23 tests: valid/invalid data for all models, literal enforcement, default values, required field enforcement
- `test_sanitizer.py` — 11 tests: file validation (extension, size, empty, MIME), text sanitization (HTML, script, style tags, whitespace, truncation), content wrapping
- 9 tests added to fixture infrastructure

### Decisions
- Tavily Researcher plan (free tier, 1,000 credits/month) — all live API calls gated behind `@pytest.mark.integration`
- Test fixtures: user's real DOCX resume + generated sample PDF + Northrop Grumman Sr. Principal AI Systems Engineer JD

---

## M1: Input + Parse — COMPLETE (2026-03-16)

### What was built
- **[modules/resume/parser.py](modules/resume/parser.py)** — `parse_pdf()` via `pdfminer.six`, `parse_docx()` via `python-docx`, `parse_resume()` router by file extension. Extracts raw text only, no layout reconstruction. Raises `ParseError` on failure with user-friendly messages.
- **[modules/resume/structurer.py](modules/resume/structurer.py)** — `structure_resume()` sends raw text to Claude (Sonnet), parses JSON response into validated `ResumeSchema`. Handles markdown fence stripping, JSON parse failures, schema validation errors, and API errors.
- **[prompts/structuring.py](prompts/structuring.py)** — System + user prompts for resume structuring and style extraction. XML-delimited user content. Explicit instruction to extract only, never infer or fabricate.
- **[pages/1_Upload.py](pages/1_Upload.py)** — Streamlit page: file upload (PDF/DOCX), job posting text area, role/industry dropdowns, optional voice sample. Runs sanitizer → parser → structurer pipeline. Stores results in `st.session_state`.

### Tests (58 passing, cumulative)
- `test_parser.py` — 9 tests: DOCX happy path (real resume), PDF happy path (fixture), empty DOCX, invalid bytes, routing by extension, case insensitivity
- `test_structurer.py` — 6 tests: valid response, markdown fence stripping, invalid JSON, bad schema, API error, empty resume (all mocked Claude)

### Test gate
All 58 tests green. No skips, no warnings.

---

## M2: Intelligence Fetch — COMPLETE (2026-03-16)

### What was built
- **[modules/intelligence/cache.py](modules/intelligence/cache.py)** — JSON file cache keyed by `(role_category, industry, iso_week)` via SHA-256 hash. 7-day TTL with automatic expiry cleanup. Case-insensitive keys. `store_brief()`, `get_cached_brief()`, `clear_cache()`. Designed for drop-in Redis upgrade in v2.
- **[modules/intelligence/fetcher.py](modules/intelligence/fetcher.py)** — Tavily tripod sourcing: LinkedIn (recruiter authority), Reddit (failure signals from r/resumes, r/recruitinghell, r/cscareerquestions), Broad (career coaching, blogs, minus LinkedIn/Reddit). Returns `SearchResults` dataclass. Graceful degradation on missing API key or search failures.
- **[modules/intelligence/distiller.py](modules/intelligence/distiller.py)** — Orchestrates cache check → fetch → Claude distillation → cache store. Truncates each leg to 3,000 chars for token budget. Strips markdown fences. Returns `None` on total failure (graceful degradation).
- **[prompts/intelligence.py](prompts/intelligence.py)** — System prompt enforces source credibility assessment, separates prescriptive vs. anecdotal signal, discards cargo-culted advice. User prompt with XML-delimited search results per leg.
- **[pages/2_Intelligence.py](pages/2_Intelligence.py)** — Displays intelligence brief with per-leg status indicators (Active/No data), categorized insights (rewards, skips, red flags, format prefs, ATS notes), collapsible source credibility notes. Shows degradation warning if brief is null.

### Tests (79 passing, cumulative)
- `test_cache.py` — 10 tests: store/retrieve, cache miss, case insensitivity, role collision, week collision, TTL expiry, corrupt JSON, clear cache
- `test_intelligence_fetch.py` — 11 tests: mocked Tavily (success, failure, missing key), truncation (within limit, exceeds, empty), mocked Claude distiller (success, cached hit, all empty, API error, invalid JSON)

### Test gate
All 79 tests green. No skips, no warnings.

---

## M3: Style + Gap Analysis — COMPLETE (2026-03-16)

### What was built
- **[modules/resume/style.py](modules/resume/style.py)** — `extract_style()` sends resume text + optional voice sample to Claude, returns validated `StyleProfile`. Voice sample block conditionally included in prompt. Handles markdown fences, JSON parse failures, schema validation errors.
- **[prompts/analysis.py](prompts/analysis.py)** — System prompt enforces specific/actionable gaps with severity levels and categories. Two user prompts: with-JD (compares against JD + intelligence) and without-JD (intelligence-only, notes limitation). XML-delimited user content.
- **[modules/resume/analyzer.py](modules/resume/analyzer.py)** — `analyze_gaps()` routes to correct prompt based on JD presence, handles optional intelligence brief. Returns validated `GapReport`. Logs severity breakdown.
- **[pages/3_Analysis.py](pages/3_Analysis.py)** — Two-panel display: StyleProfile metrics (formality, sentence length, structure, quantification, vocabulary) + GapReport with severity counts, color-coded expandable gaps sorted by priority.

### Tests (95 unit + 10 integration, cumulative)
- `test_style.py` — 7 unit tests (valid, voice sample inclusion/exclusion, markdown fences, invalid JSON, invalid literal, API error) + 2 integration tests (live style extraction with and without voice sample)
- `test_analyzer.py` — 9 unit tests (with/without JD, with/without intel, prompt routing, markdown fences, empty gaps, invalid JSON, API error) + 2 integration tests (live gap analysis with real resume + Northrop Grumman JD)
- `test_parser_structurer_live.py` — 3 integration tests (DOCX parse+structure, PDF parse+structure, full router)
- `test_intelligence_live.py` — 3 integration tests (live Tavily search, full fetch+distill pipeline, cache verification)

### Test gate
All 95 unit tests green. 10 integration tests deselected (run with `pytest -m integration`).

---

## M4: Rewrite Engine — COMPLETE (2026-03-16)

### What was built
- **[prompts/rewriting.py](prompts/rewriting.py)** — Three escalation levels, each with system + user prompt pairs. Shared building blocks: `build_style_constraint()` (enforces StyleProfile as hard constraint), `build_voice_block()` (includes voice sample exemplars), `build_intelligence_block()` (cites recruiter insights). Anti-patterns enforced: no buzzword lists, no generic verbs, no suspiciously uniform structure.
- **[modules/resume/rewriter.py](modules/resume/rewriter.py)** — `rewrite_resume()` with level routing:
  - **Level 1 (suggestions):** Returns dict with per-section suggestions, priorities, and change log. No text modification.
  - **Level 2 (edit):** Returns `RevisedResumeSchema` with surgical edits — stronger verbs, quantification, keyword insertion. Preserves sentence skeletons.
  - **Level 3 (full_rewrite):** Returns `RevisedResumeSchema` with sections rewritten from scratch. Change log must cite gaps/intelligence.
- **[modules/llm_helpers.py](modules/llm_helpers.py)** — (Added during M3 bugfix) Shared `extract_json()` with 3-stage fallback (direct parse → fence strip → brace match). `CLAUDE_MODEL` constant (`claude-sonnet-4-6`) used by all modules.

### Bugfixes applied during M3/M4 integration testing
- `max_tokens` increased: structurer 2000→4096, analyzer 1500→4096 (real resumes produce large JSON)
- `ResumeSchema.contact` type changed to `dict[str, str | None]` (Claude returns null for missing fields)
- Model ID corrected: `claude-sonnet-4-20250514` → `claude-sonnet-4-6`
- Added `tests/conftest.py` with `load_dotenv()` for integration test env loading

### Tests (105 unit + 13 integration, cumulative)
- `test_rewriter.py` — 10 unit tests (Level 1 suggestions, Level 1 with intel+voice, Level 2 revised schema, Level 2 contact preservation, Level 3 revised schema, Level 3 change log cites gaps, invalid level, API error, invalid JSON, bad schema) + 3 integration tests (live Level 1, 2, 3 with real resume + Northrop Grumman JD)

### Test gate
All 105 unit tests green. 13 integration tests deselected (run with `pytest -m integration`).

---

## M5: Scoring + Output — COMPLETE (2026-03-16)

### What was built
- **[prompts/scoring.py](prompts/scoring.py)** — Keyword extraction prompt: extracts technical skills, tools, certifications, and domain terms from JD. Normalizes to lowercase. Filters generic filler.
- **[modules/scoring/keyword_match.py](modules/scoring/keyword_match.py)** — `score_keywords()` extracts JD keywords via Claude, flattens resume into searchable text, computes match percentage. Labeled as "Job Description Match" — explicitly NOT an ATS compliance checker per CLAUDE.md spec.
- **[modules/output/renderer.py](modules/output/renderer.py)** — `render_docx()` generates professional DOCX from any `ResumeSchema` or `RevisedResumeSchema`. Calibri 11pt, narrow margins, centered contact block, section headings, bullet lists. Returns bytes for streaming download — no server-side storage.
- **[pages/4_Output.py](pages/4_Output.py)** — Full output page: rewrite level selector (radio with descriptions), Level 3 confirmation gate, suggestions display (Level 1) or side-by-side diff (Levels 2/3), collapsible change rationale panel, keyword match scoring with present/missing breakdown, DOCX download button.

### Tests (122 unit + 14 integration, cumulative)
- `test_keyword_match.py` — 8 unit tests (text flattening, scoring with matches, all present, none present, empty keywords, API error, invalid JSON) + 1 integration test (live full pipeline → keyword scoring)
- `test_renderer.py` — 9 unit tests (returns bytes, valid DOCX, contains name/experience/skills/education/certifications, empty resume, original ResumeSchema)

### Test gate
All 122 unit tests green. 14 integration tests deselected.

---

## M6: Full Pipeline Integration — COMPLETE (2026-03-16)

### What was built
- **[tests/integration/test_pipeline_end_to_end.py](tests/integration/test_pipeline_end_to_end.py)** — Three mocked end-to-end tests (full pipeline, no-JD path, graceful degradation when intelligence fails) + one live integration test (complete 8-stage pipeline with real resume + Northrop Grumman JD).
- **[app.py](app.py)** — Polished entry point with pipeline status tracker (6-stage progress bar with completion/degradation indicators), how-it-works guide, env validation.
- Removed debug scripts, verified final file structure.

### Tests (125 unit + 15 integration, final)
- `test_pipeline_end_to_end.py` — 3 mocked tests (happy path, no JD, graceful degradation) + 1 live integration test (full 8-stage pipeline: parse → structure → intelligence → style → gaps → rewrite → keyword score → DOCX render)

### Test gate
All 125 unit tests green. 15 integration tests available (`pytest -m integration`).

---

## Final Summary

| Milestone | Status | Unit Tests | Integration Tests |
|---|---|---|---|
| Foundation | Complete | 34 | — |
| M1: Input + Parse | Complete | 15 | 3 |
| M2: Intelligence Fetch | Complete | 21 | 3 |
| M3: Style + Gap Analysis | Complete | 16 | 4 |
| M4: Rewrite Engine | Complete | 10 | 3 |
| M5: Scoring + Output | Complete | 17 | 1 |
| M6: Full Pipeline | Complete | 3 | 1 |
| **Total** | **All gates passed** | **125** | **15** |

### To run
- Unit tests: `python -m pytest -v`
- Integration tests (live API): `python -m pytest -m integration -v`
- Streamlit app: `streamlit run app.py`

---

## Post-M6: COA 2 Enhancements — COMPLETE (2026-03-16)

### Intelligence Query Refinement
- **[modules/intelligence/fetcher.py](modules/intelligence/fetcher.py)** — Overhauled all three tripod queries:
  - **LinkedIn:** Switched to `search_depth="advanced"` (2 credits vs 1). Primary query targets first-person recruiter language (`"what I look for"`, `"what stands out"`, `"common mistakes"`). Fallback query broadens to `"talent acquisition"` + tips if primary returns < 2 results.
  - **Reddit:** Primary query targets rejection signals (`"instant no"`, `"red flag"`). Fallback broadens to general feedback threads.
  - **Broad:** Primary uses industry-specific query. Fallback targets `"hiring manager perspective"`.
  - All legs deduplicate results across primary + fallback via `_merge_results()`.
- **[modules/intelligence/distiller.py](modules/intelligence/distiller.py)** — `max_tokens` increased 1000→2048 (detailed briefs were getting truncated).

### Rewrite Verification Pass
- **[models/schemas.py](models/schemas.py)** — Added `VerificationFlag` (7 categories: new_company, new_title, new_date, new_metric, new_skill, new_certification, new_claim; 2 severities: warning, info) and `VerificationReport` (flags list + verified_clean bool).
- **[prompts/verification.py](prompts/verification.py)** — System prompt distinguishes legitimate edits (rephrasing, stronger verbs, keyword additions to skills section) from fabrication (invented metrics, companies, titles, dates). Clear severity guidance: new metrics = warning, new skills in skills section = info.
- **[modules/resume/verifier.py](modules/resume/verifier.py)** — `verify_rewrite()` compares original `ResumeSchema` vs `RevisedResumeSchema` in a single Claude call. Standalone module — if it fails, the pipeline still works; user just doesn't see warnings.
- **[pages/4_Output.py](pages/4_Output.py)** — Verification panel runs automatically after any Level 2/3 rewrite. Shows green "verified clean" banner or expandable warning/info flags with original text, revised text, and explanation. Displayed before download button so user reviews before exporting.

### UI Improvements (from user feedback)
- **[pages/1_Upload.py](pages/1_Upload.py)** — Job posting now accepts URL (fetches via `requests` + BeautifulSoup, strips HTML/nav/scripts). Voice sample now accepts file upload (PDF, DOCX, TXT) in addition to paste. Radio toggles for input method.
- **[pages/4_Output.py](pages/4_Output.py)** — Button label is now dynamic: "Generate Suggestions" / "Generate Edit" / "Generate Rewrite" based on selected level.
- **[requirements.txt](requirements.txt)** — Added `requests` and `beautifulsoup4`.

### Tests (136 unit + 16 integration, cumulative)
- `test_verifier.py` — 6 unit tests (flagged content, clean verification, prompt content, API error, invalid JSON, markdown fences) + 5 schema tests (valid flag, null original, invalid category, clean report, flagged report) + 1 integration test (live verification of real resume edit)

### Test gate
All 136 unit tests green. 16 integration tests available.

---

## Updated Final Summary

| Milestone | Status | Unit Tests | Integration Tests |
|---|---|---|---|
| Foundation | Complete | 34 | — |
| M1: Input + Parse | Complete | 15 | 3 |
| M2: Intelligence Fetch | Complete | 21 | 3 |
| M3: Style + Gap Analysis | Complete | 16 | 4 |
| M4: Rewrite Engine | Complete | 10 | 3 |
| M5: Scoring + Output | Complete | 17 | 1 |
| M6: Full Pipeline | Complete | 3 | 1 |
| COA 2: Intel + Verification | Complete | 11 | 1 |
| **Total** | **All gates passed** | **136** | **16** |
