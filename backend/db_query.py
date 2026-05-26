import sqlite3



def add_traning(training_type: str,duration: int ,overall_accuracy: float, leg_angle: float, body_angle: float,arm_angle: float):
    conn = sqlite3.connect('volleyball.db')
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
    conn = sqlite3.connect('volleyball.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM Training WHERE TrainingID = ?''', (training_id,))
    conn.commit()
    conn.close()
    training = cursor.fetchall()
    return training

def get_trainings():
    conn = sqlite3.connect('volleyball.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM Training''')
    conn.commit()
    conn.close()
    training = cursor.fetchall()
    return training

def get_angle(training_id: int):
    conn = sqlite3.connect('volleyball.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT * FROM AnglesAnalitic WHERE TrainingID = ?''', (training_id,))


def delete_training(training_id: int):
    conn = sqlite3.connect('volleyball.db')
    cursor = conn.cursor()
    cursor.execute('''DELETE FROM Training WHERE TrainingID = ?''', (training_id,))
    conn.commit()
    conn.close()