"""作業0 の物差しを**合成データ**で確かめる（畳むほうと畳まないほうの両方）。

0件も全件も出す走査は疑う。ここは engine を一切呼ばず、`type_key` に手で作った
params・narration・問題文を渡して、**畳む場合と畳まない場合が両方出る**ことを見る。

`type_key` の `universe`（語彙集合）は**セル共通**で、seed ごとに変えてはいけない。
だから各ケースは a と b に**同じ universe** を渡す（実装と同じ使い方をする）。

実行: .venv/bin/python records/work/check_type_split.py
"""
import sys

from engine.core.contracts import ProofAnswer, SymbolicAnswer

sys.path.insert(0, "records/work")
from build_corpus import (
    _conclusion_text,
    mask_vocab,
    structural_paths,
    type_key,
    vocab_of,
)

FAIL = 0


def case(name: str, a: tuple, b: tuple, same: bool, universe: tuple = ()) -> None:
    """a と b の文型が同じ（same=True）／別（same=False）であることを見る。

    a, b は (params, narration, axes, 問題文 or None)。
    """
    global FAIL
    ka = type_key(a[0], a[1], a[2], a[3] if len(a) > 3 else None, universe)
    kb = type_key(b[0], b[1], b[2], b[3] if len(b) > 3 else None, universe)
    got = ka == kb
    ok = got == same
    FAIL += 0 if ok else 1
    print(f"{'OK  ' if ok else 'NG  '}{name}: 期待={'同じ' if same else '別'}"
          f" / 実際={'同じ' if got else '別'}")


# ① 語彙だけが違う → 同じ文型（charter が「段階2に入らない」と決めた違い）
case(
    "語彙だけ違う（品名）",
    ({"item_a": "りんご", "item_b": "レモン", "method": "elimination"},
     ("りんごの個数を x、レモンの個数を y とおく。",), []),
    ({"item_a": "おにぎり", "item_b": "パン", "method": "elimination"},
     ("おにぎりの個数を x、パンの個数を y とおく。",), []),
    same=True,
    universe=("りんご", "レモン", "おにぎり", "パン", "個"),
)
# ② slots の下の語彙だけが違う → 同じ文型
case(
    "語彙だけ違う（slots）",
    ({"slots": {"place_a": "家", "place_b": "駅"}},
     ("家から駅までの道のりを x km とおく。",), []),
    ({"slots": {"place_a": "A町", "place_b": "B町"}},
     ("A町からB町までの道のりを x km とおく。",), []),
    same=True,
    universe=("家", "駅", "A町", "B町"),
)
# ③ 数だけが違う → 同じ文型
case(
    "数だけ違う",
    ({"numbers": {"price": "140", "count": "12"}},
     ("代金の合計が 1530 円になる式をつくる。",), []),
    ({"numbers": {"price": "90", "count": "7"}},
     ("代金の合計が 810 円になる式をつくる。",), []),
    same=True,
)
# ④ 構成フラグが違う → 別の文型（畳んではいけない）
case(
    "構成フラグが違う",
    ({"item_a": "りんご", "method": "elimination"}, ("辺々を引いて x を消去する。",), []),
    ({"item_a": "りんご", "method": "substitution"}, ("一方を他方に代入する。",), []),
    same=False, universe=("りんご",),
)
# ⑤ 解く筋道（narration）の骨格が違う → 別の文型
case(
    "解く筋道が違う",
    ({"item_a": "りんご"}, ("和が合わせて買った個数に等しい式をつくる。",), []),
    ({"item_a": "りんご"}, ("差が d 個多いという式をつくる。",), []),
    same=False, universe=("りんご",),
)
# ⑥ `numbers` の下の日本語は構成として残す（和と積は数え上げの筋道が違う）
case(
    "numbers の下の日本語（和／積）",
    ({"numbers": {"target_quantity": "和", "target": "5"}, "slots": {"framing": "大小2個"}},
     ("2つのさいころの和が 5 になる場合を数える。",), []),
    ({"numbers": {"target_quantity": "積", "target": "6"}, "slots": {"framing": "大小2個"}},
     ("2つのさいころの積が 6 になる場合を数える。",), []),
    same=False, universe=("大小2個",),
)
# ⑦ 型の軸として宣言された値は伏せない（語彙に見えても構成）
case(
    "宣言された軸は伏せない",
    ({"prop_id": "対角線は互いに他を2等分する"}, ("平行四辺形の性質を使う。",), ["prop_id"]),
    ({"prop_id": "向かい合う角は等しい"}, ("平行四辺形の性質を使う。",), ["prop_id"]),
    same=False,
)
# ⑧ 問題文の骨格まで見る場合も、語彙だけの違いは畳む。
#    助数詞（個・枚）は params に出てこないので、**YAML のカタログの値**を
#    universe に入れないと残ってしまう（`container_set: ["袋|玉|個", "箱|カード|枚"]`）。
_BAG = ("袋", "玉", "個", "箱", "カード", "枚", "赤", "青")
case(
    "問題文の骨格（語彙だけ違う・助数詞つき）",
    ({"slots": {"item": "玉"}}, (), [], "袋の中に赤い玉が3個入っている。"),
    ({"slots": {"item": "カード"}}, (), [], "箱の中に青いカードが5枚入っている。"),
    same=True, universe=_BAG,
)
# ⑨ その助数詞を universe に入れなければ**畳まれない**（＝伏せ字が効いている裏取り）
case(
    "助数詞を渡さないと畳まれない",
    ({"slots": {"item": "玉"}}, (), [], "袋の中に赤い玉が3個入っている。"),
    ({"slots": {"item": "カード"}}, (), [], "箱の中に青いカードが5枚入っている。"),
    same=False,
)
# ⑩ 計算式は語彙ではない（`×÷²−` は ASCII ではないが、かな・漢字を含まない）。
#    ★「ASCII でない文字を含む」で語彙を選んだら `given_disp` の `1/6×8×(-3.5)` が
#    まるごと伏せ字になり、g1_l6.calculation.Lv2 の3型が1型に潰れた。
case(
    "計算式は語彙ではない",
    ({"given_disp": "1/6×8×(-3.5)", "mode": "multiplication_chain"}, (), [],
     "1/6×8×(-3.5) を計算せよ。"),
    ({"given_disp": "(-5/7)×(-6)×(-0.8)", "mode": "multiplication_chain"}, (), [],
     "(-5/7)×(-6)×(-0.8) を計算せよ。"),
    same=False,
)
# ⑪ 単位や記号だけの値も語彙ではない（伏せると単位の違いが消える）
case(
    "単位つきの式は語彙ではない",
    ({"disp": "3cm²"}, ("面積を求める。",), [], "3cm² の正方形の1辺を求めよ。"),
    ({"disp": "3cm³"}, ("体積を求める。",), [], "3cm³ の立方体の1辺を求めよ。"),
    same=False,
)
# ⑫ ★**1文字の語彙が熟語に当たっても型は割れない**（seed ごとに universe を変えない）。
#    引いた値だけを伏せていたときは、`unit="回"` の seed だけ「上回る」が消えて
#    g1_l56.graph_table.Lv3 の1文型が3文型に割れた。
_UNITS = ("cm", "回", "分", "点")
case(
    "1文字の単位が熟語に当たっても割れない",
    ({"unit": "回"}, ("折れ線がその高さを初めて上回る位置を見つける。",), []),
    ({"unit": "分"}, ("折れ線がその高さを初めて上回る位置を見つける。",), []),
    same=True, universe=_UNITS,
)
case(
    "1文字の単位が熟語に当たっても割れない（半分）",
    ({"unit": "分"}, ("縦軸で総度数の半分にあたる高さを決める。",), []),
    ({"unit": "cm"}, ("縦軸で総度数の半分にあたる高さを決める。",), []),
    same=True, universe=_UNITS,
)

# ⑬ 答えは鍵に**入れない**（入れると数が型として戻ってくる）。
#    ★入れたら g1_l13.calculation.Lv2 が 1 → 59 型、全体で 943 → 1650 型になった。
#    答えは「置き場所が語彙かどうか」の判定にだけ使う（⑭⑮）。
case(
    "答えが違っても数だけの違いなら同じ文型",
    ({"slots": {"item": "りんご"}}, ("代金の合計の式をつくる。",), []),
    ({"slots": {"item": "りんご"}}, ("代金の合計の式をつくる。",), []),
    same=True, universe=("りんご",),
)


def rows(*triples):
    """(値, 答え) の並びから structural_paths 用の行を作る。"""
    return [(i, {"slots": {"target": v}}, (), (a,)) for i, (v, a) in enumerate(triples)]


# ⑭ 答えがその置き場所の値の関数になっているなら、それは語彙ではなく構造。
#    g3_l57.word_problem.Lv2: 調査の場面16通りで答えが「全数調査／標本調査」に分かれる。
got = structural_paths(
    rows(("放送局", "標本調査"), ("放送局", "標本調査"),
         ("図書館", "全数調査"), ("図書館", "全数調査")),
    [], ("放送局", "図書館"),
)
ok = got == {"slots.target"}
FAIL += 0 if ok else 1
print(f"{'OK  ' if ok else 'NG  '}答えを決めている置き場所は構造: {got}")

# ⑮ 値が1回ずつしか出ないなら判定しない（品名40通りのセルが全部構造になるのを防ぐ）
got = structural_paths(
    rows(("りんご", "正の数"), ("レモン", "負の数"),
         ("パン", "正の数"), ("みかん", "負の数")),
    [], ("りんご", "レモン", "パン", "みかん"),
)
ok = got == set()
FAIL += 0 if ok else 1
print(f"{'OK  ' if ok else 'NG  '}値が1回ずつなら構造とみなさない: {got}")

# ⑯ 答えが値の関数でないなら語彙のまま（同じ値で答えが2通り出ている）
got = structural_paths(
    rows(("放送局", "標本調査"), ("放送局", "全数調査"),
         ("図書館", "全数調査"), ("図書館", "標本調査")),
    [], ("放送局", "図書館"),
)
ok = got == set()
FAIL += 0 if ok else 1
print(f"{'OK  ' if ok else 'NG  '}答えが値の関数でないなら語彙: {got}")


# 証明の全文は鍵に入れない（入れると seed ごとに文面が変わって型が爆発する）
proof = ProofAnswer(text="△ABCと△DEFにおいて…（毎回変わる本文）")
symbolic = SymbolicAnswer(srepr="Integer(7)", display="x = 7")
ok = _conclusion_text(proof) == "" and _conclusion_text(symbolic) == "x = 7"
FAIL += 0 if ok else 1
print(f"{'OK  ' if ok else 'NG  '}証明の本文は鍵に入れない / 数値の答えは入れる")

# 語彙の選び方そのものも見る（何も選べていなければ①〜③は「たまたま」通る）
v = vocab_of({"item_a": "りんご", "method": "elimination",
              "given_disp": "1/6×8×(-3.5)",
              "numbers": {"price": "140", "color": "赤"},
              "slots": {"item": "玉"}}, [])
want = {"りんご": "〈item_a〉", "玉": "〈slots.item〉"}
ok = sorted(v) == sorted(want)  # 式（given_disp）と numbers の下は語彙に入らない
FAIL += 0 if ok else 1
print(f"{'OK  ' if ok else 'NG  '}語彙の選び方: {sorted(v)}")

# 伏せ字そのもの（長いものから当てているか）
got = mask_vocab("A町からB町まで歩いた。", ("町", "A町", "B町"))
ok = got == "〈語彙〉から〈語彙〉まで歩いた。"
FAIL += 0 if ok else 1
print(f"{'OK  ' if ok else 'NG  '}長い語彙を先に伏せる: {got}")

print(f"\n{'すべて期待どおり' if FAIL == 0 else f'期待と違うもの {FAIL} 件'}")
sys.exit(1 if FAIL else 0)
