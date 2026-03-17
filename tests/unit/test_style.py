"""Tests for StyleProfile extraction — unit (mocked) + integration (live)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import StyleProfile
from modules.resume.style import StyleExtractionError, extract_style


VALID_STYLE_JSON = json.dumps({
    "formality_level": "formal",
    "sentence_length": "mixed",
    "structure_tendency": "action_first",
    "quantification_habit": "frequent",
    "vocabulary_register": "Technical, acronym-heavy, defense sector jargon",
})


def _mock_response(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


# ── Unit tests (mocked Claude) ─────────────────────────────────────────

class TestExtractStyleMocked:
    @patch("modules.resume.style.anthropic.Anthropic")
    def test_valid_response(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(VALID_STYLE_JSON)

        result = extract_style("Some resume text")

        assert isinstance(result, StyleProfile)
        assert result.formality_level == "formal"
        assert result.structure_tendency == "action_first"
        assert result.quantification_habit == "frequent"
        assert "defense" in result.vocabulary_register.lower()

    @patch("modules.resume.style.anthropic.Anthropic")
    def test_with_voice_sample(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(VALID_STYLE_JSON)

        result = extract_style("Resume text", voice_sample="I write like this.")

        assert isinstance(result, StyleProfile)
        # Verify voice sample was included in the prompt
        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "voice_sample" in user_msg
        assert "I write like this." in user_msg

    @patch("modules.resume.style.anthropic.Anthropic")
    def test_without_voice_sample(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(VALID_STYLE_JSON)

        extract_style("Resume text", voice_sample=None)

        call_args = mock_client.messages.create.call_args
        user_msg = call_args[1]["messages"][0]["content"]
        assert "<voice_sample>" not in user_msg

    @patch("modules.resume.style.anthropic.Anthropic")
    def test_strips_markdown_fences(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        fenced = f"```json\n{VALID_STYLE_JSON}\n```"
        mock_client.messages.create.return_value = _mock_response(fenced)

        result = extract_style("Resume text")
        assert isinstance(result, StyleProfile)

    @patch("modules.resume.style.anthropic.Anthropic")
    def test_invalid_json_raises(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response("not json")

        with pytest.raises(StyleExtractionError, match="invalid"):
            extract_style("Resume text")

    @patch("modules.resume.style.anthropic.Anthropic")
    def test_invalid_literal_raises(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        bad_data = json.dumps({
            "formality_level": "super_casual",
            "sentence_length": "mixed",
            "structure_tendency": "action_first",
            "quantification_habit": "frequent",
            "vocabulary_register": "Casual",
        })
        mock_client.messages.create.return_value = _mock_response(bad_data)

        with pytest.raises(StyleExtractionError, match="did not match"):
            extract_style("Resume text")

    @patch("modules.resume.style.anthropic.Anthropic")
    def test_api_error_raises(self, mock_anthropic_cls):
        import anthropic

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="rate limited", request=MagicMock(), body=None
        )

        with pytest.raises(StyleExtractionError, match="Failed to analyze"):
            extract_style("Resume text")


# ── Integration tests (live Claude) ────────────────────────────────────

@pytest.mark.integration
class TestExtractStyleLive:
    """Live API tests — only run with: pytest -m integration"""

    def _get_resume_text(self) -> str:
        from pathlib import Path
        docx_path = (
            Path(__file__).parent.parent
            / "fixtures"
            / "sample_resumes"
            / "sample_resume.docx"
        )
        if not docx_path.exists():
            pytest.skip("DOCX fixture not available")
        from modules.resume.parser import parse_docx
        return parse_docx(docx_path.read_bytes())

    def test_live_style_extraction(self):
        resume_text = self._get_resume_text()
        result = extract_style(resume_text)

        assert isinstance(result, StyleProfile)
        assert result.formality_level in ("formal", "neutral", "conversational")
        assert result.sentence_length in ("short", "mixed", "long")
        assert result.structure_tendency in ("action_first", "context_first", "mixed")
        assert result.quantification_habit in ("frequent", "occasional", "rare")
        assert len(result.vocabulary_register) > 0

    def test_live_style_with_voice_sample(self):
        resume_text = self._get_resume_text()
        voice = (
            "I tend to write in a direct, technical style. I prefer "
            "leading with results and backing them up with context."
        )
        result = extract_style(resume_text, voice_sample=voice)

        assert isinstance(result, StyleProfile)
        assert len(result.vocabulary_register) > 0
