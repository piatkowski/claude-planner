"""Modele danych: profile stacków, role wywiadu, brief projektu."""

from __future__ import annotations

from enum import Enum

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


class ProjectScale(str, Enum):
    """Ocena skali projektu przez Orchestratora (Moduł 3: Agentic Routing) — steruje
    tym, jak dociekliwe technicznie mogą/powinny być kolejne etapy wywiadu (np. QA/DevOps)."""

    MICRO = "Micro"
    SMALL = "Small"
    MEDIUM = "Medium"
    ENTERPRISE = "Enterprise"


class ProjectState(BaseModel):
    """Globalna pamięć współdzielona (Blackboard pattern) między etapami/rolami wywiadu.

    Jedyne źródło prawdy o faktach ustalonych do tej pory — wstrzykiwana jako zrzut do
    system promptu każdej roli, żeby żadna z nich nie pytała ponownie o coś, co już tu
    jest. Aktualizowana po każdej odpowiedzi użytkownika (patrz `claude_planner.state`).
    """

    facts: dict[str, str] = Field(default_factory=dict)
    fact_sources: dict[str, str] = Field(default_factory=dict)
    scale: ProjectScale | None = None
    scale_justification: str = ""
    fatigue_triggered: bool = False


class ProjectBrief(BaseModel):
    """Zebrane dane o projekcie: metadane + wynik wywiadu + wybrane profile."""

    project_name: str
    client_name: str
    language: str = "pl"
    profile_ids: list[str] = Field(default_factory=list)
    intake_path: str | None = None
    intake_summary: str = ""
    stages: list[InterviewStageResult] = Field(default_factory=list)
    state: ProjectState = Field(default_factory=ProjectState)
