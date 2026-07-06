"""`scripts/build_ground_truth_corpus._inspect` への pinned seed 注入の検証（LLMフリー）。

`/problems/inspect` に送る payload に、level_label 由来の pinned_seed が
正しく載ることを、TestClient をモックして確認する。実際の inspect 呼び出しは行わない
（別途 tests/test_seed_injection.py 等が実際の生成を通した決定論を検証している）。
"""
from __future__ import annotations

from typing import Any

from scripts.build_ground_truth_corpus import _inspect
from scripts.corpus_seed import pinned_seed


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.status_code = 200
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _RecordingClient:
    """client.post を呼んだ際の json 引数を記録するフェイク TestClient。"""

    def __init__(self) -> None:
        self.last_payload: dict[str, Any] | None = None

    def post(self, path: str, json: dict[str, Any]) -> _FakeResponse:
        self.last_payload = json
        return _FakeResponse({"echo": json})


def test_inspect_injects_pinned_seed_when_level_label_given() -> None:
    client = _RecordingClient()
    lesson_mapping = {"grade": 1}

    _inspect(client, "g1_l1", lesson_mapping, "word_problem", 1, level_label="min")

    assert client.last_payload is not None
    expected_seed = pinned_seed("g1_l1", "word_problem", "min")
    assert client.last_payload["seed"] == expected_seed


def test_inspect_omits_seed_when_level_label_not_given() -> None:
    client = _RecordingClient()
    lesson_mapping = {"grade": 1}

    _inspect(client, "g1_l1", lesson_mapping, "word_problem", 1)

    assert client.last_payload is not None
    assert "seed" not in client.last_payload


def test_inspect_payload_shape_unchanged_besides_seed() -> None:
    client = _RecordingClient()
    lesson_mapping = {"grade": 2}

    _inspect(client, "g2_l3", lesson_mapping, "calculation", 3, level_label="mid")

    payload = client.last_payload
    assert payload["curriculum"] == {"grade": 2, "lesson_ids": ["g2_l3"]}
    assert payload["problem_form"] == "calculation"
    assert payload["target_level"] == 3
    assert payload["unlearned_lesson_ids"] == []
