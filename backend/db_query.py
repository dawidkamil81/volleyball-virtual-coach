import sqlite3
import os

# Pobieramy ścieżkę do folderu, w którym leży db_query.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'volleyball.db')

def get_conn():
    return sqlite3.connect(DB_PATH)

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


def add_traning(training_type: str,duration: int ,overall_accuracy: float, leg_angle: float, body_angle: float,arm_angle: float):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''INSERT INTO Training (TraningType,Duration,OverallAccuracy) VALUES (?, ?, ?)''',
                   (training_type, duration, overall_accuracy)
                   )
    training_id = cursor.lastrowid
    cursor.execute('''INSERT INTO AnglesAnalitic (TrainingID,LegAngle,BodyAngle,ArmAngle) VALUES (?, ?, ?, ?)''',
                   (training_id,leg_angle,body_angle,arm_angle)
                   )
    conn.commit()
    conn.close()

def get_training_by_id(training_id: int):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM Training WHERE TrainingID = ?''', (training_id,))
    conn.commit()
    conn.close()
    training = cursor.fetchall()
    return training

def get_trainings():
    conn = get_conn()
    conn.row_factory = sqlite3.Row  # Dzięki temu odczytamy dane jako słowniki (JSON), a nie surowe krotki
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM Training ORDER BY TrainingID DESC''')
    training = cursor.fetchall()
    conn.close()
    return [dict(t) for t in training]

def get_angle(training_id: int):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM AnglesAnalitic WHERE TrainingID = ?''', (training_id,))


def delete_training(training_id: int):
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute('''DELETE FROM Training WHERE TrainingID = ?''', (training_id,))
    conn.commit()
    conn.close()