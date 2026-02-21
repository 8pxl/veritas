import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app

# Use the actual Postgres database running in Docker
TEST_DATABASE_URL = "postgresql://user:password@localhost:5432/veritasDB"
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Override the get_db dependency to use the test DB
def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


# ---- Organization Tests ----

def test_create_organization():
    response = client.post("/organizations", json={
        "id": 1,
        "name": "Acme Corp",
        "url": "https://acme.com",
        "logo_url": "https://acme.com/logo.png"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Acme Corp"
    assert data["id"] == 1


def test_create_organization_without_logo():
    response = client.post("/organizations", json={
        "id": 2,
        "name": "No Logo Inc",
        "url": "https://nologo.com"
    })
    assert response.status_code == 200
    assert response.json()["logo_url"] is None


# ---- Person Tests ----

def _create_org():
    """Helper: create an organization so person FK constraints pass."""
    client.post("/organizations", json={
        "id": 1,
        "name": "Acme Corp",
        "url": "https://acme.com",
        "logo_url": "https://acme.com/logo.png"
    })


def test_create_person():
    _create_org()
    response = client.post("/people", json={
        "name": "Jane Doe",
        "position": "CEO",
        "id": "person-1",
        "organization": {"id": 1, "name": "Acme Corp", "url": "https://acme.com", "logo_url": "https://acme.com/logo.png"}
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Jane Doe"
    assert data["id"] == "person-1"
    assert data["organization"]["id"] == 1


def test_create_person_without_position():
    _create_org()
    response = client.post("/people", json={
        "name": "John Smith",
        "id": "person-2",
        "organization": {"id": 1, "name": "Acme Corp", "url": "https://acme.com"}
    })
    assert response.status_code == 200
    assert response.json()["position"] is None


def test_create_person_missing_organization():
    """Should 404 if the organization doesn't exist."""
    response = client.post("/people", json={
        "name": "Ghost Worker",
        "id": "person-3",
        "organization": {"id": 999, "name": "Fake Org", "url": "https://fake.com"}
    })
    assert response.status_code == 404
    assert response.json()["detail"] == "Organization not found"


# ---- Video Tests ----

def test_create_video():
    response = client.post("/videos", json={
        "video_id": "vid-001",
        "video_path": "/videos/vid-001.mp4",
        "title": "Test Video",
        "description": "A test video",
        "video_url": "https://youtube.com/watch?v=abc",
        "time": "2026-02-21T12:00:00"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Test Video"
    assert data["video_id"] == "vid-001"


def test_create_video_without_description():
    response = client.post("/videos", json={
        "video_id": "vid-002",
        "video_path": "/videos/vid-002.mp4",
        "title": "No Desc Video",
        "video_url": "https://youtube.com/watch?v=xyz",
        "time": "2026-02-21T13:00:00"
    })
    assert response.status_code == 200
    assert response.json()["description"] is None


# ---- Proposition Tests ----

def _create_person_and_video():
    """Helper: create an org, person and video so proposition FK constraints pass."""
    _create_org()
    client.post("/people", json={
        "name": "Jane Doe",
        "position": "CEO",
        "id": "person-1",
        "organization": {"id": 1, "name": "Acme Corp", "url": "https://acme.com", "logo_url": "https://acme.com/logo.png"}
    })
    client.post("/videos", json={
        "video_id": "vid-001",
        "video_path": "/videos/vid-001.mp4",
        "title": "Test Video",
        "video_url": "https://youtube.com/watch?v=abc",
        "time": "2026-02-21T12:00:00"
    })


def test_create_proposition():
    _create_person_and_video()
    response = client.post("/propositions", json={
        "id": 1,
        "speaker": {"name": "Jane Doe", "position": "CEO", "id": "person-1", "organization": {"id": 1, "name": "Acme Corp", "url": "https://acme.com", "logo_url": "https://acme.com/logo.png"}},
        "statement": "The sky is blue",
        "verifyAt": "2026-02-21T14:00:00",
        "video": {
            "video_id": "vid-001",
            "video_path": "/videos/vid-001.mp4",
            "title": "Test Video",
            "video_url": "https://youtube.com/watch?v=abc",
            "time": "2026-02-21T12:00:00"
        }
    })
    assert response.status_code == 200
    data = response.json()
    assert data["statement"] == "The sky is blue"
    assert data["speaker"]["id"] == "person-1"


def test_create_proposition_missing_speaker():
    """Should 404 if the speaker doesn't exist."""
    client.post("/videos", json={
        "video_id": "vid-001",
        "video_path": "/videos/vid-001.mp4",
        "title": "Test Video",
        "video_url": "https://youtube.com/watch?v=abc",
        "time": "2026-02-21T12:00:00"
    })
    response = client.post("/propositions", json={
        "id": 1,
        "speaker": {"name": "Ghost", "id": "nonexistent", "organization": {"id": 1, "name": "Acme Corp", "url": "https://acme.com"}},
        "statement": "I don't exist",
        "verifyAt": "2026-02-21T14:00:00",
        "video": {
            "video_id": "vid-001",
            "video_path": "/videos/vid-001.mp4",
            "title": "Test Video",
            "video_url": "https://youtube.com/watch?v=abc",
            "time": "2026-02-21T12:00:00"
        }
    })
    assert response.status_code == 404
    assert response.json()["detail"] == "Speaker not found"


def test_create_proposition_missing_video():
    """Should 404 if the video doesn't exist."""
    client.post("/organizations", json={
        "id": 1,
        "name": "Acme Corp",
        "url": "https://acme.com"
    })
    client.post("/people", json={
        "name": "Jane Doe",
        "position": "CEO",
        "id": "person-1",
        "organization": {"id": 1, "name": "Acme Corp", "url": "https://acme.com"}
    })
    response = client.post("/propositions", json={
        "id": 1,
        "speaker": {"name": "Jane Doe", "position": "CEO", "id": "person-1", "organization": {"id": 1, "name": "Acme Corp", "url": "https://acme.com"}},
        "statement": "No video here",
        "verifyAt": "2026-02-21T14:00:00",
        "video": {
            "video_id": "nonexistent",
            "video_path": "/videos/none.mp4",
            "title": "Ghost Video",
            "video_url": "https://youtube.com/watch?v=ghost",
            "time": "2026-02-21T12:00:00"
        }
    })
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"
