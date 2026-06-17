import sqlite3
import time

DB_NAME = "volleyball.db"


def watch_database():
    print(f"Rozpoczynam podgląd bazy danych: {DB_NAME}")
    print("Skrypt odświeża się automatycznie co 2 sekundy. Naciśnij Ctrl+C, aby wyjść.\n")

    while True:
        try:
            # Łączymy się w trybie tylko do odczytu (uri=True), żeby nie blokować bazy backendowi
            conn = sqlite3.connect(f"file:{DB_NAME}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row  # Wyniki jako słowniki/dostęp po nazwach kolumn
            cur = conn.cursor()

            # Pobieramy 5 najnowszych treningów wraz z ich analizą kątów
            query = """
                SELECT t.TrainingID, t.TrainingType, t.Duration, t.OverallAccuracy,
                       a.LegAngle, a.BodyAngle, a.ArmAngle
                FROM Training t
                LEFT JOIN AnglesAnalitic a ON t.TrainingID = a.TrainingID
                ORDER BY t.TrainingID DESC
                LIMIT 5
            """
            cur.execute(query)
            rows = cur.fetchall()

            print(f"--- Stan bazy z godziny: {time.strftime('%H:%M:%S')} ---")

            if not rows:
                print("Baza danych jest pusta. Brak rekordów w tabeli Training.")
            else:
                for row in rows:
                    print(
                        f"[ID: {row['TrainingID']}] Typ: {row['TrainingType']} | "
                        f"Czas: {row['Duration']}s | Celność: {row['OverallAccuracy']}%"
                    )
                    if row['LegAngle'] is not None:
                        print(
                            f"   -> Kąty: Nogi={row['LegAngle']}° | Tłów={row['BodyAngle']}° | Ręce={row['ArmAngle']}°")
                    else:
                        print("   -> Brak przypisanych danych analitycznych kątów.")
                    print("-" * 30)

            conn.close()

        except sqlite3.OperationalError as e:
            print(f"Błąd dostępu do bazy (być może backend jeszcze jej nie utworzył): {e}")
        except KeyboardInterrupt:
            print("\nZakończono podgląd bazy danych.")
            break

        time.sleep(2)


if __name__ == "__main__":
    watch_database()