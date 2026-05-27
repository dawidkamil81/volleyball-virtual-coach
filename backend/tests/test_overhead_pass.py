from __future__ import annotations

from backend.analysis.overhead_pass import detect_overhead_pass_issues
from backend.schemas import Landmark


def _blank_landmarks(*, visibility: float = 1.0) -> list[Landmark]:
    return [Landmark(x=0.0, y=0.0, z=0.0, visibility=visibility) for _ in range(33)]


def _active_front_pose(*, wrists_y: float = 0.35) -> list[Landmark]:
    """Pozycja aktywna (ręce nad ramionami) z konfigurowalną wysokością nadgarstków."""
    lms = _blank_landmarks()
    lms[11] = Landmark(x=0.4, y=0.5, z=0.0, visibility=1.0)
    lms[12] = Landmark(x=0.6, y=0.5, z=0.0, visibility=1.0)
    lms[13] = Landmark(x=0.45, y=0.38, z=0.0, visibility=1.0)
    lms[14] = Landmark(x=0.55, y=0.38, z=0.0, visibility=1.0)
    lms[15] = Landmark(x=0.45, y=wrists_y, z=0.0, visibility=1.0)
    lms[16] = Landmark(x=0.55, y=wrists_y, z=0.0, visibility=1.0)
    lms[0] = Landmark(x=0.5, y=0.3, z=0.0, visibility=1.0)
    lms[2] = Landmark(x=0.48, y=0.32, z=0.0, visibility=1.0)
    lms[5] = Landmark(x=0.52, y=0.32, z=0.0, visibility=1.0)
    return lms


def _side_bent_knees(*, knee_angle_setup: str = "bent") -> list[Landmark]:
    """Kamera boczna: ugięte lub proste kolana (profil lewej nogi)."""
    lms = _blank_landmarks()
    lms[23] = Landmark(x=0.5, y=0.55, z=0.0, visibility=1.0)
    if knee_angle_setup == "bent":
        lms[25] = Landmark(x=0.52, y=0.72, z=0.0, visibility=1.0)
        lms[27] = Landmark(x=0.48, y=0.92, z=0.0, visibility=1.0)
    else:
        lms[25] = Landmark(x=0.5, y=0.75, z=0.0, visibility=1.0)
        lms[27] = Landmark(x=0.5, y=0.95, z=0.0, visibility=1.0)
    return lms


def test_low_visibility_returns_issue() -> None:
    lms = _blank_landmarks(visibility=0.0)
    result = detect_overhead_pass_issues(lms, min_visibility=0.5)
    assert result.issues
    assert result.issues[0].code == "low_visibility"
    assert result.peak_valid is False


def test_contact_too_low_detected() -> None:
    # Nadgarstki powyżej ramion (aktywny ruch), ale za nisko względem oczu/czoła
    front = _active_front_pose(wrists_y=0.45)
    side = _side_bent_knees(knee_angle_setup="bent")

    result = detect_overhead_pass_issues(front, side)
    codes = {i.code for i in result.issues}
    assert "contact_too_low" in codes
    assert result.peak_valid is False


def test_straight_knees_from_side_camera() -> None:
    front = _active_front_pose(wrists_y=0.25)
    side = _side_bent_knees(knee_angle_setup="straight")

    result = detect_overhead_pass_issues(front, side)
    codes = {i.code for i in result.issues}
    assert "no_legs_drive" in codes
    assert result.peak_valid is False


def test_peak_valid_with_front_and_side() -> None:
    front = _active_front_pose(wrists_y=0.25)
    side = _side_bent_knees(knee_angle_setup="bent")

    result = detect_overhead_pass_issues(front, side)
    assert result.peak_valid is True
