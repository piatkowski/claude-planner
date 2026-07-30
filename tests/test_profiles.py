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
