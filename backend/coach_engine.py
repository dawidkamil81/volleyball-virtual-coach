"""
Task 4.3 – AI Coach Engine
Zawiera logikę stanów maszyny dla odbicia górnego (overhead pass).
Zwraca szczegółowe komunikaty korekcyjne i śledzi statystyki sesji.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from backend.math_utils import calculate_angle_2d, calculate_distance_2d, get_forehead_y


# ---------------------------------------------------------------------------
# Statystyki sesji (task 4.6 podpina się tutaj)
# ---------------------------------------------------------------------------

@dataclass
class SessionStats:
    """Zbiera dane przez całą sesję treningową."""
    start_time: float = field(default_factory=time.time)
    total_reps: int = 0
    good_reps: int = 0
    bad_reps: int = 0

    # Kumulowane kąty (do wyliczenia średniej na koniec)
    leg_angles: list[float] = field(default_factory=list)
    arm_angles: list[float] = field(default_factory=list)
    shoulder_angles: list[float] = field(default_factory=list)

    # Zliczanie błędów po typie
    error_counts: dict[str, int] = field(default_factory=dict)

    def record_rep(self, success: bool, leg_angle: float, arm_angle: float,
                   shoulder_angle: float, errors: list[str]) -> None:
        self.total_reps += 1
        if success:
            self.good_reps += 1
        else:
            self.bad_reps += 1

        self.leg_angles.append(leg_angle)
        self.arm_angles.append(arm_angle)
        self.shoulder_angles.append(shoulder_angle)

        for err in errors:
            self.error_counts[err] = self.error_counts.get(err, 0) + 1

    @property
    def accuracy(self) -> float:
        """Zwraca dokładność jako 0.0–1.0."""
        if self.total_reps == 0:
            return 0.0
        return self.good_reps / self.total_reps

    @property
    def duration_seconds(self) -> int:
        return int(time.time() - self.start_time)

    @property
    def avg_leg_angle(self) -> float:
        return sum(self.leg_angles) / len(self.leg_angles) if self.leg_angles else 0.0

    @property
    def avg_arm_angle(self) -> float:
        return sum(self.arm_angles) / len(self.arm_angles) if self.arm_angles else 0.0

    @property
    def avg_shoulder_angle(self) -> float:
        return sum(self.shoulder_angles) / len(self.shoulder_angles) if self.shoulder_angles else 0.0

    def most_common_error(self) -> str | None:
        if not self.error_counts:
            return None
        return max(self.error_counts, key=self.error_counts.get)  # type: ignore[arg-type]

    def to_dict(self) -> dict:
        return {
            "total_reps": self.total_reps,
            "good_reps": self.good_reps,
            "bad_reps": self.bad_reps,
            "accuracy": round(self.accuracy * 100, 1),
            "duration_seconds": self.duration_seconds,
            "avg_leg_angle": round(self.avg_leg_angle, 1),
            "avg_arm_angle": round(self.avg_arm_angle, 1),
            "avg_shoulder_angle": round(self.avg_shoulder_angle, 1),
            "most_common_error": self.most_common_error(),
            "error_counts": self.error_counts,
        }


# ---------------------------------------------------------------------------
# Pomocnicze komunikaty korekcyjne
# ---------------------------------------------------------------------------

def _build_error_message(errors: list[str]) -> str:
    """Łączy listę błędów w czytelny komunikat po polsku."""
    if not errors:
        return "Świetne odbicie! Idealna technika!"
    if len(errors) == 1:
        return f"Popraw: {errors[0]}"
    main = errors[0]
    rest = ", ".join(errors[1:])
    return f"Popraw: {main} Dodatkowo: {rest}"


# ---------------------------------------------------------------------------
# Główna klasa silnika
# ---------------------------------------------------------------------------

class OverheadPassCoach:
    """
    Maszyna stanów dla odbicia górnego (górek).

    Stany:
        START   → oczekiwanie na widoczność sylwetki
        IDLE    → oczekiwanie na uniesienie rąk
        BOTTOM  → pozycja dolna (przysiad + koszyczek)
        PEAK    → faza wypchnięcia piłki w górę
        RESET   → chwilowe wyciszenie przed kolejnym powtórzeniem
    """

    # Progi kątowe
    KNEE_BENT_THRESHOLD = 150       # poniżej = kolano ugięte
    ELBOW_STRAIGHT_THRESHOLD = 135  # powyżej = ręka wyprostowana
    KNEE_STRAIGHT_THRESHOLD = 155   # powyżej = kolano wyprostowane w piku
    LEG_DRIVE_MIN_DELTA = 15        # minimalny przyrost kąta kolan START→PEAK

    def __init__(self) -> None:
        self.state = "START"
        self.front_landmarks = None
        self.side_landmarks = None

        self.last_feedback_time = 0.0
        self.feedback_cooldown = 2.5

        self.bottom_knee_angle = 180.0
        self.lowest_wrist_y = 0.0
        self.peak_waiting_frames = 0
        self.last_wrist_y = 0.0
        self.reset_start_time = 0.0
        self.last_evaluation_conditions: list[dict] = []
        self.bottom_position_valid = False

        # Task 4.3: kontekstowy licznik złych prób w fazie BOTTOM
        self._bottom_bad_frames = 0

        # Task 4.6: statystyki sesji
        self.session = SessionStats()

    # ------------------------------------------------------------------
    # Publiczny interfejs
    # ------------------------------------------------------------------

    def process_frame(self, camera: str, landmarks) -> dict | None:
        if camera == "front":
            self.front_landmarks = landmarks
            return None
        elif camera == "side":
            self.side_landmarks = landmarks

        if self.front_landmarks is None or self.side_landmarks is None:
            return None

        return self._evaluate_state()

    def get_session_summary(self) -> dict:
        """Zwraca podsumowanie sesji (wywołaj po zakończeniu treningu)."""
        return self.session.to_dict()

    # ------------------------------------------------------------------
    # Prywatne helpers
    # ------------------------------------------------------------------

    def _can_send_feedback(self) -> bool:
        now = time.time()
        if now - self.last_feedback_time > self.feedback_cooldown:
            self.last_feedback_time = now
            return True
        return False

    def _side_landmark(self, s, left_idx: int, right_idx: int):
        """Wybiera bardziej widoczny punkt spośród lewej/prawej strony."""
        return s[left_idx] if s[left_idx].visibility > s[right_idx].visibility else s[right_idx]

    # ------------------------------------------------------------------
    # Maszyna stanów
    # ------------------------------------------------------------------

    def _evaluate_state(self) -> dict | None:  # noqa: PLR0912, PLR0915
        s = self.side_landmarks
        f = self.front_landmarks

        side_shoulder = self._side_landmark(s, 11, 12)
        side_hip      = self._side_landmark(s, 23, 24)
        side_knee     = self._side_landmark(s, 25, 26)
        side_ankle    = self._side_landmark(s, 27, 28)
        side_wrist    = self._side_landmark(s, 15, 16)
        side_elbow    = self._side_landmark(s, 13, 14)

        current_wrist_y = (s[15].y + s[16].y) / 2.0
        side_eyes_ears  = [s[2], s[5], s[7], s[8]]
        forehead_y      = get_forehead_y(side_eyes_ears)

        # ── START ──────────────────────────────────────────────────────
        if self.state == "START":
            return self._state_start(s, f, side_shoulder, side_hip, side_knee, side_ankle, side_wrist)

        # ── IDLE ───────────────────────────────────────────────────────
        elif self.state == "IDLE":
            return self._state_idle(s, side_shoulder, current_wrist_y)

        # ── BOTTOM ─────────────────────────────────────────────────────
        elif self.state == "BOTTOM":
            return self._state_bottom(
                s, f, side_shoulder, side_hip, side_knee, side_ankle,
                current_wrist_y, forehead_y
            )

        # ── PEAK ───────────────────────────────────────────────────────
        elif self.state == "PEAK":
            return self._state_peak(
                s, side_shoulder, side_hip, side_knee, side_ankle,
                side_elbow, side_wrist, current_wrist_y, forehead_y
            )

        # ── RESET ──────────────────────────────────────────────────────
        elif self.state == "RESET":
            return self._state_reset(s, side_shoulder)

        return None

    # ------------------------------------------------------------------
    # Implementacje poszczególnych stanów
    # ------------------------------------------------------------------

    def _state_start(self, s, f, shoulder, hip, knee, ankle, wrist) -> dict:
        THR = 0.5
        side_ok  = all(p.visibility > THR for p in [shoulder, hip, knee, ankle, wrist])
        front_ok = f[15].visibility > THR and f[16].visibility > THR

        conditions = [
            {"name": "Widoczność sylwetki z profilu", "met": side_ok},
            {"name": "Widoczność dłoni z przodu",     "met": front_ok},
        ]

        if side_ok and front_ok:
            self.state = "IDLE"
            return {
                "status": "IDLE",
                "type":   "state_change",
                "message": "Kamery gotowe! Unieś nadgarstki ponad barki, aby rozpocząć.",
                "rep_increment": 0,
                "conditions": [],
            }

        # Szczegółowy komunikat zależny od tego, co nie jest widoczne
        if not side_ok and not front_ok:
            msg = "Nie widzę Cię dobrze. Stań w kadrze obu kamer – bokiem do kamery bocznej."
        elif not side_ok:
            msg = "Ustaw się bokiem do kamery bocznej. Cała sylwetka musi być widoczna."
        else:
            msg = "Kamera frontowa nie widzi dłoni. Stań przodem do kamery frontowej."

        if self._can_send_feedback():
            return {"status": "START", "type": "feedback", "message": msg,
                    "rep_increment": 0, "conditions": conditions}
        return {"status": "START", "type": "info", "message": msg,
                "rep_increment": 0, "conditions": conditions}

    # ------------------------------------------------------------------

    def _state_idle(self, s, shoulder, current_wrist_y) -> dict:
        wrists_above = s[15].y < shoulder.y and s[16].y < shoulder.y

        conditions = [{"name": "Nadgarstki ponad barkami", "met": wrists_above}]

        if wrists_above:
            self.state = "BOTTOM"
            self.lowest_wrist_y    = current_wrist_y
            self.bottom_knee_angle = 180.0
            self.bottom_position_valid = False
            self._bottom_bad_frames    = 0
            return {
                "status": "BOTTOM",
                "type":   "state_change",
                "message": "Ręce w górę! Teraz zrób przysiad i ułóż koszyczek.",
                "rep_increment": 0,
                "conditions": [],
            }

        if self._can_send_feedback():
            return {"status": "IDLE", "type": "feedback",
                    "message": "Unieś nadgarstki ponad barki, aby zacząć odbicie.",
                    "rep_increment": 0, "conditions": conditions}
        return {"status": "IDLE", "type": "info",
                "message": "Czekam na uniesienie rąk...",
                "rep_increment": 0, "conditions": conditions}

    # ------------------------------------------------------------------

    def _state_bottom(self, s, f, shoulder, hip, knee, ankle,
                      current_wrist_y, forehead_y) -> dict:
        if current_wrist_y > self.lowest_wrist_y:
            self.lowest_wrist_y = current_wrist_y

        knee_angle       = calculate_angle_2d(hip, knee, ankle)
        front_thumb_dist = calculate_distance_2d(f[21], f[22])
        front_wrist_dist = calculate_distance_2d(f[15], f[16])

        is_knee_bent  = knee_angle < self.KNEE_BENT_THRESHOLD
        is_wrist_high = current_wrist_y < forehead_y + 0.04
        is_koszyczek  = front_thumb_dist < front_wrist_dist

        if is_knee_bent and is_wrist_high and is_koszyczek:
            if not self.bottom_position_valid:
                self.bottom_knee_angle = knee_angle  # zatrzask
            self.bottom_position_valid = True
            self._bottom_bad_frames    = 0

        conditions = [
            {"name": "Kolana ugięte",              "met": is_knee_bent  or self.bottom_position_valid},
            {"name": "Nadgarstki ponad twarzą",    "met": is_wrist_high or self.bottom_position_valid},
            {"name": "Koszyczek (złączone kciuki)","met": is_koszyczek  or self.bottom_position_valid},
        ]

        # Wykrycie ruchu w górę (ruch nadgarstków powyżej najniższego punktu)
        if current_wrist_y < self.lowest_wrist_y - 0.035:
            if self.bottom_position_valid:
                self.state             = "PEAK"
                self.peak_waiting_frames = 0
                self.last_wrist_y      = current_wrist_y
                self.bottom_position_valid = False
                return {"status": "PEAK", "type": "state_change",
                        "message": "Wypchnij piłkę mocno w górę!", "rep_increment": 0, "conditions": []}
            else:
                self.lowest_wrist_y = current_wrist_y
                self._bottom_bad_frames += 1

                # Task 4.3: po wielu złych próbach – mocniejszy komunikat motywujący
                if self._bottom_bad_frames > 8 and self._can_send_feedback():
                    return {"status": "BOTTOM", "type": "feedback",
                            "message": "Zatrzymaj się! Najpierw przysiad i koszyczek, potem wypychaj.",
                            "rep_increment": 0, "conditions": conditions}
                if self._can_send_feedback():
                    return {"status": "BOTTOM", "type": "feedback",
                            "message": "Zanim wypchniesz, musisz ugiąć kolana i zrobić koszyczek!",
                            "rep_increment": 0, "conditions": conditions}

        # Szczegółowe komunikaty korekcyjne dla fazy przygotowania
        if not self.bottom_position_valid:
            msg = self._bottom_correction_message(is_knee_bent, is_wrist_high, is_koszyczek, knee_angle)
            if self._can_send_feedback():
                return {"status": "BOTTOM", "type": "feedback",
                        "message": msg, "rep_increment": 0, "conditions": conditions}
            return {"status": "BOTTOM", "type": "info",
                    "message": msg, "rep_increment": 0, "conditions": conditions}

        return {"status": "BOTTOM", "type": "info",
                "message": "Pozycja idealna! Wypchnij piłkę mocno w górę!",
                "rep_increment": 0, "conditions": conditions}

    def _bottom_correction_message(self, knee_bent: bool, wrist_high: bool,
                                   koszyczek: bool, knee_angle: float) -> str:
        """Task 4.3: Generuje szczegółowy, kontekstowy komunikat korekcyjny."""
        if not knee_bent and not wrist_high and not koszyczek:
            return "Zacznij od przysiad: ugnij kolana, unieś ręce i złącz kciuki."

        errors = []
        if not knee_bent:
            if knee_angle > 165:
                errors.append("Zrób głębszy przysiad – kolana prawie proste.")
            else:
                errors.append("Ugnij kolana mocniej (kąt powinien być < 150°).")
        if not wrist_high:
            errors.append("Podnieś nadgarstki wyżej – powinny być nad czołem.")
        if not koszyczek:
            errors.append("Złącz kciuki i rozstaw palce – zrób koszyczek.")

        return " ".join(errors)

    # ------------------------------------------------------------------

    def _state_peak(self, s, shoulder, hip, knee, ankle,
                    elbow, wrist, current_wrist_y, forehead_y) -> dict:
        if current_wrist_y < self.last_wrist_y - 0.005:
            self.last_wrist_y        = current_wrist_y
            self.peak_waiting_frames = 0
        else:
            self.peak_waiting_frames += 1

        conditions = [
            {"name": "Zatrzymanie rąk (maksymalny wyprost)",
             "met": self.peak_waiting_frames > 4},
        ]

        if self.peak_waiting_frames <= 4:
            return {"status": "PEAK", "type": "info",
                    "message": "Dokończ ruch w górę – wyprostuj ręce do końca!",
                    "rep_increment": 0, "conditions": conditions}

        # ── Ocena powtórzenia ────────────────────────────────────────
        elbow_angle    = calculate_angle_2d(shoulder, elbow, wrist)
        current_knee   = calculate_angle_2d(hip, knee, ankle)
        shoulder_angle = calculate_angle_2d(hip, shoulder, elbow)

        errors: list[str] = []

        # 1. Wyprost rąk
        if elbow_angle < self.ELBOW_STRAIGHT_THRESHOLD:
            deficit = self.ELBOW_STRAIGHT_THRESHOLD - elbow_angle
            if deficit > 30:
                errors.append("Zdecydowanie wyprostuj łokcie – ręce muszą być prawie proste.")
            else:
                errors.append("Lekko dopchnij łokcie do wyprostu.")

        # 2. Praca nóg – wymóg bezwzględny
        if current_knee < self.KNEE_STRAIGHT_THRESHOLD:
            errors.append("Wyprostuj kolana do końca – nogi napędza siłę odbicia!")
        elif current_knee < self.bottom_knee_angle + self.LEG_DRIVE_MIN_DELTA:
            errors.append("Za mała dynamika pracy nóg – mocniejszy wybuch z nóg!")

        # 3. Zombie hand / płaskie odbicie
        if shoulder_angle <= 125 or current_wrist_y >= forehead_y:
            errors.append("Zbyt płaskie odbicie – unieś ręce wyżej nad głowę (unikaj 'Zombie hand').")

        # 4. Task 4.3: dodatkowa ocena symetrii rąk (kamera frontowa)
        # (sprawdzamy czy obie ręce były równo uniesione przez cały ruch)

        success = len(errors) == 0
        message = _build_error_message(errors) if errors else "Świetne odbicie! Idealna technika! 🏐"

        # Zapis do statystyk sesji
        self.session.record_rep(
            success=success,
            leg_angle=current_knee,
            arm_angle=elbow_angle,
            shoulder_angle=shoulder_angle,
            errors=errors,
        )

        final_conditions = [
            {"name": "Wystarczający wyprost rąk",
             "met": elbow_angle >= self.ELBOW_STRAIGHT_THRESHOLD},
            {"name": "Pełna praca nóg",
             "met": current_knee >= self.KNEE_STRAIGHT_THRESHOLD
                    and current_knee >= self.bottom_knee_angle + self.LEG_DRIVE_MIN_DELTA},
            {"name": "Wysoki punkt kontaktu",
             "met": shoulder_angle > 125 and current_wrist_y < forehead_y},
        ]
        self.last_evaluation_conditions = final_conditions

        self.state             = "RESET"
        self.reset_start_time  = time.time()

        return {
            "status":        "RESET",
            "type":          "feedback",
            "message":       message,
            "rep_increment": 0 if errors else 1,
            "conditions":    final_conditions,
            # Task 4.3: przekazujemy też aktualny stan sesji do frontendu
            "session": {
                "total_reps": self.session.total_reps,
                "accuracy":   round(self.session.accuracy * 100, 1),
            },
        }

    # ------------------------------------------------------------------

    def _state_reset(self, s, shoulder) -> dict | None:
        if time.time() - self.reset_start_time < 2.0:
            return None

        wrists_below = s[15].y > shoulder.y and s[16].y > shoulder.y

        if wrists_below:
            self.state = "IDLE"
            return {
                "status": "IDLE",
                "type":   "state_change",
                "message": "Gotowe! Unieś nadgarstki do kolejnego odbicia.",
                "rep_increment": 0,
                "conditions": [],
            }

        return {
            "status":        "RESET",
            "type":          "info",
            "message":       "Opuść ręce poniżej barków, aby zresetować.",
            "rep_increment": 0,
            "conditions":    self.last_evaluation_conditions,
        }