from __future__ import annotations

import math
from backend.analysis.overhead_pass import detect_overhead_pass_issues, _side_knee_angles_deg, _most_bent_knee_angle
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
    # Dodajemy palce aby uniknąć closed_fists (index y < wrist y)
    lms[19] = Landmark(x=0.45, y=wrists_y - 0.05, z=0.0, visibility=1.0)
    lms[20] = Landmark(x=0.55, y=wrists_y - 0.05, z=0.0, visibility=1.0)
    lms[0] = Landmark(x=0.5, y=0.3, z=0.0, visibility=1.0)
    lms[2] = Landmark(x=0.48, y=0.32, z=0.0, visibility=1.0)
    lms[5] = Landmark(x=0.52, y=0.32, z=0.0, visibility=1.0)
    return lms

def _side_bent_knees(*, knee_angle_setup: str = "bent") -> list[Landmark]:
    """Kamera boczna: ugięte lub proste kolana (profil lewej nogi)."""
    lms = _blank_landmarks()
    # Hip
    lms[23] = Landmark(x=0.5, y=0.5, z=0.0, visibility=1.0)
    if knee_angle_setup == "bent":
        # Bent to exactly 90 degrees: Hip(0.5, 0.5), Knee(0.7, 0.5), Ankle(0.7, 0.7)
        lms[25] = Landmark(x=0.7, y=0.5, z=0.0, visibility=1.0)
        lms[27] = Landmark(x=0.7, y=0.7, z=0.0, visibility=1.0)
    elif knee_angle_setup == "straight":
        # Straight (180 degrees): Hip(0.5, 0.5), Knee(0.5, 0.7), Ankle(0.5, 0.9)
        lms[25] = Landmark(x=0.5, y=0.7, z=0.0, visibility=1.0)
        lms[27] = Landmark(x=0.5, y=0.9, z=0.0, visibility=1.0)
    elif knee_angle_setup == "standing":
        # ~165 degrees (slightly bent): Hip(0.5, 0.5), Knee(0.52, 0.7), Ankle(0.5, 0.9)
        lms[25] = Landmark(x=0.52, y=0.7, z=0.0, visibility=1.0)
        lms[27] = Landmark(x=0.5, y=0.9, z=0.0, visibility=1.0)
    return lms

def test_low_visibility_returns_issue() -> None:
    lms = _blank_landmarks(visibility=0.0)
    result = detect_overhead_pass_issues(lms, min_visibility=0.5)
    assert result.issues
    assert result.issues[0].code == "low_visibility"

def test_contact_too_low_detected() -> None:
    front = _active_front_pose(wrists_y=0.45)
    side = _side_bent_knees(knee_angle_setup="bent")
    result = detect_overhead_pass_issues(front, side)
    codes = {i.code for i in result.issues}
    assert "contact_too_low" in codes

def test_straight_knees_peak_emits_no_legs_drive() -> None:
    # Faza PEAK (wrists bardzo wysoko)
    front = _active_front_pose(wrists_y=0.15)
    # Proste kolana -> kąt 180 stopni
    side = _side_bent_knees(knee_angle_setup="straight")

    result = detect_overhead_pass_issues(front, side)
    codes = {i.code for i in result.issues}
    assert result.phase == "peak"
    assert "no_legs_drive" not in codes # Kąt 180 > 135, na szczycie wymuszamy pełen wyprost (kąt rośnie)

def test_bent_knees_peak_emits_no_legs_drive() -> None:
    # Faza PEAK (wrists bardzo wysoko)
    front = _active_front_pose(wrists_y=0.15)
    # Zgięte kolana -> kąt 90 stopni (brak wyprostu)
    side = _side_bent_knees(knee_angle_setup="bent")

    result = detect_overhead_pass_issues(front, side)
    codes = {i.code for i in result.issues}
    assert result.phase == "peak"
    assert "no_legs_drive" in codes # Kąt 90 < 135, nie ma wyprostu

def test_standing_knees_bottom_emits_too_straight() -> None:
    # Faza BOTTOM (wrists pod czołem ale wciąż ręce podniesione, czyli < 0.5)
    front = _active_front_pose(wrists_y=0.45)
    # Stanie prosto (165 stopni)
    side = _side_bent_knees(knee_angle_setup="standing")

    result = detect_overhead_pass_issues(front, side)
    codes = {i.code for i in result.issues}
    assert result.phase == "bottom"
    assert "knees_too_straight" in codes # Kąt ~165 >= 145, nie ugięto na dole

def test_bent_knees_bottom_is_correct() -> None:
    # Faza BOTTOM
    front = _active_front_pose(wrists_y=0.45)
    # Zgięte kolana -> kąt 90 stopni
    side = _side_bent_knees(knee_angle_setup="bent")

    result = detect_overhead_pass_issues(front, side)
    codes = {i.code for i in result.issues}
    assert result.phase == "bottom"
    assert "knees_too_straight" not in codes # 90 < 145, jest poprawne ugięcie

def test_knee_angle_calculation() -> None:
    side = _side_bent_knees(knee_angle_setup="bent")
    angles = _side_knee_angles_deg(side, min_visibility=0.5)
    assert len(angles) == 1
    # 90 stopni to dokładny wyliczony kąt wektorów
    assert math.isclose(angles[0], 90.0, abs_tol=1.0)
    assert _most_bent_knee_angle(angles) == angles[0]
