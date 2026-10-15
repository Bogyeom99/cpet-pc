from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "cpet.db"


def is_configured() -> bool:
    return True


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS athletes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sex TEXT NOT NULL,
            category TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS athlete_measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            athlete_id INTEGER NOT NULL,
            test_date TEXT NOT NULL,
            height REAL NOT NULL DEFAULT 0,
            weight REAL NOT NULL DEFAULT 0,
            bmi REAL NOT NULL DEFAULT 0,
            vo2max REAL NOT NULL DEFAULT 0,
            hrmax INTEGER NOT NULL DEFAULT 0,
            exercise_time TEXT NOT NULL DEFAULT '',
            load_type TEXT NOT NULL DEFAULT 'Speed',
            max_load REAL NOT NULL DEFAULT 0,
            grade_percent REAL NOT NULL DEFAULT 0,
            stage_duration_min REAL NOT NULL DEFAULT 3,
            rest_duration_min REAL NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (athlete_id) REFERENCES athletes(id) ON DELETE CASCADE,
            UNIQUE (athlete_id, test_date)
        );

        CREATE INDEX IF NOT EXISTS idx_measurements_athlete_date
        ON athlete_measurements(athlete_id, test_date DESC);
        """
    )

    columns = {
        str(row["name"])
        for row in conn.execute(
            "PRAGMA table_info(athlete_measurements)"
        ).fetchall()
    }

    if "stage_duration_min" not in columns:
        conn.execute(
            "ALTER TABLE athlete_measurements "
            "ADD COLUMN stage_duration_min REAL NOT NULL DEFAULT 3"
        )

    if "rest_duration_min" not in columns:
        conn.execute(
            "ALTER TABLE athlete_measurements "
            "ADD COLUMN rest_duration_min REAL NOT NULL DEFAULT 1"
        )

    conn.commit()


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def list_athletes() -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, name, sex, category, created_at
            FROM athletes
            ORDER BY created_at, id
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def add_athlete(name: str, sex: str, category: str) -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name:
        raise ValueError("선수 이름을 입력하세요.")

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO athletes(name, sex, category)
            VALUES (?, ?, ?)
            """,
            (clean_name, sex, category),
        )
        athlete_id = int(cursor.lastrowid)
        conn.commit()

        row = conn.execute(
            """
            SELECT id, name, sex, category, created_at
            FROM athletes
            WHERE id = ?
            """,
            (athlete_id,),
        ).fetchone()

    return _row_to_dict(row)


def list_measurements(athlete_id: int) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                athlete_id,
                test_date,
                height,
                weight,
                bmi,
                vo2max,
                hrmax,
                exercise_time,
                load_type,
                max_load,
                grade_percent,
                stage_duration_min,
                rest_duration_min,
                created_at,
                updated_at
            FROM athlete_measurements
            WHERE athlete_id = ?
            ORDER BY test_date DESC, id DESC
            """,
            (int(athlete_id),),
        ).fetchall()

    return [_row_to_dict(row) for row in rows]


def save_measurement(
    athlete_id: int,
    test_date: str,
    height: float,
    weight: float,
    bmi: float,
    vo2max: float,
    hrmax: int,
    exercise_time: str,
    load_type: str,
    max_load: float,
    grade_percent: float,
    stage_duration_min: float,
    rest_duration_min: float,
) -> dict[str, Any]:
    values = (
        int(athlete_id),
        test_date,
        float(height),
        float(weight),
        float(bmi),
        float(vo2max),
        int(hrmax),
        exercise_time,
        load_type,
        float(max_load),
        float(grade_percent),
        float(stage_duration_min),
        float(rest_duration_min),
    )

    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO athlete_measurements(
                athlete_id,
                test_date,
                height,
                weight,
                bmi,
                vo2max,
                hrmax,
                exercise_time,
                load_type,
                max_load,
                grade_percent,
                stage_duration_min,
                rest_duration_min
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(athlete_id, test_date)
            DO UPDATE SET
                height = excluded.height,
                weight = excluded.weight,
                bmi = excluded.bmi,
                vo2max = excluded.vo2max,
                hrmax = excluded.hrmax,
                exercise_time = excluded.exercise_time,
                load_type = excluded.load_type,
                max_load = excluded.max_load,
                grade_percent = excluded.grade_percent,
                stage_duration_min = excluded.stage_duration_min,
                rest_duration_min = excluded.rest_duration_min,
                updated_at = CURRENT_TIMESTAMP
            """,
            values,
        )
        conn.commit()

        row = conn.execute(
            """
            SELECT
                id,
                athlete_id,
                test_date,
                height,
                weight,
                bmi,
                vo2max,
                hrmax,
                exercise_time,
                load_type,
                max_load,
                grade_percent,
                stage_duration_min,
                rest_duration_min,
                created_at,
                updated_at
            FROM athlete_measurements
            WHERE athlete_id = ? AND test_date = ?
            """,
            (int(athlete_id), test_date),
        ).fetchone()

    return _row_to_dict(row)
