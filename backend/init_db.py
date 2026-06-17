import sqlite3
import os

print("Próbuję stworzyć bazę...")

try:
    # Wymuszamy ścieżkę do folderu backend
    db_path = os.path.join(os.path.dirname(__file__), 'volleyball.db')
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute('''CREATE TABLE IF NOT EXISTS Training (
        TrainingID INTEGER PRIMARY KEY AUTOINCREMENT,
        TrainingType TEXT NOT NULL,
        StartTime TEXT,
        EndTime TEXT,
        Duration INTEGER,
        SuccessfulReps INTEGER,
        TotalAttempts INTEGER,
        OverallAccuracy REAL
    )''')

    cur.execute('''CREATE TABLE IF NOT EXISTS AnglesAnalitic (
        TrainingID INTEGER PRIMARY KEY,
        LegAngle REAL,
        BodyAngle REAL,
        ArmAngle REAL,
        FOREIGN KEY (TrainingID) REFERENCES Training(TrainingID) ON DELETE CASCADE
    )''')

    conn.commit()
    conn.close()
    print(f"Baza stworzona pomyślnie w: {db_path}")
except Exception as e:
    print(f"BŁĄD: {e}")