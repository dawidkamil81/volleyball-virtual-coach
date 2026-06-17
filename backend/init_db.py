import sqlite3
import os

print("Próbuję stworzyć bazę...")

try:
    # Wymuszamy ścieżkę do folderu backend
    # Dynamicznie określamy ścieżkę docelową bazy danych na podstawie lokalizacji bieżącego pliku skryptu
    db_path = os.path.join(os.path.dirname(__file__), 'volleyball.db')

    # Tworzymy połączenie z bazą danych (lub otwieramy istniejącą) oraz powołujemy kursor do wykonywania zapytań SQL
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Tworzenie głównej tabeli z ogólnymi statystykami odbytego treningu
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

    # Tworzenie powiązanej tabeli przechowującej analitykę kątów dla konkretnej sesji treningowej
    # Zastosowano klauzule kaskadowego usuwania (ON DELETE CASCADE) powiązaną kluczem obcym
    cur.execute('''CREATE TABLE IF NOT EXISTS AnglesAnalitic (
        TrainingID INTEGER PRIMARY KEY,
        LegAngle REAL,
        BodyAngle REAL,
        ArmAngle REAL,
        FOREIGN KEY (TrainingID) REFERENCES Training(TrainingID) ON DELETE CASCADE
    )''')

    # Zatwierdzenie transakcji i bezpieczne zamknięcie połączenia
    conn.commit()
    conn.close()
    print(f"Baza stworzona pomyślnie w: {db_path}")
except Exception as e:
    # Wyłapanie i zalogowanie ewentualnych błędów np. braku uprawnień do zapisu w folderze
    print(f"BŁĄD: {e}")