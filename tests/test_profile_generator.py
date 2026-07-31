import json

import pytest
import yaml

from claude_planner.claude_client import ClaudeCLIError
from claude_planner.models import StackProfile
from claude_planner.profile_generator import generate_profile, profile_to_yaml

FAKE_PROFILE_JSON = {
    "name": "Ruby on Rails",
    "description": "Monolit webowy w Ruby on Rails.",
    "languages": ["Ruby"],
    "frameworks": ["Rails", "Sidekiq"],
    "setup_commands": ["bundle install"],
    "extra_agents": [
        {
            "id": "sidekiq-specialist",
            "name": "Sidekiq Specialist",
            "description": "Pilnuje jakości jobów w tle.",
            "focus": "Idempotencja i retry jobów.",
        }
    ],
    "skills": [
        {
            "name": "active-record-conventions",
            "description": "Konwencje ActiveRecord.",
            "when_to_use": "Przy modelach.",
            "guidance": "Unikaj N+1.",
        }
    ],
    "conventions_hints": "Rails Way.",
    "testing_hints": "RSpec.",
    "claude_hints": "Konwencja nad konfiguracją.",
}


def test_generate_profile_returns_valid_stack_profile(monkeypatch):
    monkeypatch.setattr(
        "claude_planner.profile_generator.one_shot",
        lambda *a, **k: json.dumps(FAKE_PROFILE_JSON),
    )
    profile = generate_profile("Ruby on Rails + Sidekiq", "ruby-on-rails", model="sonnet")
    assert isinstance(profile, StackProfile)
    assert profile.id == "ruby-on-rails"
    assert profile.name == "Ruby on Rails"
    assert profile.setup_commands == ["bundle install"]
    assert profile.extra_agents[0].id == "sidekiq-specialist"


def test_profile_to_yaml_round_trips_through_stack_profile(monkeypatch):
    monkeypatch.setattr(
        "claude_planner.profile_generator.one_shot",
        lambda *a, **k: json.dumps(FAKE_PROFILE_JSON),
    )
    profile = generate_profile("Ruby on Rails + Sidekiq", "ruby-on-rails")
    yaml_text = profile_to_yaml(profile)

    reloaded = StackProfile.model_validate(yaml.safe_load(yaml_text))
    assert reloaded == profile
    assert yaml_text.startswith("id: ruby-on-rails")


def test_generate_profile_raises_claude_cli_error_on_invalid_json(monkeypatch):
    monkeypatch.setattr(
        "claude_planner.profile_generator.one_shot", lambda *a, **k: "not valid json"
    )
    with pytest.raises(ClaudeCLIError):
        generate_profile("Stack nieznany", "some-id")


def test_generate_profile_raises_claude_cli_error_on_schema_violation(monkeypatch):
    monkeypatch.setattr(
        "claude_planner.profile_generator.one_shot",
        lambda *a, **k: json.dumps({"name": "Niepełny profil"}),
    )
    with pytest.raises(ClaudeCLIError):
        generate_profile("Stack nieznany", "some-id")


def test_generate_profile_strips_markdown_code_fence(monkeypatch):
    fenced = "```json\n" + json.dumps(FAKE_PROFILE_JSON) + "\n```"
    monkeypatch.setattr("claude_planner.profile_generator.one_shot", lambda *a, **k: fenced)
    profile = generate_profile("Ruby on Rails + Sidekiq", "ruby-on-rails")
    assert profile.name == "Ruby on Rails"


def test_generate_profile_strips_prose_around_json(monkeypatch):
    wrapped = "Oto profil:\n" + json.dumps(FAKE_PROFILE_JSON) + "\nMam nadzieję, że pomoże."
    monkeypatch.setattr("claude_planner.profile_generator.one_shot", lambda *a, **k: wrapped)
    profile = generate_profile("Ruby on Rails + Sidekiq", "ruby-on-rails")
    assert profile.name == "Ruby on Rails"


def test_generate_profile_retries_after_transient_bad_output(monkeypatch):
    calls = {"n": 0}

    def fake_one_shot(*a, **k):
        calls["n"] += 1
        if calls["n"] < 2:
            return "not valid json"
        return json.dumps(FAKE_PROFILE_JSON)

    monkeypatch.setattr("claude_planner.profile_generator.one_shot", fake_one_shot)
    profile = generate_profile("Ruby on Rails + Sidekiq", "ruby-on-rails")
    assert profile.name == "Ruby on Rails"
    assert calls["n"] == 2


def test_generate_profile_does_not_pass_json_schema_to_one_shot(monkeypatch):
    captured = {}

    def fake_one_shot(*a, **k):
        captured.update(k)
        return json.dumps(FAKE_PROFILE_JSON)

    monkeypatch.setattr("claude_planner.profile_generator.one_shot", fake_one_shot)
    generate_profile("Ruby on Rails + Sidekiq", "ruby-on-rails")
    assert captured.get("json_schema") is None
