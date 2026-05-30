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
    # HIP → SHOULDER → WRIST z kamery frontowej:
    # ~170° = ręka pionowo w górę | ~90° = ręka poziomo przed siebie
    left_arm_elevation_deg: float
    right_arm_elevation_deg: float
    wrists_y: float
    elbows_y: float
    eyes_y: float
    forehead_y: float
    shoulders_y: float
    shoulder_width: float


@dataclass(frozen=True, slots=True)
class TechniqueIssue:
    code: str
    message: str


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
    """Metryki z kamery frontowej: łokcie, elewacja ramion, pozycje Y."""
    ls = landmarks[PoseLandmark.LEFT_SHOULDER]
    rs = landmarks[PoseLandmark.RIGHT_SHOULDER]
    le = landmarks[PoseLandmark.LEFT_ELBOW]
    re = landmarks[PoseLandmark.RIGHT_ELBOW]
    lw = landmarks[PoseLandmark.LEFT_WRIST]
    rw = landmarks[PoseLandmark.RIGHT_WRIST]
    lh = landmarks[PoseLandmark.LEFT_HIP]
    rh = landmarks[PoseLandmark.RIGHT_HIP]
    left_eye  = landmarks[PoseLandmark.LEFT_EYE]
    right_eye = landmarks[PoseLandmark.RIGHT_EYE]
    nose      = landmarks[PoseLandmark.NOSE]

    required = [ls, rs, le, re, lw, rw, lh, rh, left_eye, right_eye, nose]
    if not all(_is_visible(p, min_visibility) for p in required):
        return None

    # Kąt przy łokciu: BARK → ŁOKIEĆ → NADGARSTEK
    # Mierzy czy łokieć jest wyprostowany, NIE mierzy kierunku ramienia
    left_elbow  = angle_degrees(_v(ls), _v(le), _v(lw))
    right_elbow = angle_degrees(_v(rs), _v(re), _v(rw))
    if not (math.isfinite(left_elbow) and math.isfinite(right_elbow)):
        return None

    # Kąt elewacji ramienia: BIODRO → BARK → NADGARSTEK
    # ~170° = ręka pionowo w górę | ~90° = ręka poziomo przed siebie
    # To jest jedyna metryka odróżniająca "ręce w górę" od "ręce przed siebie"
    left_elevation  = angle_degrees(_v(lh), _v(ls), _v(lw))
    right_elevation = angle_degrees(_v(rh), _v(rs), _v(rw))
    if not (math.isfinite(left_elevation) and math.isfinite(right_elevation)):
        return None

    shoulder_width = distance(_v(ls), _v(rs))
    wrists_y    = (lw.y + rw.y) / 2.0
    elbows_y    = (le.y + re.y) / 2.0
    shoulders_y = (ls.y + rs.y) / 2.0
    eyes_y      = (left_eye.y + right_eye.y) / 2.0
    forehead_y  = min(eyes_y, nose.y) - 0.025

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
) -> OverheadDetectionResult:
    metrics = compute_front_metrics(landmarks, min_visibility=min_visibility)

    if not metrics:
        return OverheadDetectionResult(
            metrics=None,
            issues=[TechniqueIssue(
                code="low_visibility",
                message="Brak pełnej widoczności kluczowych punktów ciała.",
            )],
            peak_valid=False,
        )

    # ── IDLE: nadgarstki poniżej linii barków ────────────────────────────────
    if metrics.wrists_y >= metrics.shoulders_y:
        return OverheadDetectionResult(
            metrics=metrics,
            issues=[TechniqueIssue(code="idle", message="Czekam na kolejne odbicie")],
            peak_valid=False,
            phase="idle",
        )

    issues: list[TechniqueIssue] = []

    # ── Warunki geometryczne fazy PEAK ───────────────────────────────────────

    # 1. Pozycja Y: dłonie wyraźnie nad czołem
    head_height       = metrics.shoulders_y - metrics.forehead_y
    contact_clearance = max(0.05, 0.5 * head_height)

    hands_above_forehead  = metrics.wrists_y < (metrics.forehead_y - contact_clearance)
    hands_above_eyes      = metrics.wrists_y < (metrics.eyes_y - 0.01)
    hands_above_shoulders = metrics.wrists_y < (metrics.shoulders_y - 0.05)

    # 2. Łokcie blisko głowy (nie przy boku / brodzie)
    elbows_high_enough = metrics.elbows_y < (metrics.forehead_y + 0.08)

    # 3. Wyprost łokcia: obie ręce muszą być wyprostowane (≥ 150°)
    #    Przy zgiętych rękach (bottom/koszyczek) kąt wynosi ~80–110°
    elbows_straight = (
        metrics.left_elbow_angle_deg  >= 150
        and metrics.right_elbow_angle_deg >= 150
    )

    # 4. Elewacja ramion: BIODRO → BARK → NADGARSTEK ≥ 140°
    #    Ręce w górę ~160–175° | Ręce przed siebie ~85–100°
    #    Kąt łokcia NIE rozróżnia tych przypadków — tu był korzeń buga
    ARM_ELEVATION_MIN = 140.0
    arms_elevated = (
        metrics.left_arm_elevation_deg  >= ARM_ELEVATION_MIN
        and metrics.right_arm_elevation_deg >= ARM_ELEVATION_MIN
    )

    is_peak_position = (
        hands_above_forehead
        and hands_above_eyes
        and hands_above_shoulders
        and elbows_high_enough
        and elbows_straight   # wyprost łokcia jako warunek wejścia do peak
        and arms_elevated     # kierunek ramion jako warunek wejścia do peak
    )

    # ── Feedback gdy nie ma peaku ─────────────────────────────────────────────
    if not is_peak_position:
        if not arms_elevated:
            issues.append(TechniqueIssue(
                code="arms_forward",
                message="Wypychasz ręce przed siebie! Unieś je pionowo nad głowę.",
            ))
        else:
            issues.append(TechniqueIssue(
                code="contact_too_low",
                message="Punkt kontaktu jest zbyt nisko. Unieś dłonie nad czoło przed odbiciem.",
            ))

    # ── Kolana (kamera boczna) ────────────────────────────────────────────────
    if side_landmarks is not None:
        side_angles = _side_knee_angles_deg(side_landmarks, min_visibility=0.4)
        knee_angle  = _most_bent_knee_angle(side_angles)
        if knee_angle is None:
            issues.append(TechniqueIssue(
                code="side_low_visibility",
                message="Ustaw kamerę boczną tak, by widać było kolano, biodro i kostkę.",
            ))
        else:
            if is_peak_position and knee_angle < 145:
                issues.append(TechniqueIssue(
                    code="no_legs_drive",
                    message="Wyprostuj kolana przy wypchnięciu piłki (brak wyrzutu z nóg).",
                ))
            elif not is_peak_position and knee_angle >= 145:
                issues.append(TechniqueIssue(
                    code="knees_too_straight",
                    message="Ugnij kolana pod piłką przed odbiciem.",
                ))
    else:
        issues.append(TechniqueIssue(
            code="side_low_visibility",
            message="Brak danych z kamery bocznej — nie mogę ocenić pracy nóg.",
        ))

    # ── Łokcie: wyprost przy peaku, ugięcie przy bottom ──────────────────────
    if is_peak_position:
        if metrics.left_elbow_angle_deg < 150 or metrics.right_elbow_angle_deg < 150:
            issues.append(TechniqueIssue(
                code="elbows_too_bent",
                message="Wyprostuj ręce w łokciach przy wypchnięciu piłki.",
            ))
    else:
        if not arms_elevated:
            issues.append(TechniqueIssue(
                code="arms_not_overhead",
                message="Unieś ręce pionowo nad głowę — nie wystarczy wyciągnąć ich przed siebie.",
            ))
        if metrics.left_elbow_angle_deg > 150 or metrics.right_elbow_angle_deg > 150:
            issues.append(TechniqueIssue(
                code="elbows_too_straight",
                message="Ugnij łokcie przygotowując się do odbicia.",
            ))

    # ── Symetria rąk ─────────────────────────────────────────────────────────
    if abs(metrics.left_elbow_angle_deg - metrics.right_elbow_angle_deg) > 35:
        issues.append(TechniqueIssue(
            code="arm_asymmetry",
            message="Utrzymaj symetrię pracy rąk — oba łokcie powinny prostować się podobnie.",
        ))

    # ── Koszyczek ────────────────────────────────────────────────────────────
    left_wrist  = landmarks[PoseLandmark.LEFT_WRIST]
    right_wrist = landmarks[PoseLandmark.RIGHT_WRIST]
    left_index  = landmarks[PoseLandmark.LEFT_INDEX]
    right_index = landmarks[PoseLandmark.RIGHT_INDEX]

    wrists_dist_x = abs(left_wrist.x - right_wrist.x)
    wrists_diff_y = abs(left_wrist.y - right_wrist.y)

    if wrists_dist_x > metrics.shoulder_width * 0.85 or wrists_diff_y > 0.20:
        issues.append(TechniqueIssue(
            code="bad_hand_position",
            message="Zbliż dłonie do siebie w 'koszyczek' i trzymaj je równo.",
        ))

    if left_index.y > left_wrist.y + 0.02 or right_index.y > right_wrist.y + 0.02:
        issues.append(TechniqueIssue(
            code="closed_fists",
            message="Otwórz dłonie! Palce muszą tworzyć koszyczek, nie zaciskaj pięści.",
        ))

    # ── Debug (wyłączyć na produkcji: ustaw poziom logów na WARNING) ─────────
    logger.debug(
        "wrists_y=%.3f forehead_y=%.3f "
        "L_elbow=%.1f R_elbow=%.1f "
        "L_elev=%.1f R_elev=%.1f "
        "elbows_straight=%s arms_elevated=%s is_peak=%s",
        metrics.wrists_y, metrics.forehead_y,
        metrics.left_elbow_angle_deg, metrics.right_elbow_angle_deg,
        metrics.left_arm_elevation_deg, metrics.right_arm_elevation_deg,
        elbows_straight, arms_elevated, is_peak_position,
    )

    # ── Przypisanie fazy ──────────────────────────────────────────────────────
    if metrics.wrists_y > metrics.shoulders_y:
        phase = "idle"
    elif is_peak_position:
        phase = "peak"
    else:
        phase = "bottom"

    return OverheadDetectionResult(
        metrics=metrics,
        issues=issues,
        peak_valid=False,
        phase=phase,
    )


# Zachowanie kompatybilności wstecznej dla testów / starych wywołań
def compute_overhead_pass_metrics(
    landmarks: list[Landmark],
    *,
    min_visibility: float = 0.2,
) -> FrontMetrics | None:
    return compute_front_metrics(landmarks, min_visibility=min_visibility)
