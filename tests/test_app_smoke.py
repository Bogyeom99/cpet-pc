from app import app


def test_flask_app_starts_without_external_services():
    client = app.test_client()

    response = client.get("/")
    assert response.status_code == 200
    assert "NGC CPET" in response.get_data(as_text=True)

    athletes = client.get("/api/athletes")
    assert athletes.status_code == 200
    assert athletes.get_json()["ok"] is True
