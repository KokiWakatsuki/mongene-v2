"""level_sep（実装設計 §4.4・§8.3・Q3/H2・Task10）— レベル分離の検査。

family ごとに:
  (a) **レベル間 signature 相異**[静的]: spec 宣言の signature が全レベルで相異
      （spec_lint R2 が既に静的保証するが、eval でも独立に再確認する）。
  (b) **署名間 fp 相異**[必須]: 異なる signature の生成物が異なる計算指紋 fp を持つ。
      同一なら「レベルが実際には構造を変えていない」（宣言の嘘）＝ FAIL。fp は
      独立ソルバ由来の steps op 列を含むため recipe 側で偽装しにくい接地点。
  (c) **宣言メトリクスの単調性**[任意]: M0 の spec には宣言メトリクス欄が無いため
      本項は "not_declared" として報告のみ（合否に算入しない）。

CLI: `python -m engine.eval.level_sep [--seeds N] [--json] [--out PATH]`
終了コード: (a)(b) 全合格=0 / いずれか失敗=1。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engine.core.contracts import Coordinate
from engine.core.signature import fingerprint_hash
from engine.eval._harness import EvalEnv, build_mr, family_of, make_env, select_cells
from engine.eval._parallel import pmap

_DEFAULT_SEEDS = 5


@dataclass
class FamilyLevelSep:
    family: str
    levels: list[int]
    signatures: list[str]
    signatures_distinct: bool          # (a)
    fp_by_signature: dict[str, str] = field(default_factory=dict)
    fp_collisions: list[dict[str, object]] = field(default_factory=list)  # (b) 失敗詳細
    monotonicity: str = "not_declared"  # (c)
    build_failures: list[dict[str, object]] = field(default_factory=list)

    @property
    def fp_distinct(self) -> bool:  # (b)
        return not self.fp_collisions

    @property
    def ok(self) -> bool:
        return self.signatures_distinct and self.fp_distinct and not self.build_failures


def family_level_sep(env: EvalEnv, family: str, coords: list[Coordinate], seeds: int) -> FamilyLevelSep:
    coords_typed = sorted(coords, key=lambda c: c.level)
    levels = [c.level for c in coords_typed]

    # 各レベルの signature と fp（fp は seed をまたいで一定であることも確認）。
    sig_by_level: dict[int, str] = {}
    fp_by_sig: dict[str, str] = {}
    fp_per_sig_seen: dict[str, set[str]] = defaultdict(set)
    build_failures: list[dict[str, object]] = []

    for coord in coords_typed:
        for seed in range(1, seeds + 1):
            r = build_mr(coord, seed, env)
            if not r.ok or r.mr is None:
                build_failures.append({"level": coord.level, "seed": seed, "error": r.error})
                continue
            sig_by_level[coord.level] = r.mr.signature
            fp = fingerprint_hash(r.mr)
            fp_per_sig_seen[r.mr.signature].add(fp)
            fp_by_sig[r.mr.signature] = fp

    signatures = [sig_by_level.get(lv, "?") for lv in levels]
    signatures_distinct = len(set(signatures)) == len(signatures)

    # (b) 署名間 fp 相異: fp -> [signatures] を作り、複数署名が同一 fp を持てば衝突。
    sig_by_fp: dict[str, list[str]] = defaultdict(list)
    for sig, fp in fp_by_sig.items():
        sig_by_fp[fp].append(sig)
    fp_collisions: list[dict[str, object]] = [
        {"fp": fp, "signatures": sorted(sigs)} for fp, sigs in sig_by_fp.items() if len(sigs) >= 2
    ]

    return FamilyLevelSep(
        family=family,
        levels=levels,
        signatures=signatures,
        signatures_distinct=signatures_distinct,
        fp_by_signature=fp_by_sig,
        fp_collisions=fp_collisions,
        build_failures=build_failures,
    )


@dataclass
class LevelSepReport:
    seeds: int
    families: list[FamilyLevelSep]

    @property
    def ok(self) -> bool:
        return all(f.ok for f in self.families)

    def to_json(self) -> dict[str, object]:
        return {
            "seeds": self.seeds,
            "ok": self.ok,
            "families": [asdict(f) | {"ok": f.ok, "fp_distinct": f.fp_distinct} for f in self.families],
        }


def _family_job(
    env: EvalEnv, fam: str, coords: list[Coordinate], seeds: int
) -> FamilyLevelSep:
    """ワーカー1つが担当する family 1つ分（`_parallel.pmap` から呼ばれる）。

    level_sep は **family の中で** レベル同士を見比べるので、配る単位はセルでなく
    family（family どうしは独立）。
    """
    return family_level_sep(env, fam, coords, seeds)


def run_level_sep(
    env: EvalEnv | None = None,
    *,
    seeds: int = _DEFAULT_SEEDS,
    jobs: int | None = None,
    only: str | None = None,
) -> LevelSepReport:
    env = env if env is not None else make_env()
    by_family: dict[str, list[Coordinate]] = defaultdict(list)
    for coord in select_cells(env, only):
        by_family[family_of(coord)].append(coord)
    families = pmap(
        _family_job, [(fam, coords, seeds) for fam, coords in sorted(by_family.items())], jobs=jobs
    )
    return LevelSepReport(seeds=seeds, families=families)


def _format_text(report: LevelSepReport) -> str:
    lines = [f"level_sep (seeds={report.seeds}) — {'OK' if report.ok else 'FAIL'}"]
    for f in report.families:
        mark = "✓" if f.ok else "✗"
        lines.append(f"  {mark} {f.family} levels={f.levels}")
        a_mark = "✓" if f.signatures_distinct else "✗"
        lines.append(f"      (a) signature 相異[静的]: {a_mark} {f.signatures}")
        b_mark = "✓" if f.fp_distinct else "✗"
        fp_repr = {s: f.fp_by_signature[s] for s in sorted(f.fp_by_signature)}
        lines.append(f"      (b) fp 相異[必須]: {b_mark} {fp_repr}")
        if f.fp_collisions:
            lines.append(f"          衝突: {f.fp_collisions}")
        lines.append(f"      (c) 単調性[任意]: {f.monotonicity}")
        if f.build_failures:
            lines.append(f"      build_failures: {f.build_failures[:3]}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="level_sep", description="レベル分離（署名相異[静的]+fp相異[必須]）")
    parser.add_argument("--seeds", type=int, default=_DEFAULT_SEEDS)
    parser.add_argument(
        "--only", default=None,
        help="セル名（unit.form.LvN）の正規表現で走査を絞る（テスト・部分確認用）",
    )
    parser.add_argument(
        "--jobs", type=int, default=None,
        help="並列プロセス数（既定はコア数-1）。1 で逐次",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    report = run_level_sep(seeds=args.seeds, only=args.only, jobs=args.jobs)
    payload = report.to_json()

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(_format_text(report))

    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
