import sqlite3
import os

# Pobieramy ścieżkę do folderu, w którym leży db_query.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'volleyball.db')

# Pomocnicza funkcja tworząca świeży obiekt połączenia z SQLite
def get_conn():
    return sqlite3.connect(DB_PATH)

# Zapis statystyk sesji treningowej i zwrócenie wygenerowanego klucza głównego (ID)
def save_training_session(training_type: str, start_time: str, end_time: str, duration: int, successful_reps: int, total_attempts: int, overall_accuracy: float):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO Training (TrainingType, StartTime, EndTime, Duration, SuccessfulReps, TotalAttempts, OverallAccuracy) 
                      VALUES (?, ?, ?, ?, ?, ?, ?)''',
                   (training_type, start_time, end_time, duration, successful_reps, total_attempts, overall_accuracy)
                   )
    training_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return training_id


# Alternatywna (starsza/dodatkowa) metoda zapisu rozszerzona o analizę kątów stawów
def add_traning(training_type: str,duration: int ,overall_accuracy: float, leg_angle: float, body_angle: float,arm_angle: float):
    conn = get_conn()
    cursor = conn.cursor()
    # Wprowadzenie rekordu do tabeli głównej
    cursor.execute('''INSERT INTO Training (TraningType,Duration,OverallAccuracy) VALUES (?, ?, ?)''',
                   (training_type, duration, overall_accuracy)
                   )
    training_id = cursor.lastrowid
    # Wprowadzenie powiązanych danych analitycznych na podstawie wyciągniętego ID
    cursor.execute('''INSERT INTO AnglesAnalitic (TrainingID,LegAngle,BodyAngle,ArmAngle) VALUES (?, ?, ?, ?)''',
                   (training_id,leg_angle,body_angle,arm_angle)
                   )
    conn.commit()
    conn.close()

# Pobieranie surowych danych konkretnego treningu na podstawie unikalnego ID
def get_training_by_id(training_id: int):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM Training WHERE TrainingID = ?''', (training_id,))
    conn.commit()
    conn.close()
    training = cursor.fetchall()
    return training

# Pobieranie listy wszystkich treningów posortowanych od najnowszych
def get_trainings():
    conn = get_conn()
    conn.row_factory = sqlite3.Row  # Dzięki temu odczytamy dane jako słowniki (JSON), a nie surowe krotki
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM Training ORDER BY TrainingID DESC''')
    training = cursor.fetchall()
    conn.close()
    return [dict(t) for t in training]

# Sygnatura funkcji przeznaczonej do odpytywania o analizę kątów danego treningu (do rozbudowy)
def get_angle(training_id: int):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM AnglesAnalitic WHERE TrainingID = ?''', (training_id,))


# Usuwanie wybranego treningu z bazy (tabela AnglesAnalitic wyczyści się automatycznie przez CASCADE)
def delete_training(training_id: int):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''DELETE FROM Training WHERE TrainingID = ?''', (training_id,))
    conn.commit()
    conn.close()