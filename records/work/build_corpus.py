"""「明らかに違う問題」を、単元・form・Lv ごとに、型を全部出す。

## 何を1問とするか
**セルをまたいだ重複除去はしない。** 同じ単元・form で Lv だけ違えば、型が同じでも
別々に1問出す（Lv 差が数値の範囲だけで付いているセルもあるため）。
1セルの中では、型の数だけ出す。

## 型の見分け方
family YAML の params にある列挙のうち、**話の骨格が変わる軸**だけを型とみなす。
軸か中身かは設計が記録していないので、名前の規約でここに明文化する:

  型の軸  `*_set`（concept_set を除く）・`term_kinds`  ただし人名・題材・品物・場所・
          色を指す `*_set` は中身なので除く（person_pair_set・subject_set など）
  中身    `*_candidates`・`*_range`・`*_domain`・`*_pool`

これに加えて **解く筋道の言葉（narration）** も鍵に混ぜる。YAML に出ない分岐
（g2_l38 Lv3 の「証明する枝」と「反例を出す枝」）はこれでしか拾えない。

## seed の引き方
型は rng が引くので、狙って出せない。**期待する型数だけ出るまで seed を増やす**
（上限あり）。取りこぼしたら `log` に出す——黙って打ち切ると「全部見た」と読めてしまう。

実行: PYTHONPATH=engine_core .venv/bin/python records/work/build_corpus.py
"""
from __future__ import annotations

import glob
import argparse
import json
import os
import re
from pathlib import Path

import yaml

from engine.core.contracts import Coordinate, GenerateRequest, Unsupported
from engine.core.pipeline import generate
from engine.eval._harness import build_mr, make_env

# **出力先は外から差せる。** ここが `records/work/corpus` 固定だったので、
# `engine_core/` だけをメインプロジェクトへ移すと「生成はできるが結果がどこにも
# 残らない」状態になっていた（引き継ぎ書 §3 の穴）。
# 優先順: 引数 --out > 環境変数 MONGENE_CORPUS_DIR > 既定（このリポジトリの場所）。
_DEFAULT_OUT = Path(os.environ.get("MONGENE_CORPUS_DIR", "records/work/corpus"))

# 名前は `_set` でも、中身の差し替えでしかない軸。
_FILLER_HINTS = ("person", "subject", "item", "color", "place", "object", "name")
_SEEDS_PER_TYPE = 60      # 型1つあたり、これだけ seed を引いてみる
_SEED_CAP = 2400          # 1セルの上限


def _answer_text(answer: object) -> str:
    """答えの表示。**選択肢と作図にも文字列を出す**（走査に見えるようにするため）。

    `display` を持つのは数値・式・証明の答えだけで、選択（ChoiceAnswer）は `correct`、
    作図とグラフ（GraphAnswer）は特徴点の並びが答えにあたる。ここが空だと
    「答えが空」が213セルに出て、その中の欠陥（分数の相対度数など）を文面の走査が
    一度も見ないままになる。
    """
    display = getattr(answer, "display", None)
    if display:
        return str(display)
    correct = getattr(answer, "correct", None)
    if correct:
        return str(correct)
    features = getattr(answer, "features", None)
    if features:
        # **`f.kind` を前に足さない。** 足していたので `intersection 交点 (-1, 6)`・
        # `min 最小値 6` と出て、「答えに英語のスロット名が漏れている」と読み違えた。
        # 漏れていたのはこの道具のほうで、engine は `f.display` しか出していない
        # （どの display も日本語のラベルを持っている）。
        # 読む道具が足したものは、読む人には engine の出力と区別できない。
        return "、".join(f.display for f in features)
    return str(getattr(answer, "text", "") or "")


def type_axes(params: dict) -> list[str]:
    """型の軸になる params のキー。

    **数値だけの列挙は型ではない。** `denominator_set: [2,3,4,5,6,8,9,10]` は
    `x/9 + x/2 = 33` と `x/10 + x/6 = 8` を作り分けるだけで、問題の型は同じである
    （最初これを型と数えて、8型あることにしてしまった）。
    """
    out = []
    for k, v in params.items():
        if not (isinstance(v, list) and len(v) > 1):
            continue
        if not (k.endswith("_set") and k != "concept_set" or k == "term_kinds"):
            continue
        if any(h in k for h in _FILLER_HINTS):
            continue
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
            continue  # 数値の列挙＝中身の差し替え
        out.append(k)
    return sorted(out)


def _mask_names(v: object) -> object:
    """点名（連続する大文字）を伏せる。数字と日本語はそのまま。

    型の鍵に使う。`labels` のような表層の軸が鍵に入っていると、名前だけ違う問題が
    別の型になる。文字列以外はそのまま返す（数値の軸は伏せてはいけない）。
    """
    if isinstance(v, str):
        return re.sub(r"[A-Z]", "＊", v)
    if isinstance(v, (list, tuple)):
        return [_mask_names(x) for x in v]
    return v


def text_skeleton(text: str) -> str:
    """問題文から数字を落とした骨格（話が違えばここが変わる）。

    `scene_set` のように**カタログが params に載らない**セルがある（場面は問題文を
    変えるのに、params には数値しか残らない）。名前でも値でも対応づけられないので、
    最後は問題文そのものの形で見分ける。

    ★**点名（大文字）も落とす。** 落としていなかったので、数値も場面も同じで
    頂点名だけ違う問題を別の型として数え、問題集に同じ問題が2回載っていた
    （実測 12問/6組）。`dup_key` から表層を外したのと同じ理由——
    **名前が違うだけの問題は別の問題ではない**。
    """
    return re.sub(r"[A-Z]", "＊", re.sub(r"\d+", "#", text))


def load_cells() -> list[tuple[str, str, int, list[set], int]]:
    """(unit, form, level, カタログの値の集合たち, 期待する型数) を family YAML から作る。

    **軸は名前で照合できない。** YAML は `proof_set` と宣言するが、MR に載るのは
    `proof_id` である（`scene_set` → `scene` も同様）。名前の対応は設計が持っていないので、
    **値の集合**を持ち回り、MR のどのパラメータがその集合から値を取っているかを
    実測で対応づける（`match_axis_keys`）。
    """
    cells = []
    for path in sorted(glob.glob("engine_core/engine/curriculum/math/families/*.yaml")):
        doc = yaml.safe_load(open(path, encoding="utf-8"))
        unit, form = doc["family"].removeprefix("math.").rsplit(".", 1)
        for lv, spec in (doc.get("levels") or {}).items():
            params = spec.get("params") or {}
            catalogs = []
            expected = 1
            for a in type_axes(params):
                values = {json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)
                          for v in params[a]}
                catalogs.append(values)
                expected *= len(params[a])
            cells.append((unit, form, int(lv), catalogs, expected))
    # **中1 → 中2 → 中3 → 入試の順に並べる。** ファイル名順（sorted(glob)）だと
    # exam が先頭に来て、レッスン番号も文字列順（g1_l1 → g1_l10 → g1_l2）になる。
    grade_order = {"g1": 0, "g2": 1, "g3": 2, "exam": 3}
    form_order = {
        "knowledge": 0, "calculation": 1, "find_value": 2, "graph_table": 3,
        "construction": 4, "proof": 5, "word_problem": 6,
    }

    def key(c: tuple) -> tuple:
        grade, _, lesson = c[0].partition("_l")
        return (grade_order.get(grade, 9), int(lesson or 0), form_order.get(c[1], 9), c[2])

    return sorted(cells, key=key)


def match_axis_keys(rows: list[dict], catalogs: list[set]) -> list[str]:
    """MR params のうち、カタログの値を取っているキーを見つける（値で照合）。"""
    observed: dict[str, set[str]] = {}
    for params in rows:
        for k, v in params.items():
            observed.setdefault(k, set()).add(
                json.dumps(v, ensure_ascii=False, sort_keys=True, default=str)
            )
    keys: list[str] = []
    for values in catalogs:
        for k, seen in sorted(observed.items()):
            if k in keys:
                continue
            # そのキーの観測値がすべてカタログに含まれ、2つ以上の値を取っていること
            if len(seen) > 1 and seen <= values:
                keys.append(k)
                break
    return keys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="build_corpus", description="全セルの型を書き出す（生成物の置き場は --out）"
    )
    parser.add_argument(
        "--out", type=Path, default=_DEFAULT_OUT,
        help="生成物の出力先（既定: 環境変数 MONGENE_CORPUS_DIR か records/work/corpus）",
    )
    args = parser.parse_args()
    out_dir: Path = args.out
    figs_dir = out_dir / "figs"
    figs_dir.mkdir(parents=True, exist_ok=True)
    env = make_env()
    try:
        import cairosvg  # noqa: PLC0415
    except ImportError:
        cairosvg = None  # type: ignore[assignment]

    lines: list[str] = [
        "# 生成できる問題の全型（単元・form・Lv ごと）\n",
        "セルをまたいだ重複除去はしていない。1セルにつき最低1問、"
        "型が複数あるセルはその全部。\n",
    ]
    shortfalls: list[str] = []
    n_problems = n_figs = 0

    for unit, form, level, catalogs, expected in load_cells():
        coord = Coordinate(subject="math", unit=unit, form=form, level=level)
        cell = f"{unit}.{form}.Lv{level}"
        budget = min(_SEED_CAP, max(_SEEDS_PER_TYPE, expected * _SEEDS_PER_TYPE))

        # まず引けるだけ引いて、params と narration を貯める。
        seen_rows: list[tuple[int, dict, tuple]] = []
        for seed in range(1, budget + 1):
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                continue
            narration = tuple(
                s.narration for sq in r.mr.sub_questions for s in (sq.steps or ())
            )
            seen_rows.append((seed, dict(r.mr.params), narration))
            if len(seen_rows) >= _SEEDS_PER_TYPE * max(1, expected):
                break

        # カタログの値を取っているキーを、値で対応づける。
        axes = match_axis_keys([p for _, p, _ in seen_rows], catalogs)
        # 対応づかないカタログが残ったら、問題文の骨格で見分ける（scene_set など）。
        use_text = len(axes) < len(catalogs)
        found: dict[str, int] = {}
        labels: dict[str, str] = {}   # 鍵 → 読めるラベル（鍵を読み直さない）
        for seed, params, narration in seen_rows:
            # ★点名（大文字）は鍵から落とす。narration には「三角形ABCと三角形EDCで」
            # のように点名が入るので、落とさないと**数値も場面も同じで名前だけ違う
            # 問題を別の型として数え、問題集に同じ問題が2回載る**（実測 12問/6組）。
            # `dup_key` から表層を外したのと同じ理由。
            masked = [_mask_names(s) for s in narration]
            parts: list[object] = [[a, _mask_names(params.get(a))] for a in axes] + [masked]
            if use_text:
                res = generate(
                    GenerateRequest(subject="math", unit=unit, form=form,
                                    level=level, seed=seed),
                    curriculum=env.curriculum, families=env.families,
                    registry=env.registry,
                )
                if isinstance(res, Unsupported):
                    continue
                parts.append(text_skeleton(res.problem_text))
            key = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
            if key not in found:
                found[key] = seed
                axis_part = "・".join(
                    f"{a}={params.get(a)}" for a in axes if params.get(a) is not None
                )
                labels[key] = axis_part or ("場面ちがい" if use_text else "（軸なし）")
            if use_text and len(found) >= expected:
                break
        if len(found) < expected:
            shortfalls.append(f"{cell}: 期待 {expected} 型 / 出たのは {len(found)} 型")

        lines.append(f"\n---\n\n## {cell}  — 型 {len(found)} 個"
                     + (f"（軸: {', '.join(axes)}）" if axes else ""))
        for i, (key, seed) in enumerate(sorted(found.items(), key=lambda kv: kv[1]), start=1):
            res = generate(
                GenerateRequest(subject="math", unit=unit, form=form, level=level, seed=seed),
                curriculum=env.curriculum, families=env.families, registry=env.registry,
            )
            if isinstance(res, Unsupported):
                lines.append(f"\n### 型{i}  （生成不可: {res.code}）\n")
                continue
            n_problems += 1
            sq = res.sub_questions[0]
            multi = len(res.sub_questions) > 1
            # **答えは全小問ぶん出す。** 1つ目しか出していなかったので、(2)(3) の答えを
            # 走査が一度も見ていなかった。選択肢の答え（ChoiceAnswer）と作図の答え
            # （GraphAnswer）も出す——これらが空欄だったため「答えが空」が213セルに
            # 出ていて、その中の欠陥は文面の走査に一度もかからなかった。
            ans = " ／ ".join(
                f"{s.label} {_answer_text(s.answer)}" if multi else _answer_text(s.answer)
                for s in res.sub_questions
            )
            # **解説とヒントも全小問ぶん出す（2026-08-16）。** 答えだけを直して
            # ここを `sub_questions[0]` のままにしていたので、(2) 以降の解説を
            # 走査も読み手も一度も見ていなかった。連立方程式の「消去して解く」段は
            # 小問(2)にあるのに、読むと「式を立てて終わっている」ように見えていた
            # ——**同じ根（1つ目しか出さない）の別の出口**。
            exp = "\n\n".join(
                (f"{s.label} {s.explanation}" if multi else str(s.explanation))
                for s in res.sub_questions if s.explanation
            )
            hints = " ／ ".join(
                (f"{s.label} " if multi else "") + " / ".join(s.hints)
                for s in res.sub_questions if s.hints
            )

            fig = "（図なし）"
            if res.visual_svg:
                stem = f"{unit}_{form}_Lv{level}_{i}"
                (figs_dir / f"{stem}.svg").write_text(res.visual_svg, encoding="utf-8")
                fig = f"records/work/corpus/figs/{stem}.svg"
                if cairosvg is not None:
                    cairosvg.svg2png(
                        bytestring=res.visual_svg.encode("utf-8"),
                        write_to=str(figs_dir / f"{stem}.png"), output_width=520,
                    )
                    fig = f"records/work/corpus/figs/{stem}.png"
                n_figs += 1

            lines.append(f"\n### 型{i}  `{labels[key]}`  (seed {seed})\n")
            lines.append(f"**問題**\n\n{res.problem_text}\n")
            lines.append(f"**問い** {sq.prompt_text}\n")
            lines.append(f"**図** {fig}\n")
            lines.append(f"**答え** {ans}\n")
            lines.append(f"**解説**\n\n{exp}\n")
            if hints:
                lines.append(f"**ヒント** {hints}\n")

    if shortfalls:
        lines.insert(2, "\n## 取りこぼした型（seed を引き切れなかったセル）\n\n"
                     + "\n".join(f"- {s}" for s in shortfalls) + "\n")

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "INDEX.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"問題 {n_problems} 個 / 図 {n_figs} 枚 → {out_dir / 'INDEX.md'}")
    if shortfalls:
        print(f"取りこぼし {len(shortfalls)} セル（INDEX.md の冒頭に列挙した）")


if __name__ == "__main__":
    main()
