import pytest

from claude_planner.intake import IntakeError, summarize_intake


def test_summarize_intake_returns_placeholder_when_no_path():
    assert "brak folderu" in summarize_intake(None)


def test_summarize_intake_raises_when_path_does_not_exist(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(IntakeError):
        summarize_intake(missing)


def test_summarize_intake_raises_when_path_is_a_file(tmp_path):
    spec_file = tmp_path / "spec.txt"
    spec_file.write_text("notatki", encoding="utf-8")
    with pytest.raises(IntakeError):
        summarize_intake(spec_file)


def test_summarize_intake_returns_placeholder_when_dir_is_empty(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert "pusty" in summarize_intake(empty_dir)
