import sqlite3

conn = sqlite3.connect('volleyball.db')
cur = conn.cursor()

# Users table
cur.execute('''CREATE TABLE IF NOT EXISTS Users (
    UserID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    Surname TEXT NOT NULL,
    Height REAL,
    Weight REAL,
    Age INTEGER,
    Email TEXT UNIQUE NOT NULL
)''')

# Training table
cur.execute('''CREATE TABLE IF NOT EXISTS Training (
    TrainingID INTEGER PRIMARY KEY AUTOINCREMENT,
    TrainingType TEXT NOT NULL,
    Duration INTEGER,
    OverallAccuracy REAL,
    UserID INTEGER NOT NULL,
    FOREIGN KEY (UserID) REFERENCES Users(UserID) ON DELETE CASCADE
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