"""All Pydantic v2 schemas for the resume builder pipeline."""

from typing import Literal
from pydantic import BaseModel, Field


class UserInput(BaseModel):
    resume_text: str
    job_posting: str | None = None
    role_category: str
    industry: str
    voice_sample: str | None = None


class StyleProfile(BaseModel):
    formality_level: Literal["formal", "neutral", "conversational"]
    sentence_length: Literal["short", "mixed", "long"]
    structure_tendency: Literal["action_first", "context_first", "mixed"]
    quantification_habit: Literal["frequent", "occasional", "rare"]
    vocabulary_register: str = Field(
        description="Brief free-text characterization of vocabulary register"
    )


class IntelligenceBrief(BaseModel):
    role_category: str
    industry: str
    week: str = Field(description='ISO week string, e.g. "2025-W22"')
    what_recruiters_reward: list[str] = Field(default_factory=list)
    what_recruiters_skip: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    format_preferences: list[str] = Field(default_factory=list)
    current_ats_notes: list[str] = Field(default_factory=list)
    source_credibility_notes: str = ""
    legs_populated: list[Literal["linkedin", "reddit", "broad"]] = Field(
        default_factory=list
    )


class ResumeSection(BaseModel):
    section_type: str
    raw_text: str
    bullets: list[str] | None = None


class ResumeSchema(BaseModel):
    contact: dict[str, str | None] = Field(default_factory=dict)
    summary: str | None = None
    experience: list[ResumeSection] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    education: list[ResumeSection] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class GapItem(BaseModel):
    severity: Literal["high", "medium", "low"]
    category: str
    description: str
    suggested_action: str


class GapReport(BaseModel):
    gaps: list[GapItem] = Field(default_factory=list)
    jd_provided: bool


class KeywordReport(BaseModel):
    match_pct: float
    present_terms: list[str] = Field(default_factory=list)
    missing_terms: list[str] = Field(default_factory=list)


class RevisedResumeSchema(ResumeSchema):
    rewrite_level_used: Literal["suggestions", "edit", "full_rewrite"]
    change_log: list[str] = Field(
        default_factory=list,
        description="Human-readable list of changes made",
    )


class VerificationFlag(BaseModel):
    category: Literal[
        "new_company",
        "new_title",
        "new_date",
        "new_metric",
        "new_skill",
        "new_certification",
        "new_claim",
    ]
    severity: Literal["warning", "info"]
    original_text: str | None = Field(
        default=None,
        description="The closest matching text in the original, if any",
    )
    revised_text: str = Field(
        description="The text in the revision that triggered this flag",
    )
    explanation: str


class VerificationReport(BaseModel):
    flags: list[VerificationFlag] = Field(default_factory=list)
    verified_clean: bool = Field(
        description="True if no flags were raised",
    )
