from __future__ import annotations

from dataclasses import dataclass
import math

from backend.analysis.geometry import Vec3, angle_degrees, distance
from backend.analysis.mediapipe_pose import PoseLandmark
from backend.schemas import Landmark


@dataclass(frozen=True, slots=True)
class FrontMetrics:
    left_elbow_angle_deg: float
    right_elbow_angle_deg: float
    wrists_y: float
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


def _v(lm: Landmark) -> Vec3:
    return Vec3(lm.x, lm.y, lm.z)


def _is_visible(lm: Landmark, min_visibility: float) -> bool:
    return lm.visibility >= min_visibility


def compute_front_metrics(
    landmarks: list[Landmark],
    *,
    min_visibility: float = 0.5,
) -> FrontMetrics | None:
    """Metryki z kamery front: ręce, łokcie, punkt kontaktu (bez kolan)."""
    ls = landmarks[PoseLandmark.LEFT_SHOULDER]
    rs = landmarks[PoseLandmark.RIGHT_SHOULDER]
    le = landmarks[PoseLandmark.LEFT_ELBOW]
    re = landmarks[PoseLandmark.RIGHT_ELBOW]
    lw = landmarks[PoseLandmark.LEFT_WRIST]
    rw = landmarks[PoseLandmark.RIGHT_WRIST]
    left_eye = landmarks[PoseLandmark.LEFT_EYE]
    right_eye = landmarks[PoseLandmark.RIGHT_EYE]
    nose = landmarks[PoseLandmark.NOSE]

    required = [ls, rs, le, re, lw, rw, left_eye, right_eye, nose]
    if not all(_is_visible(p, min_visibility) for p in required):
        return None

    left_elbow = angle_degrees(_v(ls), _v(le), _v(lw))
    right_elbow = angle_degrees(_v(rs), _v(re), _v(rw))
    if not (math.isfinite(left_elbow) and math.isfinite(right_elbow)):
        return None

    shoulder_width = distance(_v(ls), _v(rs))
    wrists_y = (lw.y + rw.y) / 2.0
    shoulders_y = (ls.y + rs.y) / 2.0
    eyes_y = (left_eye.y + right_eye.y) / 2.0
    # Linia czoła: nad oczami (mniejsze Y = wyżej w kadrze)
    forehead_y = min(eyes_y, nose.y) - 0.025

    return FrontMetrics(
        left_elbow_angle_deg=left_elbow,
        right_elbow_angle_deg=right_elbow,
        wrists_y=wrists_y,
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
        (PoseLandmark.LEFT_HIP, PoseLandmark.LEFT_KNEE, PoseLandmark.LEFT_ANKLE),
        (PoseLandmark.RIGHT_HIP, PoseLandmark.RIGHT_KNEE, PoseLandmark.RIGHT_ANKLE),
    )
    angles: list[float] = []
    for hip_i, knee_i, ankle_i in leg_chains:
        hip = side_landmarks[hip_i]
        knee = side_landmarks[knee_i]
        ankle = side_landmarks[ankle_i]
        if not all(_is_visible(p, min_visibility) for p in (hip, knee, ankle)):
            continue
        ang = angle_degrees(_v(hip), _v(knee), _v(ankle))
        if math.isfinite(ang):
            angles.append(ang)
    return angles


def _most_bent_knee_angle(angles: list[float]) -> float | None:
    if not angles:
        return None
    return min(angles)


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
            issues=[
                TechniqueIssue(
                    code="low_visibility",
                    message="Brak pełnej widoczności kluczowych punktów ciała.",
                )
            ],
            peak_valid=False,
        )

    # --- IDLE (front): nadgarstki poniżej linii ramion ---
    if metrics.wrists_y > metrics.shoulders_y:
        return OverheadDetectionResult(
            metrics=metrics,
            issues=[
                TechniqueIssue(
                    code="idle",
                    message="Czekam na kolejne odbicie",
                )
            ],
            peak_valid=False,
        )

    issues: list[TechniqueIssue] = []

    # --- Punkt kontaktu (front): nadgarstki muszą być wyraźnie NAD czołem/oczami ---
    contact_clearance = max(0.02, 0.08 * metrics.shoulder_width)
    hands_above_forehead = metrics.wrists_y < (metrics.forehead_y - contact_clearance)
    hands_above_eyes = metrics.wrists_y < (metrics.eyes_y - 0.01)
    hands_above_shoulders = metrics.wrists_y < (metrics.shoulders_y - 0.05)

    if not (hands_above_forehead and hands_above_eyes and hands_above_shoulders):
        issues.append(
            TechniqueIssue(
                code="contact_too_low",
                message="Punkt kontaktu jest zbyt nisko. Unieś dłonie nad czoło przed odbiciem.",
            )
        )

    # --- Kolana (bok): lekko ugięte; proste kolana = brak pracy nóg ---
    knee_angle: float | None = None
    if side_landmarks is not None:
        side_angles = _side_knee_angles_deg(side_landmarks, min_visibility=0.4)
        knee_angle = _most_bent_knee_angle(side_angles)
        if knee_angle is None:
            issues.append(
                TechniqueIssue(
                    code="side_low_visibility",
                    message="Ustaw kamerę boczną tak, by widać było kolano, biodro i kostkę.",
                )
            )
        elif knee_angle > 165:
            issues.append(
                TechniqueIssue(
                    code="no_legs_drive",
                    message="Pracuj nogami: ugnij kolana i wypchnij piłkę z nóg, nie samymi rękami.",
                )
            )
    else:
        issues.append(
            TechniqueIssue(
                code="side_low_visibility",
                message="Brak danych z kamery bocznej — nie mogę ocenić pracy nóg.",
            )
        )

    # --- Łokcie / symetria (front) ---
    if metrics.left_elbow_angle_deg < 150 or metrics.right_elbow_angle_deg < 150:
        issues.append(
            TechniqueIssue(
                code="elbows_too_bent",
                message="Wyprostuj łokcie podczas wypchnięcia — ruch powinien być płynny i symetryczny.",
            )
        )

    if abs(metrics.left_elbow_angle_deg - metrics.right_elbow_angle_deg) > 20:
        issues.append(
            TechniqueIssue(
                code="arm_asymmetry",
                message="Utrzymaj symetrię pracy rąk — oba łokcie powinny prostować się podobnie.",
            )
        )

    # --- Koszyczek (front, nadgarstki) ---
    left_wrist = landmarks[PoseLandmark.LEFT_WRIST]
    right_wrist = landmarks[PoseLandmark.RIGHT_WRIST]
    wrists_dist_x = abs(left_wrist.x - right_wrist.x)
    wrists_diff_y = abs(left_wrist.y - right_wrist.y)

    if wrists_dist_x > metrics.shoulder_width * 0.8 or wrists_diff_y > 0.1:
        issues.append(
            TechniqueIssue(
                code="bad_hand_position",
                message="Zbliż dłonie do siebie i trzymaj je równo nad czołem",
            )
        )

    # Szczyt repa: wysokie dłonie + lekko ugięte kolana (bok) + brak innych błędów technicznych
    knees_bent_ok = knee_angle is not None and 115 <= knee_angle <= 165
    technical_issue_codes = {
        "contact_too_low",
        "no_legs_drive",
        "elbows_too_bent",
        "arm_asymmetry",
        "bad_hand_position",
    }
    has_technical_error = any(i.code in technical_issue_codes for i in issues)
    peak_valid = (
        hands_above_forehead
        and hands_above_eyes
        and hands_above_shoulders
        and knees_bent_ok
        and not has_technical_error
    )

    return OverheadDetectionResult(metrics=metrics, issues=issues, peak_valid=peak_valid)


# Zachowanie kompatybilności wstecznej dla testów / starych wywołań
def compute_overhead_pass_metrics(
    landmarks: list[Landmark],
    *,
    min_visibility: float = 0.5,
) -> FrontMetrics | None:
    return compute_front_metrics(landmarks, min_visibility=min_visibility)
