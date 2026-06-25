"""個別最適化・完全習得ループの E2E テスト（生成はモック: SKIP_LLM_IN_TESTS）。

検証:
  生徒作成 → /learning/next で出題 → 既知 sympy_form を自動採点 → 習熟更新 →
  反復で mastered=True → 次 lesson がアンロックされる。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # 一時 DB にストアを差し替え（他テスト・本番 DB と分離）
    db = Path(tempfile.mkdtemp()) / "loop_test.db"
    monkeypatch.setenv("ADAPTIVE_DB_PATH", str(db))
    from apps.api.src.domains.learning import deps

    deps.reset_store_for_tests(str(db))
    from apps.api.main import app

    return TestClient(app)


def _create_student(client: TestClient, grade: int = 1) -> str:
    r = client.post("/students", json={"grade": grade})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _correct_answers(problem: dict) -> list[dict]:
    """生成問題の既知 sympy_form を「正答」として提出ペイロードを作る。"""
    out = []
    for sq in problem["sub_questions"]:
        ans = sq["answer"].get("sympy_form") or sq["answer"].get("text_form") or ""
        out.append({"label": sq["label"], "answer": ans})
    return out


def test_create_and_fetch_student(client: TestClient) -> None:
    sid = _create_student(client, grade=2)
    r = client.get(f"/students/{sid}")
    assert r.status_code == 200
    assert r.json()["grade"] == 2


def test_next_unknown_student_404(client: TestClient) -> None:
    r = client.post("/learning/next", json={"student_id": "nope"})
    assert r.status_code == 404


def test_submit_unknown_problem_404(client: TestClient) -> None:
    sid = _create_student(client)
    r = client.post("/learning/submit", json={"student_id": sid, "problem_id": "nope", "answers": []})
    assert r.status_code == 404


def test_next_returns_calculation_problem_with_known_answer(client: TestClient) -> None:
    sid = _create_student(client, grade=1)
    r = client.post("/learning/next", json={"student_id": sid})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["problem_id"]
    assert data["lesson_id"].startswith("g1_")
    assert 1 <= data["target_difficulty"] <= 100
    assert len(data["problem"]["sub_questions"]) >= 1
    # 自動採点可能な解答(sympy_form)を持つ
    assert any(sq["answer"].get("sympy_form") for sq in data["problem"]["sub_questions"])


def test_correct_answer_is_graded_correct(client: TestClient) -> None:
    sid = _create_student(client, grade=1)
    nxt = client.post("/learning/next", json={"student_id": sid}).json()
    payload = {"student_id": sid, "problem_id": nxt["problem_id"], "answers": _correct_answers(nxt["problem"])}
    r = client.post("/learning/submit", json=payload)
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["overall_correct"] is True
    assert res["mastery"]["correct_streak"] == 1


def test_wrong_answer_resets_streak(client: TestClient) -> None:
    sid = _create_student(client, grade=1)
    # 1問正解 → streak 1
    nxt = client.post("/learning/next", json={"student_id": sid}).json()
    client.post("/learning/submit", json={"student_id": sid, "problem_id": nxt["problem_id"], "answers": _correct_answers(nxt["problem"])})
    # 次は誤答 → streak 0
    nxt2 = client.post("/learning/next", json={"student_id": sid}).json()
    wrong = [{"label": sq["label"], "answer": "999999"} for sq in nxt2["problem"]["sub_questions"]]
    res = client.post("/learning/submit", json={"student_id": sid, "problem_id": nxt2["problem_id"], "answers": wrong}).json()
    assert res["overall_correct"] is False
    assert res["mastery"]["correct_streak"] == 0


def test_full_loop_reaches_mastery_and_advances(client: TestClient) -> None:
    sid = _create_student(client, grade=1)
    first_lesson = None
    mastered_lesson = None

    for _ in range(12):
        nxt = client.post("/learning/next", json={"student_id": sid})
        if nxt.status_code == 409:
            break  # 全習得
        assert nxt.status_code == 200, nxt.text
        nxt = nxt.json()
        if first_lesson is None:
            first_lesson = nxt["lesson_id"]
        payload = {"student_id": sid, "problem_id": nxt["problem_id"], "answers": _correct_answers(nxt["problem"])}
        res = client.post("/learning/submit", json=payload).json()
        # 自動採点で正答できているはず
        assert res["overall_correct"] is True, res
        if res["mastered"]:
            mastered_lesson = res["lesson_id"]
            break

    assert mastered_lesson is not None, "反復正答で習得に到達しなかった"
    # 習得した lesson が mastery サマリで mastered になっている
    summary = client.get(f"/students/{sid}/mastery").json()
    assert summary["mastered_count"] >= 1
    assert any(item["lesson_id"] == mastered_lesson and item["mastered"] for item in summary["lessons"])

    # 習得後の次手は別 lesson にアンロック（or 全習得で 409）
    nxt = client.post("/learning/next", json={"student_id": sid})
    if nxt.status_code == 200:
        assert nxt.json()["lesson_id"] != mastered_lesson
    else:
        assert nxt.status_code == 409
