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


def test_inspect_moving_point_calculation_now_generates() -> None:
    """g2_l29「動点の問題」の calculation は、かつて候補 blueprint（MovingPointStructure）が
    構造欠陥で凍結され未対応だったため honest 422 だったが、時間パラメトリックな
    MovingPointAreaVerb 実装で凍結解除（§9）。退化せず 200 で生成されることを回帰検知する。
    """
    payload = {
        "curriculum": {"grade": 2, "lesson_ids": ["g2_l29"]},
        "problem_form": "calculation",
        "target_difficulty": 6,
    }
    r = client.post("/problems/inspect", json=payload)
    assert r.status_code == 200


def test_inspect_rejects_undeclared_form() -> None:
    """mapping.supported_forms に宣言の無い form（g2_l29 に proof は無い）を要求すると、
    黙って別 form にフォールバックせず honest に拒否すること（200 で偽の結果を返さない）。
    """
    payload = {
        "curriculum": {"grade": 2, "lesson_ids": ["g2_l29"]},
        "problem_form": "proof",
        "target_difficulty": 6,
    }
    r = client.post("/problems/inspect", json=payload)
    assert r.status_code in (400, 422)
    assert "proof" in r.json()["detail"]


def test_inspect_supported_form_still_generates() -> None:
    """g1_l1 の knowledge form は execute_blueprint_by_form 経由で
    KnowledgeBaseStructure が選ばれ、これは supported_forms=["knowledge"] を
    満たすため、契約強制導入後も 200 で正常に生成されること（退化しない）。
    """
    payload = {
        "curriculum": {"grade": 1, "lesson_ids": ["g1_l1"]},
        "problem_form": "knowledge",
        "target_difficulty": 6,
    }
    r = client.post("/problems/inspect", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["blueprint_id"] == "KnowledgeBaseStructure"
    assert data["problem_form"] == "knowledge"


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
