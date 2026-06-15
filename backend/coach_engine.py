import time
from backend.math_utils import calculate_angle_2d, calculate_distance_2d, get_forehead_y

class OverheadPassCoach:
    def __init__(self):
        self.state = "START"
        self.front_landmarks = None
        self.side_landmarks = None
        
        # Ostatni czas wysłania komunikatu (zapobiega spamowaniu)
        self.last_feedback_time = 0.0
        self.feedback_cooldown = 2.5  # sekundy
        
        # Pamięć parametrów z fazy BOTTOM (np. kąt kolan do porównania w fazie PEAK)
        self.bottom_knee_angle = 180.0
        
        # Pamięć do detekcji dynamiki w fazie BOTTOM -> PEAK
        self.last_wrist_y = 1.0  # Środek nadgarstków z bocznej kamery
        self.peak_waiting_frames = 0
        
    def process_frame(self, camera: str, landmarks):
        if camera == "front":
            self.front_landmarks = landmarks
        elif camera == "side":
            self.side_landmarks = landmarks
            
        # Analizujemy stan tylko jeśli mamy w miarę świeże dane z obu kamer
        if self.front_landmarks is None or self.side_landmarks is None:
            return None
            
        return self._evaluate_state()
        
    def _can_send_feedback(self):
        current_time = time.time()
        if current_time - self.last_feedback_time > self.feedback_cooldown:
            self.last_feedback_time = current_time
            return True
        return False

    def _evaluate_state(self):
        # Indeksy MediaPipe
        # Głowa: oczy (2, 5), uszy (7, 8)
        # Obręcz barkowa: barki (11, 12)
        # Ręce: łokcie (13, 14), nadgarstki (15, 16), kciuki (21, 22), palce wskazujące (19, 20)
        # Nogi: biodra (23, 24), kolana (25, 26), kostki (27, 28)
        
        # Wypakowanie często używanych punktów (zakładamy średnią dla symetrii ze strony profilu)
        # Wybieramy te punkty z side_landmarks, które są lepiej widoczne (bliżej kamery),
        # dla uproszczenia po prostu bierzemy lewą (nieparzyste) lub prawą (parzyste) stronę,
        # ale w MediaPipe z boku jedna strona może mieć wyższe confidence.
        
        s = self.side_landmarks
        f = self.front_landmarks
        
        # Uproszczenie: używamy lewej strony ze środowiska profilowego do kątów, jeśli ułożenie z boku (lub uśrednienie).
        # Tu bierzemy uśrednienie z boku dla stabilności lub stronę z wyższym zaufaniem.
        side_shoulder = s[11] if s[11].visibility > s[12].visibility else s[12]
        side_hip = s[23] if s[23].visibility > s[24].visibility else s[24]
        side_knee = s[25] if s[25].visibility > s[26].visibility else s[26]
        side_ankle = s[27] if s[27].visibility > s[28].visibility else s[28]
        side_wrist = s[15] if s[15].visibility > s[16].visibility else s[16]
        side_elbow = s[13] if s[13].visibility > s[14].visibility else s[14]
        
        # Środek nadgarstków dla widoku bocznego (dynamika Y)
        current_wrist_y = (s[15].y + s[16].y) / 2.0
        
        # Oczy/uszy do czoła
        side_eyes_ears = [s[2], s[5], s[7], s[8]]
        forehead_y = get_forehead_y(side_eyes_ears)
        
        if self.state == "START":
            # Sprawdzenie czy główne punkty są widoczne na profilu i froncie
            confidence_threshold = 0.5
            side_ok = all(p.visibility > confidence_threshold for p in [side_shoulder, side_hip, side_knee, side_ankle, side_wrist])
            front_ok = f[15].visibility > confidence_threshold and f[16].visibility > confidence_threshold
            
            if not (side_ok and front_ok):
                if self._can_send_feedback():
                    return {"status": "START", "type": "feedback", "message": "Proszę stanąć w pełni w kadrze obu kamer.", "rep_increment": 0}
            else:
                self.state = "IDLE"
                return {"status": "IDLE", "type": "state_change", "message": "Kamery gotowe. Unieś nadgarstki, by rozpocząć.", "rep_increment": 0}
                
        elif self.state == "IDLE":
            # Warunek przejścia: nadgarstki powyżej linii barków (Y nadgarstków < Y barków)
            if s[15].y < side_shoulder.y and s[16].y < side_shoulder.y:
                self.state = "BOTTOM"
                self.last_wrist_y = current_wrist_y
                return {"status": "BOTTOM", "type": "state_change", "message": "Zrób przysiad i ułóż koszyczek.", "rep_increment": 0}
                
        elif self.state == "BOTTOM":
            knee_angle = calculate_angle_2d(side_hip, side_knee, side_ankle)
            
            # Wymuszenie przysiadu
            if knee_angle >= 140:
                if self._can_send_feedback():
                    return {"status": "BOTTOM", "type": "feedback", "message": "Ugnij kolana.", "rep_increment": 0}
                return None
                
            # Punkt kontaktu: Nadgarstki powyżej wirtualnego czoła (Y mniejsze to wyżej)
            if current_wrist_y >= forehead_y:
                if self._can_send_feedback():
                    return {"status": "BOTTOM", "type": "feedback", "message": "Nadgarstki wyżej, ponad czołem.", "rep_increment": 0}
                return None
                
            # Koszyczek z przedniej kamery
            front_thumb_dist = calculate_distance_2d(f[21], f[22])
            front_wrist_dist = calculate_distance_2d(f[15], f[16])
            
            # Kciuki powinny być bliżej siebie niż nadgarstki, dłonie skierowane do środka
            if front_thumb_dist >= front_wrist_dist:
                if self._can_send_feedback():
                    return {"status": "BOTTOM", "type": "feedback", "message": "Złącz kciuki, zrób poprawny koszyczek.", "rep_increment": 0}
                return None
                
            # Jeśli wszystkie warunki są spełnione, sprawdzamy czy zaczyna się ruch w górę
            # Ruch w górę oznacza, że Y nadgarstków maleje
            if current_wrist_y < self.last_wrist_y - 0.02: # -0.02 to threshold dla dynamiki
                self.state = "PEAK"
                self.bottom_knee_angle = knee_angle
                self.peak_waiting_frames = 0
                return {"status": "PEAK", "type": "state_change", "message": "Wypchnij piłkę!", "rep_increment": 0}
                
            self.last_wrist_y = current_wrist_y
            
        elif self.state == "PEAK":
            # Rejestrujemy moment, w którym ruch rąk w górę się zatrzymuje
            if current_wrist_y < self.last_wrist_y:
                self.last_wrist_y = current_wrist_y
                self.peak_waiting_frames = 0
            else:
                self.peak_waiting_frames += 1
                
            # Jeśli przez X klatek dłonie nie idą w górę, zakładamy, że to koniec ruchu (max wyprost)
            if self.peak_waiting_frames > 5:
                # Walidacja końcowa
                elbow_angle = calculate_angle_2d(side_shoulder, side_elbow, side_wrist)
                current_knee_angle = calculate_angle_2d(side_hip, side_knee, side_ankle)
                shoulder_angle = calculate_angle_2d(side_hip, side_shoulder, side_elbow)
                
                errors = []
                if elbow_angle < 160:
                    errors.append("Brak wyprostu rąk.")
                
                # Czy kolana zwiększyły kąt o min 25 w stosunku do BOTTOM
                if current_knee_angle < self.bottom_knee_angle + 25:
                    errors.append("Odbicie z samych rąk, brak pracy nóg.")
                    
                if shoulder_angle <= 140 or current_wrist_y >= forehead_y:
                    errors.append("Zbyt niski punkt kontaktu (Zombie hand).")
                    
                self.state = "IDLE"
                
                if errors:
                    msg = " ".join(errors)
                    return {"status": "IDLE", "type": "feedback", "message": msg, "rep_increment": 0}
                else:
                    return {"status": "IDLE", "type": "feedback", "message": "Świetne odbicie!", "rep_increment": 1}
                    
        return None
