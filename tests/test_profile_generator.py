import json

import yaml

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
