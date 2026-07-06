"""FastAPI エンドポイントの統合テスト（Phase 6）"""
from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_health() -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_lessons() -> None:
    r = client.get("/problems/lessons")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 184
    assert len(data["lessons"]) == 184


def test_get_mapping_existing() -> None:
    r = client.get("/problems/mapping/g1_l5")
    assert r.status_code == 200
    assert r.json()["grade"] == 1


def test_get_mapping_404() -> None:
    r = client.get("/problems/mapping/g9_l99")
    assert r.status_code == 404


def test_generate_basic_calculation() -> None:
    payload = {
        "curriculum": {"grade": 1, "lesson_ids": ["g1_l5"]},
        "problem_form": "calculation",
        "target_difficulty": 13,
        "unlearned_lesson_ids": [],
    }
    r = client.post("/problems/generate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert "content_problem_text" in data
    assert data["sub_questions"]
    assert data["metadata"]["blueprint_id"] == "BasicCalculationStructure"


def test_generate_rejects_unsupported_form() -> None:
    payload = {
        "curriculum": {"grade": 1, "lesson_ids": ["g1_l5"]},
        "problem_form": "proof",
        "target_difficulty": 13,
        "unlearned_lesson_ids": [],
    }
    r = client.post("/problems/generate", json=payload)
    assert r.status_code == 400


def test_generate_rejects_unknown_lesson() -> None:
    payload = {
        "curriculum": {"grade": 1, "lesson_ids": ["g9_l99"]},
        "problem_form": "calculation",
        "target_difficulty": 13,
        "unlearned_lesson_ids": [],
    }
    r = client.post("/problems/generate", json=payload)
    assert r.status_code == 404


def test_generate_rejects_empty_lesson_ids() -> None:
    payload = {
        "curriculum": {"grade": 1, "lesson_ids": []},
        "problem_form": "calculation",
        "target_difficulty": 13,
        "unlearned_lesson_ids": [],
    }
    r = client.post("/problems/generate", json=payload)
    assert r.status_code == 400


def test_teachers_declare_and_get() -> None:
    r = client.post(
        "/teachers/unlearned",
        json={"class_id": "test-class-1", "unlearned_lesson_ids": ["g3_l51"]},
    )
    assert r.status_code == 200
    r = client.get("/teachers/unlearned/test-class-1")
    assert r.status_code == 200
    assert r.json()["unlearned_lesson_ids"] == ["g3_l51"]


def test_index_html_served() -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "mongene-v2" in r.text
    assert "katex" in r.text.lower()


def test_openapi_docs_available() -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/problems/generate" in paths
    assert "/problems/lessons" in paths
    assert "/teachers/unlearned" in paths
