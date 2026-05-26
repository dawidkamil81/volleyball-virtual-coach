import sqlite3

conn = sqlite3.connect('volleyball.db')
cur = conn.cursor()


# Training table
cur.execute('''CREATE TABLE IF NOT EXISTS Training (
    TrainingID INTEGER PRIMARY KEY AUTOINCREMENT,
    TrainingType TEXT NOT NULL,
    Duration INTEGER,
    OverallAccuracy REAL
)''')

# AnglesAnalitic table
cur.execute('''CREATE TABLE IF NOT EXISTS AnglesAnalitic (
    TrainingID INTEGER PRIMARY KEY,
    LegAngle REAL,
    BodyAngle REAL,
    ArmAngle REAL,
    FOREIGN KEY (TrainingID) REFERENCES Training(TrainingID) ON DELETE CASCADE
)''')

conn.commit()
conn.close()