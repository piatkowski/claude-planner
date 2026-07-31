import pytest

from claude_planner.profiles import get_profile, load_all_profiles

EXPECTED_IDS = {
    "web-fullstack",
    "backend-api",
    "mobile",
    "python",
    "wordpress-woocommerce",
    "ai-ml",
    "postgresql-pgvector-postgis",
    "generic",
    "symfony",
    "laravel",
    "django",
    "react-native",
    "flutter",
    "rag-ai-agents",
    "data-engineering",
    "machine-learning",
}


def test_all_v1_profiles_present():
    profiles = load_all_profiles()
    assert EXPECTED_IDS <= set(profiles.keys())


def test_profile_fields_populated():
    profiles = load_all_profiles()
    for profile in profiles.values():
        assert profile.name
        assert profile.description


def test_get_profile_unknown_raises_with_available_list():
    try:
        get_profile("does-not-exist")
    except KeyError as exc:
        assert "web-fullstack" in str(exc)
    else:
        raise AssertionError("expected KeyError")


def test_get_profile_returns_matching_id():
    profile = get_profile("wordpress-woocommerce")
    assert profile.id == "wordpress-woocommerce"
    assert "PHP" in profile.languages


def test_load_all_profiles_skips_unparseable_yaml_and_warns(tmp_path):
    (tmp_path / "broken.yaml").write_text("key: [unclosed list\n", encoding="utf-8")
    (tmp_path / "good.yaml").write_text(
        "id: custom-good\nname: Custom Good\ndescription: opis\n", encoding="utf-8"
    )

    with pytest.warns(UserWarning, match="broken.yaml"):
        profiles = load_all_profiles(extra_dir=tmp_path)

    assert "custom-good" in profiles
    assert all(pid != "broken" for pid in profiles)


def test_load_all_profiles_skips_profile_missing_required_fields(tmp_path):
    (tmp_path / "invalid.yaml").write_text("id: custom-invalid\n", encoding="utf-8")

    with pytest.warns(UserWarning, match="invalid.yaml"):
        profiles = load_all_profiles(extra_dir=tmp_path)

    assert "custom-invalid" not in profiles
