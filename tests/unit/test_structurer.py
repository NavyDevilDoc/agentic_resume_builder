"""Tests for raw text to ResumeSchema structuring (mocked Claude API)."""

import json
from unittest.mock import MagicMock, patch

import pytest

from models.schemas import ResumeSchema
from modules.resume.structurer import StructuringError, structure_resume


VALID_STRUCTURED_RESPONSE = json.dumps({
    "contact": {
        "name": "Jeremy Springston",
        "email": "jeremy.springston@gmail.com",
        "phone": "678-852-8379",
        "location": "Fredericksburg, VA",
        "linkedin": "Jeremy Springston",
        "github": "NavyDevilDoc",
    },
    "summary": "AI/ML Engineer and U.S. Navy Engineering Duty Officer with 20+ years of leadership experience.",
    "experience": [
        {
            "section_type": "experience",
            "raw_text": "Booz Allen Hamilton, AI/ML Engineer 3, Arlington, VA, 05/2025 – Present",
            "bullets": [
                "Coordinating critical engineering decisions for PEO IWS 11.0",
                "Architected semantic search and LLM-based productivity tools",
            ],
        }
    ],
    "skills": ["Python", "PyTorch", "TensorFlow", "LangChain", "RAG"],
    "education": [
        {
            "section_type": "education",
            "raw_text": "MS Johns Hopkins University, Applied Mathematics 2021",
            "bullets": None,
        }
    ],
    "certifications": [],
})


def _mock_response(text: str) -> MagicMock:
    """Create a mock Claude API response."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


class TestStructureResume:
    @patch("modules.resume.structurer.anthropic.Anthropic")
    def test_valid_response(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(
            VALID_STRUCTURED_RESPONSE
        )

        result = structure_resume("Some resume text here")

        assert isinstance(result, ResumeSchema)
        assert result.contact["name"] == "Jeremy Springston"
        assert len(result.experience) == 1
        assert len(result.skills) == 5
        assert result.summary is not None

    @patch("modules.resume.structurer.anthropic.Anthropic")
    def test_strips_markdown_fences(self, mock_anthropic_cls):
        """Claude sometimes wraps JSON in ```json ... ``` despite instructions."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        fenced = f"```json\n{VALID_STRUCTURED_RESPONSE}\n```"
        mock_client.messages.create.return_value = _mock_response(fenced)

        result = structure_resume("Resume text")
        assert isinstance(result, ResumeSchema)
        assert result.contact["name"] == "Jeremy Springston"

    @patch("modules.resume.structurer.anthropic.Anthropic")
    def test_invalid_json_raises(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _mock_response(
            "This is not JSON at all"
        )

        with pytest.raises(StructuringError, match="invalid response"):
            structure_resume("Resume text")

    @patch("modules.resume.structurer.anthropic.Anthropic")
    def test_valid_json_bad_schema_raises(self, mock_anthropic_cls):
        """Valid JSON but doesn't match ResumeSchema (e.g., wrong types)."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        bad_schema = json.dumps({"contact": "not a dict", "skills": "not a list"})
        mock_client.messages.create.return_value = _mock_response(bad_schema)

        with pytest.raises(StructuringError, match="did not match"):
            structure_resume("Resume text")

    @patch("modules.resume.structurer.anthropic.Anthropic")
    def test_api_error_raises(self, mock_anthropic_cls):
        import anthropic

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.side_effect = anthropic.APIError(
            message="rate limited",
            request=MagicMock(),
            body=None,
        )

        with pytest.raises(StructuringError, match="AI service"):
            structure_resume("Resume text")

    @patch("modules.resume.structurer.anthropic.Anthropic")
    def test_empty_resume_still_processes(self, mock_anthropic_cls):
        """An empty resume schema is valid — parser handles non-empty enforcement."""
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        empty_response = json.dumps({
            "contact": {},
            "summary": None,
            "experience": [],
            "skills": [],
            "education": [],
            "certifications": [],
        })
        mock_client.messages.create.return_value = _mock_response(empty_response)

        result = structure_resume("")
        assert isinstance(result, ResumeSchema)
        assert result.experience == []
