from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_bundled_frontend_serves_spa_and_keeps_api_routes(tmp_path):
    (tmp_path / "index.html").write_text("<main>MyCareer UI</main>", encoding="utf-8")
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url="sqlite://",
        secret_key="test-only-static-frontend-secret-key-48",
        static_directory=str(tmp_path),
    )
    client = TestClient(create_app(settings))

    page = client.get("/")
    nested_page = client.get("/my-appraisal")
    health = client.get("/api/v1/health/live")
    unknown_api = client.get("/api/v1/not-a-route")

    assert page.status_code == nested_page.status_code == 200
    assert page.text == nested_page.text == "<main>MyCareer UI</main>"
    assert page.headers["content-security-policy"].startswith("default-src 'self'")
    assert health.json() == {"status": "ok"}
    assert unknown_api.status_code == 404
