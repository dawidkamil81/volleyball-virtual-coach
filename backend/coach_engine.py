import time
from backend.math_utils import calculate_angle_2d, calculate_distance_2d, get_forehead_y

class OverheadPassCoach:
    def __init__(self):
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
        self.last_evaluation_conditions = []
        
    def process_frame(self, camera: str, landmarks):
        if camera == "front":
            self.front_landmarks = landmarks
            # Kamera frontowa tylko aktualizuje dane, maszyna stanów jest napędzana z boku
            return None
        elif camera == "side":
            self.side_landmarks = landmarks
            
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
        s = self.side_landmarks
        f = self.front_landmarks
        
        side_shoulder = s[11] if s[11].visibility > s[12].visibility else s[12]
        side_hip = s[23] if s[23].visibility > s[24].visibility else s[24]
        side_knee = s[25] if s[25].visibility > s[26].visibility else s[26]
        side_ankle = s[27] if s[27].visibility > s[28].visibility else s[28]
        side_wrist = s[15] if s[15].visibility > s[16].visibility else s[16]
        side_elbow = s[13] if s[13].visibility > s[14].visibility else s[14]
        
        current_wrist_y = (s[15].y + s[16].y) / 2.0
        
        side_eyes_ears = [s[2], s[5], s[7], s[8]]
        forehead_y = get_forehead_y(side_eyes_ears)
        
        if self.state == "START":
            confidence_threshold = 0.5
            side_ok = all(p.visibility > confidence_threshold for p in [side_shoulder, side_hip, side_knee, side_ankle, side_wrist])
            front_ok = f[15].visibility > confidence_threshold and f[16].visibility > confidence_threshold
            
            conditions = [
                {"name": "Widoczność sylwetki z profilu", "met": side_ok},
                {"name": "Widoczność dłoni z przodu", "met": front_ok}
            ]
            
            if not (side_ok and front_ok):
                if self._can_send_feedback():
                    return {"status": "START", "type": "feedback", "message": "Proszę stanąć w pełni w kadrze obu kamer.", "rep_increment": 0, "conditions": conditions}
                return {"status": "START", "type": "info", "message": "Proszę stanąć w pełni w kadrze obu kamer.", "rep_increment": 0, "conditions": conditions}
            else:
                self.state = "IDLE"
                return {"status": "IDLE", "type": "state_change", "message": "Kamery gotowe. Unieś nadgarstki nad barki.", "rep_increment": 0, "conditions": []}
                
        elif self.state == "IDLE":
            wrists_above_shoulders = s[15].y < side_shoulder.y and s[16].y < side_shoulder.y
            conditions = [
                {"name": "Nadgarstki ponad barkami", "met": wrists_above_shoulders}
            ]
            
            if wrists_above_shoulders:
                self.state = "BOTTOM"
                self.lowest_wrist_y = current_wrist_y # Inicjalizacja
                return {"status": "BOTTOM", "type": "state_change", "message": "Zrób przysiad i ułóż koszyczek.", "rep_increment": 0, "conditions": []}
            else:
                if self._can_send_feedback():
                    return {"status": "IDLE", "type": "feedback", "message": "Unieś nadgarstki nad barki.", "rep_increment": 0, "conditions": conditions}
                return {"status": "IDLE", "type": "info", "message": "Oczekuję na uniesienie rąk...", "rep_increment": 0, "conditions": conditions}
                
        elif self.state == "BOTTOM":
            if current_wrist_y > self.lowest_wrist_y:
                self.lowest_wrist_y = current_wrist_y

            knee_angle = calculate_angle_2d(side_hip, side_knee, side_ankle)
            front_thumb_dist = calculate_distance_2d(f[21], f[22])
            front_wrist_dist = calculate_distance_2d(f[15], f[16])
            
            is_knee_bent = knee_angle < 140
            is_wrist_high = current_wrist_y < forehead_y + 0.02
            is_koszyczek = front_thumb_dist < front_wrist_dist
            
            conditions = [
                {"name": "Kolana ugięte", "met": is_knee_bent},
                {"name": "Nadgarstki ponad twarzą", "met": is_wrist_high},
                {"name": "Koszyczek (złączone kciuki)", "met": is_koszyczek}
            ]
            
            # Jeśli któryś warunek nie jest spełniony, trzymamy w BOTTOM
            if not (is_knee_bent and is_wrist_high and is_koszyczek):
                msg = "Ułóż poprawnie pozycję do odbicia."
                if not is_knee_bent: msg = "Ugnij kolana."
                elif not is_wrist_high: msg = "Nadgarstki wyżej, nie opuszczaj przed twarz."
                elif not is_koszyczek: msg = "Złącz kciuki, zrób koszyczek."
                
                if self._can_send_feedback():
                    return {"status": "BOTTOM", "type": "feedback", "message": msg, "rep_increment": 0, "conditions": conditions}
                return {"status": "BOTTOM", "type": "info", "message": msg, "rep_increment": 0, "conditions": conditions}
                
            # Gdy wszystkie warunki są spełnione, sprawdzamy dynamikę wypchnięcia
            conditions.append({"name": "Wypchnięcie rąk w górę", "met": current_wrist_y < self.lowest_wrist_y - 0.025})
            
            if current_wrist_y < self.lowest_wrist_y - 0.025: 
                self.state = "PEAK"
                self.bottom_knee_angle = knee_angle
                self.peak_waiting_frames = 0
                self.last_wrist_y = current_wrist_y
                return {"status": "PEAK", "type": "state_change", "message": "Wypchnij piłkę w górę!", "rep_increment": 0, "conditions": []}
            else:
                return {"status": "BOTTOM", "type": "info", "message": "Zatrzymaj pozycję i wypchnij piłkę!", "rep_increment": 0, "conditions": conditions}
            
        elif self.state == "PEAK":
            if current_wrist_y < self.last_wrist_y:
                self.last_wrist_y = current_wrist_y
                self.peak_waiting_frames = 0
            else:
                self.peak_waiting_frames += 1
                
            conditions = [
                {"name": "Oczekiwanie na pełen wyprost", "met": self.peak_waiting_frames > 5}
            ]
                
            if self.peak_waiting_frames > 5:
                elbow_angle = calculate_angle_2d(side_shoulder, side_elbow, side_wrist)
                current_knee_angle = calculate_angle_2d(side_hip, side_knee, side_ankle)
                shoulder_angle = calculate_angle_2d(side_hip, side_shoulder, side_elbow)
                
                errors = []
                if elbow_angle < 145:
                    errors.append("Brak wyprostu rąk.")
                if current_knee_angle < self.bottom_knee_angle + 10:
                    errors.append("Brak wyprostu kolan przy odbiciu.")
                if shoulder_angle <= 135 or current_wrist_y >= forehead_y:
                    errors.append("Zbyt płaskie odbicie (Zombie hand).")
                    
                self.state = "RESET"
                self.reset_start_time = time.time()
                
                final_conditions = [
                    {"name": "Wystarczający wyprost rąk", "met": elbow_angle >= 145},
                    {"name": "Wystarczająca praca nóg", "met": current_knee_angle >= self.bottom_knee_angle + 10},
                    {"name": "Wysoki punkt kontaktu", "met": shoulder_angle > 135 and current_wrist_y < forehead_y}
                ]
                
                self.last_evaluation_conditions = final_conditions
                
                if errors:
                    return {"status": "PEAK", "type": "feedback", "message": " ".join(errors), "rep_increment": 0, "conditions": final_conditions}
                else:
                    return {"status": "PEAK", "type": "feedback", "message": "Świetne odbicie!", "rep_increment": 1, "conditions": final_conditions}
                    
            return {"status": "PEAK", "type": "info", "message": "Dokończ ruch w górę...", "rep_increment": 0, "conditions": conditions}
            
        elif self.state == "RESET":
            wrists_below_shoulders = s[15].y > side_shoulder.y and s[16].y > side_shoulder.y
            
            if wrists_below_shoulders:
                self.state = "IDLE"
                return {"status": "IDLE", "type": "state_change", "message": "Ręce opuszczone. Unieś nadgarstki, by rozpocząć nowe odbicie.", "rep_increment": 0, "conditions": []}
            else:
                # Zamrażamy ekran na 2 sekundy by gracz zobaczył ocenę (zwracamy None = brak aktualizacji na UI)
                if time.time() - self.reset_start_time > 2.0:
                    return {"status": "RESET", "type": "info", "message": "Opuść ręce poniżej barków, aby zresetować układ.", "rep_increment": 0, "conditions": self.last_evaluation_conditions}
                return None
                    
        return None