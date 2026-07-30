"""Modele danych: profile stacków, role wywiadu, brief projektu."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillSpec(BaseModel):
    """Deklaracja skilla Claude Code dostarczanego przez profil stacku."""

    name: str
    description: str
    when_to_use: str
    guidance: str = ""


class AgentSpec(BaseModel):
    """Deklaracja dodatkowego agenta (poza rolami bazowymi) dostarczanego przez profil."""

    id: str
    name: str
    description: str
    focus: str


class StackProfile(BaseModel):
    """Jeden deklaratywny profil stacku (plik YAML w profiles/)."""

    id: str
    name: str
    description: str
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    extra_agents: list[AgentSpec] = Field(default_factory=list)
    skills: list[SkillSpec] = Field(default_factory=list)
    setup_commands: list[str] = Field(default_factory=list)
    conventions_hints: str = ""
    testing_hints: str = ""
    claude_hints: str = ""


class InterviewRole(BaseModel):
    """Jeden etap sekwencyjnego wywiadu, prowadzony jako osobna persona/agent."""

    id: str
    display_name: str
    persona: str
    topics: list[str]
    goal: str


class InterviewAnswer(BaseModel):
    role_id: str
    question: str
    answer: str


class InterviewStageResult(BaseModel):
    role_id: str
    display_name: str
    qa: list[InterviewAnswer] = Field(default_factory=list)
    summary: str = ""


class ProjectBrief(BaseModel):
    """Zebrane dane o projekcie: metadane + wynik wywiadu + wybrane profile."""

    project_name: str
    client_name: str
    language: str = "pl"
    profile_ids: list[str] = Field(default_factory=list)
    intake_path: str | None = None
    intake_summary: str = ""
    stages: list[InterviewStageResult] = Field(default_factory=list)
