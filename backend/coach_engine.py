import time
from backend.math_utils import calculate_angle_2d, calculate_distance_2d, get_forehead_y


class OverheadPassCoach:
    def __init__(self):
        # Definicja stanu początkowego maszyny stanów
        self.state = "START"
        self.front_landmarks = None
        self.side_landmarks = None

        # System kontroli powiadomień (cooldown) zapobiegający spamowaniu komunikatami głosowymi/tekstowymi
        self.last_feedback_time = 0.0
        self.feedback_cooldown = 2.5

        # Zmienne przechowujące kluczowe parametry biomechaniczne z poszczególnych faz ruchu
        self.bottom_knee_angle = 180.0

        # Zmienne do detekcji fazy wypchnięcia (Peak) na bazie kierunku ruchu nadgarstków
        self.lowest_wrist_y = 0.0
        self.peak_waiting_frames = 0
        self.last_wrist_y = 0.0

        self.reset_start_time = 0.0
        self.last_evaluation_conditions = []

        # Flaga odblokowująca ruch w górę (Zatrzask Poprawności)
        # Gwarantuje, że użytkownik faktycznie zaliczył poprawną pozycję niską (schowanie pod piłkę)
        self.bottom_position_valid = False

    def process_frame(self, camera: str, landmarks):
        # Agregacja danych z dwóch niezależnych strumieni wideo (kamery)
        if camera == "front":
            self.front_landmarks = landmarks
            return None
        elif camera == "side":
            self.side_landmarks = landmarks

        # Analiza startuje dopiero wtedy, gdy posiadamy klatki z obu perspektyw
        if self.front_landmarks is None or self.side_landmarks is None:
            return None

        return self._evaluate_state()

    def _can_send_feedback(self):
        # Sprawdzenie czy upłynął już zdefiniowany czas ochrony (cooldown)
        current_time = time.time()
        if current_time - self.last_feedback_time > self.feedback_cooldown:
            self.last_feedback_time = current_time
            return True
        return False

    def _evaluate_state(self):
        s = self.side_landmarks
        f = self.front_landmarks

        # Przypisanie kluczowych punktów anatomicznych z profilu (z uwzględnieniem lepiej widocznej strony ciała)
        side_shoulder = s[11] if s[11].visibility > s[12].visibility else s[12]
        side_hip = s[23] if s[23].visibility > s[24].visibility else s[24]
        side_knee = s[25] if s[25].visibility > s[26].visibility else s[26]
        side_ankle = s[27] if s[27].visibility > s[28].visibility else s[28]
        side_wrist = s[15] if s[15].visibility > s[16].visibility else s[16]
        side_elbow = s[13] if s[13].visibility > s[14].visibility else s[14]

        # Obliczanie średniej wysokości obu nadgarstków w osi pionowej
        current_wrist_y = (s[15].y + s[16].y) / 2.0

        # Wyznaczenie punktów odniesienia dla twarzy w celu weryfikacji wysokości ułożenia rąk
        side_eyes_ears = [s[2], s[5], s[7], s[8]]
        forehead_y = get_forehead_y(side_eyes_ears)

        # --- FAZA START ---
        # Sprawdzanie czy użytkownik jest w ogóle widoczny w kadrach obu kamer
        if self.state == "START":
            confidence_threshold = 0.5
            side_ok = all(p.visibility > confidence_threshold for p in
                          [side_shoulder, side_hip, side_knee, side_ankle, side_wrist])
            front_ok = f[15].visibility > confidence_threshold and f[16].visibility > confidence_threshold

            conditions = [
                {"name": "Widoczność sylwetki z profilu", "met": side_ok},
                {"name": "Widoczność dłoni z przodu", "met": front_ok}
            ]

            if not (side_ok and front_ok):
                if self._can_send_feedback():
                    return {"status": "START", "type": "feedback",
                            "message": "Proszę stanąć w pełni w kadrze obu kamer.", "rep_increment": 0,
                            "conditions": conditions}
                return {"status": "START", "type": "info", "message": "Proszę stanąć w pełni w kadrze obu kamer.",
                        "rep_increment": 0, "conditions": conditions}
            else:
                self.state = "IDLE"
                return {"status": "IDLE", "type": "state_change",
                        "message": "Kamery gotowe. Unieś nadgarstki nad barki.", "rep_increment": 0, "conditions": []}

        # --- FAZA IDLE ---
        # Oczekiwanie na przyjęcie pozycji wyjściowej (ręce uniesione do góry)
        elif self.state == "IDLE":
            wrists_above_shoulders = s[15].y < side_shoulder.y and s[16].y < side_shoulder.y
            conditions = [
                {"name": "Nadgarstki ponad barkami", "met": wrists_above_shoulders}
            ]

            if wrists_above_shoulders:
                self.state = "BOTTOM"
                self.lowest_wrist_y = current_wrist_y
                self.bottom_knee_angle = 180.0
                self.bottom_position_valid = False
                return {"status": "BOTTOM", "type": "state_change", "message": "Zrób przysiad i ułóż koszyczek.",
                        "rep_increment": 0, "conditions": []}
            else:
                if self._can_send_feedback():
                    return {"status": "IDLE", "type": "feedback", "message": "Unieś nadgarstki nad barki.",
                            "rep_increment": 0, "conditions": conditions}
                return {"status": "IDLE", "type": "info", "message": "Oczekuję na uniesienie rąk...",
                        "rep_increment": 0, "conditions": conditions}

        # --- FAZA BOTTOM ---
        # Najważniejsza faza przygotowania: ugięcie nóg oraz ułożenie dłoni w kształt koszyczka nad czołem
        elif self.state == "BOTTOM":
            # Zapisujemy jedynie pozycję rąk, by wyczuć ruch w górę
            if current_wrist_y > self.lowest_wrist_y:
                self.lowest_wrist_y = current_wrist_y

            knee_angle = calculate_angle_2d(side_hip, side_knee, side_ankle)
            front_thumb_dist = calculate_distance_2d(f[21], f[22])
            front_wrist_dist = calculate_distance_2d(f[15], f[16])

            # Warunki poprawności siadu i koszyczka
            is_knee_bent = knee_angle < 150
            is_wrist_high = current_wrist_y < forehead_y + 0.04
            is_koszyczek = front_thumb_dist < front_wrist_dist

            # ZATRZASK: Łapiemy prawdziwy kąt kolan dokładnie w momencie odblokowania bramki
            if is_knee_bent and is_wrist_high and is_koszyczek:
                if not self.bottom_position_valid:
                    self.bottom_knee_angle = knee_angle
                self.bottom_position_valid = True

            conditions = [
                {"name": "Kolana ugięte", "met": is_knee_bent or self.bottom_position_valid},
                {"name": "Nadgarstki ponad twarzą", "met": is_wrist_high or self.bottom_position_valid},
                {"name": "Koszyczek (złączone kciuki)", "met": is_koszyczek or self.bottom_position_valid}
            ]

            # Wykrywanie ruchu rąk w górę (wypchnięcie piłki)
            if current_wrist_y < self.lowest_wrist_y - 0.035:
                if self.bottom_position_valid:
                    self.state = "PEAK"
                    self.peak_waiting_frames = 0
                    self.last_wrist_y = current_wrist_y
                    self.bottom_position_valid = False
                    return {"status": "PEAK", "type": "state_change", "message": "Wypchnij piłkę w górę!",
                            "rep_increment": 0, "conditions": []}
                else:
                    # Próba odbicia bez uprzedniego ugięcia nóg lub ułożenia dłoni
                    self.lowest_wrist_y = current_wrist_y
                    if self._can_send_feedback():
                        return {"status": "BOTTOM", "type": "feedback",
                                "message": "Zanim wypchniesz piłkę, musisz ugiąć kolana i zrobić koszyczek!",
                                "rep_increment": 0, "conditions": conditions}

            # Generowanie podpowiedzi korygujących pozycję na bieżąco
            if not self.bottom_position_valid:
                msg = "Ułóż poprawnie pozycję do odbicia."
                if not is_knee_bent:
                    msg = "Ugnij kolana (zrób lekki przysiad)."
                elif not is_wrist_high:
                    msg = "Podnieś nadgarstki nad czoło."
                elif not is_koszyczek:
                    msg = "Złącz kciuki (koszyczek)."

                if self._can_send_feedback():
                    return {"status": "BOTTOM", "type": "feedback", "message": msg, "rep_increment": 0,
                            "conditions": conditions}
                return {"status": "BOTTOM", "type": "info", "message": msg, "rep_increment": 0,
                        "conditions": conditions}

            return {"status": "BOTTOM", "type": "info", "message": "Pozycja idealna! Wypchnij piłkę w górę!",
                    "rep_increment": 0, "conditions": conditions}

        # --- FAZA PEAK ---
        # Moment maksymalnego wyprostu rąk i nóg. Trwa do momentu, w którym dłonie przestaną poruszać się w górę.
        elif self.state == "PEAK":
            if current_wrist_y < self.last_wrist_y - 0.005:
                self.last_wrist_y = current_wrist_y
                self.peak_waiting_frames = 0
            else:
                # Zliczanie klatek braku progresu ruchu w pionie w celu wykrycia punktu zwrotnego
                self.peak_waiting_frames += 1

            conditions = [
                {"name": "Zatrzymanie rąk (maksymalny wyprost)", "met": self.peak_waiting_frames > 4}
            ]

            if self.peak_waiting_frames > 4:
                # Odczyt końcowych kątów w celu oceny technicznej powtórzenia
                elbow_angle = calculate_angle_2d(side_shoulder, side_elbow, side_wrist)
                current_knee_angle = calculate_angle_2d(side_hip, side_knee, side_ankle)
                shoulder_angle = calculate_angle_2d(side_hip, side_shoulder, side_elbow)

                errors = []
                if elbow_angle < 135:
                    errors.append("Brak wyprostu rąk.")

                # ZMIANA: Bezwzględny wymóg wyprostowanych kolan w najwyższym punkcie
                if current_knee_angle < 155:
                    errors.append("Brak wyprostu kolan (pracuj nogami do końca!).")
                elif current_knee_angle < self.bottom_knee_angle + 15:
                    errors.append("Za mała dynamika pracy nóg.")

                if shoulder_angle <= 125 or current_wrist_y >= forehead_y:
                    errors.append("Zbyt płaskie odbicie przed siebie (Zombie hand).")

                self.state = "RESET"
                self.reset_start_time = time.time()

                final_conditions = [
                    {"name": "Wystarczający wyprost rąk", "met": elbow_angle >= 135},
                    {"name": "Pełna praca nóg",
                     "met": current_knee_angle >= 155 and current_knee_angle >= self.bottom_knee_angle + 15},
                    {"name": "Wysoki punkt kontaktu", "met": shoulder_angle > 125 and current_wrist_y < forehead_y}
                ]

                self.last_evaluation_conditions = final_conditions

                # Ocena czy powtórzenie jest zaliczone (brak błędów), czy też błędne technicznie
                if errors:
                    return {"status": "RESET", "type": "feedback", "message": " ".join(errors), "rep_increment": 0,
                            "conditions": final_conditions}
                else:
                    return {"status": "RESET", "type": "feedback", "message": "Świetne odbicie!", "rep_increment": 1,
                            "conditions": final_conditions}

            return {"status": "PEAK", "type": "info", "message": "Dokończ ruch w górę...", "rep_increment": 0,
                    "conditions": conditions}

        # --- FAZA RESET ---
        # Wymuszenie powrotu rąk w dół oraz wprowadzenie sztucznej zwłoki czasowej przed kolejną próbą
        elif self.state == "RESET":
            time_elapsed = time.time() - self.reset_start_time

            if time_elapsed < 2.0:
                return None

            wrists_below_shoulders = s[15].y > side_shoulder.y and s[16].y > side_shoulder.y

            if wrists_below_shoulders:
                self.state = "IDLE"
                return {"status": "IDLE", "type": "state_change",
                        "message": "Gotowe. Unieś nadgarstki do kolejnego odbicia.", "rep_increment": 0,
                        "conditions": []}
            else:
                return {"status": "RESET", "type": "info",
                        "message": "Opuść ręce poniżej barków, aby zresetować układ.", "rep_increment": 0,
                        "conditions": self.last_evaluation_conditions}

        return None