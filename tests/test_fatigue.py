from claude_planner.fatigue import FatigueTracker, is_affirmative, is_dismissive


def test_is_dismissive_matches_common_polish_brushoffs():
    for text in [
        "pomiń",
        "Pomin to",
        "nie wiem",
        "zostaw to",
        "bez znaczenia",
        "cokolwiek",
    ]:
        assert is_dismissive(text), text


def test_is_dismissive_false_for_content_answers():
    assert not is_dismissive("Chcemy hostować na AWS, budżet to 50000 PLN")


def test_is_affirmative_matches_yes_like_answers():
    for text in ["tak", "Tak, pomiń", "ok", "okej", "jasne"]:
        assert is_affirmative(text), text


def test_is_affirmative_false_for_no():
    assert not is_affirmative("nie, chcę kontynuować")


def test_fatigue_tracker_trips_breaker_exactly_once_at_threshold():
    tracker = FatigueTracker(threshold=3)
    assert tracker.record("pomiń") is False
    assert tracker.record("nie wiem") is False
    assert tracker.record("zostaw to") is True
    assert tracker.breaker_tripped is True
    # kolejne zbywające odpowiedzi nie wyzwalają breakera ponownie
    assert tracker.record("cokolwiek") is False


def test_fatigue_tracker_ignores_content_answers():
    tracker = FatigueTracker(threshold=2)
    assert tracker.record("AWS") is False
    assert tracker.record("pomiń") is False
    assert tracker.count == 1
    assert tracker.breaker_tripped is False
