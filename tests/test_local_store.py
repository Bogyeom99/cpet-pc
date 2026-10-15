from pathlib import Path

from services import athlete_store


def test_local_sqlite_store_round_trip(tmp_path, monkeypatch):
    db_path = Path(tmp_path) / "cpet-test.db"
    monkeypatch.setattr(athlete_store, "DB_PATH", db_path)

    assert athlete_store.list_athletes() == []

    athlete = athlete_store.add_athlete(
        "테스트 선수",
        "남",
        "국가대표 후보",
    )

    assert athlete["name"] == "테스트 선수"
    assert db_path.exists()

    saved = athlete_store.save_measurement(
        athlete_id=athlete["id"],
        test_date="2026-10-15",
        height=180.0,
        weight=75.0,
        bmi=23.1,
        vo2max=60.25,
        hrmax=190,
        exercise_time="20분",
        load_type="Speed",
        max_load=16.0,
        grade_percent=6.0,
        stage_duration_min=3,
        rest_duration_min=1,
    )

    assert saved["athlete_id"] == athlete["id"]
    assert saved["stage_duration_min"] == 3
    assert saved["rest_duration_min"] == 1

    athlete_store.save_measurement(
        athlete_id=athlete["id"],
        test_date="2026-10-15",
        height=181.0,
        weight=75.5,
        bmi=23.0,
        vo2max=61.0,
        hrmax=192,
        exercise_time="21분",
        load_type="Speed",
        max_load=17.0,
        grade_percent=6.0,
        stage_duration_min=5,
        rest_duration_min=2,
    )

    rows = athlete_store.list_measurements(athlete["id"])
    assert len(rows) == 1
    assert rows[0]["height"] == 181.0
    assert rows[0]["stage_duration_min"] == 5
    assert rows[0]["rest_duration_min"] == 2
