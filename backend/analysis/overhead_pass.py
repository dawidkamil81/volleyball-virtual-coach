from __future__ import annotations

from dataclasses import dataclass
import math

from backend.analysis.geometry import Vec3, angle_degrees, distance
from backend.analysis.mediapipe_pose import PoseLandmark
from backend.schemas import Landmark

import logging
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FrontMetrics:
    left_elbow_angle_deg: float
    right_elbow_angle_deg: float
    left_arm_elevation_deg: float
    right_arm_elevation_deg: float
    wrists_y: float
    elbows_y: float
    eyes_y: float
    forehead_y: float
    shoulders_y: float
    shoulder_width: float
    # NOWE METRYKI DO KOSZYCZKA
    elbows_dist_x: float
    index_fingers_dist_2d: float
    thumbs_dist_2d: float


@dataclass(frozen=True, slots=True)
class TechniqueIssue:
    code: str
    message: str

@dataclass
class SessionState:
    bottom_perfect: bool = False
    peak_reached: bool = False


@dataclass(frozen=True, slots=True)
class OverheadDetectionResult:
    metrics: FrontMetrics | None
    issues: list[TechniqueIssue]
    peak_valid: bool
    phase: str = "idle"  # "idle" | "bottom" | "peak"


def _v(lm: Landmark) -> Vec3:
    return Vec3(lm.x, lm.y, lm.z)


def _is_visible(lm: Landmark, min_visibility: float) -> bool:
    return lm.visibility >= min_visibility


def compute_front_metrics(
    landmarks: list[Landmark],
    *,
    min_visibility: float = 0.5,
) -> FrontMetrics | None:
    ls = landmarks[PoseLandmark.LEFT_SHOULDER]
    rs = landmarks[PoseLandmark.RIGHT_SHOULDER]
    le = landmarks[PoseLandmark.LEFT_ELBOW]
    re = landmarks[PoseLandmark.RIGHT_ELBOW]
    lw = landmarks[PoseLandmark.LEFT_WRIST]
    rw = landmarks[PoseLandmark.RIGHT_WRIST]
    lh = landmarks[PoseLandmark.LEFT_HIP]
    rh = landmarks[PoseLandmark.RIGHT_HIP]
    left_eye = landmarks[PoseLandmark.LEFT_EYE]
    right_eye = landmarks[PoseLandmark.RIGHT_EYE]
    nose = landmarks[PoseLandmark.NOSE]
    
    # Dodatkowe punkty dłoni
    left_index = landmarks[PoseLandmark.LEFT_INDEX]
    right_index = landmarks[PoseLandmark.RIGHT_INDEX]
    left_thumb = landmarks[PoseLandmark.LEFT_THUMB]
    right_thumb = landmarks[PoseLandmark.RIGHT_THUMB]

    required = [ls, rs, le, re, lw, rw, lh, rh, left_eye, right_eye, nose, left_index, right_index, left_thumb, right_thumb]
    if not all(_is_visible(p, min_visibility) for p in required):
        return None

    left_elbow = angle_degrees(_v(ls), _v(le), _v(lw))
    right_elbow = angle_degrees(_v(rs), _v(re), _v(rw))
    if not (math.isfinite(left_elbow) and math.isfinite(right_elbow)):
        return None

    left_elevation = angle_degrees(_v(lh), _v(ls), _v(lw))
    right_elevation = angle_degrees(_v(rh), _v(rs), _v(rw))
    if not (math.isfinite(left_elevation) and math.isfinite(right_elevation)):
        return None

    shoulder_width = distance(_v(ls), _v(rs))
    wrists_y = (lw.y + rw.y) / 2.0
    elbows_y = (le.y + re.y) / 2.0
    shoulders_y = (ls.y + rs.y) / 2.0
    eyes_y = (left_eye.y + right_eye.y) / 2.0
    forehead_y = min(eyes_y, nose.y) - 0.025

    # OBLICZENIA KOSZYCZKA
    elbows_dist_x = abs(le.x - re.x)
    index_dist = math.hypot(left_index.x - right_index.x, left_index.y - right_index.y)
    thumbs_dist = math.hypot(left_thumb.x - right_thumb.x, left_thumb.y - right_thumb.y)

    return FrontMetrics(
        left_elbow_angle_deg=left_elbow,
        right_elbow_angle_deg=right_elbow,
        left_arm_elevation_deg=left_elevation,
        right_arm_elevation_deg=right_elevation,
        wrists_y=wrists_y,
        elbows_y=elbows_y,
        eyes_y=eyes_y,
        forehead_y=forehead_y,
        shoulders_y=shoulders_y,
        shoulder_width=shoulder_width,
        elbows_dist_x=elbows_dist_x,
        index_fingers_dist_2d=index_dist,
        thumbs_dist_2d=thumbs_dist,
    )


def _side_knee_angles_deg(
    side_landmarks: list[Landmark],
    *,
    min_visibility: float = 0.4,
) -> list[float]:
    """Kąty kolan z kamery bocznej — widok profilu daje wiarygodniejszy pomiar."""
    leg_chains = (
        (PoseLandmark.LEFT_HIP,  PoseLandmark.LEFT_KNEE,  PoseLandmark.LEFT_ANKLE),
        (PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_KNEE, PoseLandmark.RIGHT_ANKLE),
    )
    angles: list[float] = []
    for hip_i, knee_i, ankle_i in leg_chains:
        hip   = side_landmarks[hip_i]
        knee  = side_landmarks[knee_i]
        ankle = side_landmarks[ankle_i]
        if not all(_is_visible(p, min_visibility) for p in (hip, knee, ankle)):
            continue
        ang = angle_degrees(_v(hip), _v(knee), _v(ankle))
        if math.isfinite(ang):
            angles.append(ang)
    return angles


def _most_bent_knee_angle(angles: list[float]) -> float | None:
    return min(angles) if angles else None


def detect_overhead_pass_issues(
    landmarks: list[Landmark],
    side_landmarks: list[Landmark] | None = None,
    *,
    min_visibility: float = 0.5,
    state: SessionState | None = None,
) -> OverheadDetectionResult:
    # Zabezpieczenie dla środowisk bezstanowych
    if state is None:
        state = SessionState()

    metrics = compute_front_metrics(landmarks, min_visibility=min_visibility)

    if not metrics:
        return OverheadDetectionResult(
            metrics=None,
            issues=[TechniqueIssue(code="low_visibility", message="Brak pełnej widoczności kluczowych punktów ciała.")],
            peak_valid=False,
            phase="idle"
        )

    # ── IDLE ─────────────────────────────────────────────────────────
    hands_raised = metrics.wrists_y < metrics.shoulders_y
    if not hands_raised:
        # Twardy reset pamięci po opuszczeniu rąk
        state.bottom_perfect = False
        state.peak_reached = False
        return OverheadDetectionResult(
            metrics=metrics,
            issues=[TechniqueIssue(code="idle", message="Czekam na uniesienie dłoni.")],
            peak_valid=False,
            phase="idle",
        )

    issues: list[TechniqueIssue] = []

    # ── WYLICZENIE KIERUNKU RAMION I KOSZYCZKA ───────────────────────────────
    vertical_reach = metrics.shoulders_y - metrics.wrists_y
    ARM_ELEVATION_MIN = 125.0
    arms_elevated = False

    if side_landmarks is not None:
        side_arm_angles = _side_arm_elevation_angles_deg(side_landmarks, min_visibility=0.4)
        if side_arm_angles:
            arms_elevated = all(angle >= ARM_ELEVATION_MIN for angle in side_arm_angles)
        else:
            arms_elevated = vertical_reach > (metrics.shoulder_width * 0.85)
    else:
        arms_elevated = vertical_reach > (metrics.shoulder_width * 0.85)

    max_finger_gap = metrics.shoulder_width * 0.40
    basket_broken = (metrics.index_fingers_dist_2d > max_finger_gap or metrics.thumbs_dist_2d > max_finger_gap)
    elbows_flared = metrics.elbows_dist_x > (metrics.shoulder_width * 1.85)

    # ── SPRAWDZANIE BŁĘDÓW POZYCJI STARTOWEJ (BOTTOM) ────────────────────────
    bottom_issues: list[TechniqueIssue] = []
    
    if side_landmarks is not None:
        side_angles = _side_knee_angles_deg(side_landmarks, min_visibility=0.4)
        knee_angle = _most_bent_knee_angle(side_angles)
        if knee_angle is None:
            bottom_issues.append(TechniqueIssue(code="side_low_visibility", message="Ustaw kamerę boczną tak, by widać było kolano i biodro."))
        elif knee_angle >= 145:
            bottom_issues.append(TechniqueIssue(code="knees_too_straight", message="Ugnij kolana pod piłką przed odbiciem."))
    else:
        bottom_issues.append(TechniqueIssue(code="side_low_visibility", message="Brak danych z kamery bocznej."))

    if not arms_elevated and metrics.wrists_y > metrics.forehead_y:
        bottom_issues.append(TechniqueIssue(code="arms_not_overhead", message="Szykujesz ręce przed klatką. Przenieś dłonie nad czoło."))
        
    if metrics.left_elbow_angle_deg > 145 or metrics.right_elbow_angle_deg > 145:
        bottom_issues.append(TechniqueIssue(code="elbows_too_straight", message="Ręce za proste! Ugnij łokcie przygotowując się do odbicia."))

    if elbows_flared:
        bottom_issues.append(TechniqueIssue(code="elbows_flared", message="Schowaj łokcie! Są rozstawione za szeroko (skrzydełka)."))
    
    if basket_broken:
        bottom_issues.append(TechniqueIssue(code="basket_broken", message="Złącz kciuki i palce wskazujące w trójkąt."))

    left_wrist = landmarks[PoseLandmark.LEFT_WRIST]
    right_wrist = landmarks[PoseLandmark.RIGHT_WRIST]
    left_index = landmarks[PoseLandmark.LEFT_INDEX]
    right_index = landmarks[PoseLandmark.RIGHT_INDEX]
    
    if left_index.y > left_wrist.y + 0.02 or right_index.y > right_wrist.y + 0.02:
        bottom_issues.append(TechniqueIssue(code="closed_fists", message="Otwórz dłonie! Nie zaciskaj pięści."))

    # ── AKTUALIZACJA PAMIĘCI STANU (ZAMROŻENIE W TRAKCIE WYRZUTU) ────────────
    # Gdy gracz zaczyna wyrzut (łokcie > 145), przestajemy oceniać ugięcie, 
    # bazując na tym czy przed ułamkiem sekundy wszystko było idealnie.
    is_initiating_push = metrics.left_elbow_angle_deg > 145 and metrics.right_elbow_angle_deg > 145
    
    if not is_initiating_push:
        state.bottom_perfect = (len(bottom_issues) == 0)

    # ── MASZYNA STANÓW (Z TWARDĄ BLOKADĄ CAŁEGO BOTTOM) ──────────────────────
    avg_elbow_angle = (metrics.left_elbow_angle_deg + metrics.right_elbow_angle_deg) / 2.0
    arms_extended_angle = avg_elbow_angle > 155.0
    arms_extended_up_2d = vertical_reach > (metrics.shoulder_width * 1.3)
    head_height = metrics.shoulders_y - metrics.forehead_y
    hands_high_enough = metrics.wrists_y < (metrics.forehead_y - head_height * 0.3)

    is_pushing = (arms_extended_angle or arms_extended_up_2d) and hands_high_enough
    
    if is_pushing:
        if not state.bottom_perfect:
            # Gracz robi wypchnięcie, ale pozycja startowa miała błędy! Blokujemy.
            phase = "bottom"
            issues.append(TechniqueIssue(
                code="bottom_block",
                message="⛔ ZABLOKOWANO! Przyjmij i zatrzymaj idealną pozycję przed wyrzutem."
            ))
            issues.extend(bottom_issues)
        else:
            phase = "peak"
            state.peak_reached = True
    else:
        phase = "bottom"
        if state.peak_reached:
            # Skończył poprzedni wyrzut, musi od nowa ułożyć idealny bottom
            state.bottom_perfect = False
            state.peak_reached = False
        issues.extend(bottom_issues)

    # ── OCENA TECHNIKI W FAZIE PEAK ──────────────────────────────────────────
    if phase == "peak":
        if not arms_elevated:
            issues.append(TechniqueIssue(code="arms_forward", message="Wypychasz ręce przed siebie! Skieruj wyrzut bardziej w górę."))
        
        if metrics.left_elbow_angle_deg < 130 or metrics.right_elbow_angle_deg < 130:
            issues.append(TechniqueIssue(code="elbows_too_bent", message="Dokończ wyprost rąk przy wypchnięciu piłki."))
            
        if side_landmarks is not None:
            side_angles = _side_knee_angles_deg(side_landmarks, min_visibility=0.4)
            knee_angle = _most_bent_knee_angle(side_angles)
            if knee_angle is not None and knee_angle < 135:
                issues.append(TechniqueIssue(code="no_legs_drive", message="Wyprostuj kolana przy wypchnięciu piłki."))

    # 3. Symetria rąk (poza idle)
    if abs(metrics.left_elbow_angle_deg - metrics.right_elbow_angle_deg) > 35:
        issues.append(TechniqueIssue(code="arm_asymmetry", message="Oba łokcie powinny prostować się podobnie."))

    # ── WALIDACJA POWTÓRZENIA ────────────────────────────────────────────────
    is_valid_rep = False
    if phase == "peak":
        blocking_issues = [i for i in issues if i.code != "arms_forward"]
        if not blocking_issues:
            is_valid_rep = True

    return OverheadDetectionResult(
        metrics=metrics,
        issues=issues,
        peak_valid=is_valid_rep,
        phase=phase,
    )

# Zachowanie kompatybilności wstecznej dla testów / starych wywołań
def compute_overhead_pass_metrics(
    landmarks: list[Landmark],
    *,
    min_visibility: float = 0.2,
) -> FrontMetrics | None:
    return compute_front_metrics(landmarks, min_visibility=min_visibility)

def _side_arm_elevation_angles_deg(
    side_landmarks: list[Landmark],
    *,
    min_visibility: float = 0.4,
) -> list[float]:
    """Kąty elewacji ramion z kamery bocznej (BIODRO → BARK → NADGARSTEK).
    Z boku idealnie widać czy ręce są w górze (~170°) czy z przodu (~90°)."""
    arm_chains = (
        (PoseLandmark.LEFT_HIP,  PoseLandmark.LEFT_SHOULDER,  PoseLandmark.LEFT_WRIST),
        (PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_SHOULDER, PoseLandmark.RIGHT_WRIST),
    )
    angles: list[float] = []
    for hip_i, shoulder_i, wrist_i in arm_chains:
        hip      = side_landmarks[hip_i]
        shoulder = side_landmarks[shoulder_i]
        wrist    = side_landmarks[wrist_i]
        
        if not all(_is_visible(p, min_visibility) for p in (hip, shoulder, wrist)):
            continue
            
        ang = angle_degrees(_v(hip), _v(shoulder), _v(wrist))
        if math.isfinite(ang):
            angles.append(ang)
            
    return angles
