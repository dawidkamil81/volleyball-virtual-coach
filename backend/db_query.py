"""
Task 4.6 – Zapis danych sesji treningowej do SQLite.

Naprawione błędy względem oryginalnego db_query.py:
  - Literówka: TraningType → TrainingType
  - cursor.fetchall() wywoływane PO conn.close() (fix: fetch przed close)
  - get_angle() nie commitowało ani nie zwracało wyników
  - Dodano save_session() integrującą dane z SessionStats (coach_engine.py)
"""

from __future__ import annotations

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Baza w katalogu backend/ – można nadpisać zmienną środowiskową
DB_PATH = Path(__file__).parent / "volleyball.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")   # wymuś kaskadowe usuwanie
    conn.row_factory = sqlite3.Row             # wyniki jako słowniki
    return conn


# ---------------------------------------------------------------------------
# Task 4.6 – główna funkcja zapisu sesji (integracja z coach_engine.SessionStats)
# ---------------------------------------------------------------------------

def save_session(
    training_type: str,
    duration: int,
    overall_accuracy: float,
    leg_angle: float,
    body_angle: float,
    arm_angle: float,
) -> int:
    """
    Zapisuje jedną ukończoną sesję treningową do bazy.

    Zwraca TrainingID nowego rekordu.

    Args:
        training_type:    Typ ćwiczenia, np. "górne" / "dolne".
        duration:         Czas trwania sesji w sekundach.
        overall_accuracy: Dokładność 0.0–1.0 (np. 0.75 = 75 %).
        leg_angle:        Średni kąt kolan w najwyższym punkcie.
        body_angle:       Średni kąt barków / tułowia.
        arm_angle:        Średni kąt łokci w najwyższym punkcie.

    Raises:
        sqlite3.Error: przy problemach z bazą danych.
    """
    with _get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO Training (TrainingType, Duration, OverallAccuracy)
            VALUES (?, ?, ?)
            """,
            (training_type, duration, round(overall_accuracy, 4)),
        )
        training_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO AnglesAnalitic (TrainingID, LegAngle, BodyAngle, ArmAngle)
            VALUES (?, ?, ?, ?)
            """,
            (training_id, round(leg_angle, 2), round(body_angle, 2), round(arm_angle, 2)),
        )
        conn.commit()

    logger.info(
        "Zapisano sesję #%d: typ=%s, czas=%ds, dokładność=%.1f%%",
        training_id, training_type, duration, overall_accuracy * 100,
    )
    return training_id


def save_session_from_stats(training_type: str, stats) -> int:
    """
    Wygodna nakładka przyjmująca obiekt SessionStats z coach_engine.

    Przykład użycia w main.py:
        from backend.db_query import save_session_from_stats
        save_session_from_stats("górne", coach.session)
    """
    return save_session(
        training_type    = training_type,
        duration         = stats.duration_seconds,
        overall_accuracy = stats.accuracy,
        leg_angle        = stats.avg_leg_angle,
        body_angle       = stats.avg_shoulder_angle,
        arm_angle        = stats.avg_arm_angle,
    )


# ---------------------------------------------------------------------------
# Odczyt
# ---------------------------------------------------------------------------

def get_training_by_id(training_id: int) -> dict | None:
    """Zwraca słownik z danymi sesji lub None gdy nie znaleziono."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM Training WHERE TrainingID = ?", (training_id,)
        ).fetchone()
    return dict(row) if row else None


def get_all_trainings() -> list[dict]:
    """Zwraca wszystkie sesje posortowane od najnowszej."""
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM Training ORDER BY TrainingID DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_angles_for_training(training_id: int) -> dict | None:
    """Zwraca kąty dla danej sesji lub None."""
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM AnglesAnalitic WHERE TrainingID = ?", (training_id,)
        ).fetchone()
    return dict(row) if row else None


def get_training_with_angles(training_id: int) -> dict | None:
    """JOIN Training + AnglesAnalitic – jedna wygodna funkcja dla Dashboard."""
    with _get_conn() as conn:
        row = conn.execute(
            """
            SELECT t.*, a.LegAngle, a.BodyAngle, a.ArmAngle
            FROM Training t
            LEFT JOIN AnglesAnalitic a USING (TrainingID)
            WHERE t.TrainingID = ?
            """,
            (training_id,),
        ).fetchone()
    return dict(row) if row else None


def get_recent_trainings(limit: int = 10) -> list[dict]:
    """Zwraca `limit` ostatnich sesji z kątami – wygodne dla wykresów w Dashboard."""
    with _get_conn() as conn:
        rows = conn.execute(
            """
            SELECT t.*, a.LegAngle, a.BodyAngle, a.ArmAngle
            FROM Training t
            LEFT JOIN AnglesAnalitic a USING (TrainingID)
            ORDER BY t.TrainingID DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Usuwanie
# ---------------------------------------------------------------------------

def delete_training(training_id: int) -> bool:
    """
    Usuwa sesję (CASCADE usuwa też rekord w AnglesAnalitic).
    Zwraca True jeśli coś usunięto.
    """
    with _get_conn() as conn:
        cursor = conn.execute(
            "DELETE FROM Training WHERE TrainingID = ?", (training_id,)
        )
        conn.commit()
    deleted = cursor.rowcount > 0
    if deleted:
        logger.info("Usunięto sesję #%d", training_id)
    return deleted