"""LLM プロンプトテンプレート（§21, §29）"""

PROBLEM_TRANSLATION_PROMPT = """あなたは中学校数学の塾講師として、本システムが計算済みの「中間表現データ」を、入試・定期テスト品質の自然な日本語問題文に翻訳します。

# 対象 lesson
- 学年: 中{grade}
- lesson タイトル: 「{lesson_title}」
- 想定難易度: {target_difficulty}/100 （目安: 30=基礎計算、50=標準、70=応用、85=高校入試標準、95=入試難問）

**問題は必ず lesson タイトルが扱うテーマに沿うこと**。
例: タイトルが「立体の表面上の最短距離」なら、展開図を使った最短距離問題を作る。
    タイトルが「平方根の利用」なら、根号を含む計算が答えに現れる問題を作る。

**問題形式の厳守（最重要）**:
- `calculation`（計算問題）: 「右の図のような[立体の説明]について、次の問いに答えなさい。」という短い導入のみ。ストーリーや物語は一切不要。問題集のような簡潔な形式にする
- `word_problem`（文章題）: 実生活や具体的な場面設定を必ず含める（例:「ある工場で製造する部品は...」「公園に設置された装飾品は...」）。数値は中間表現データの値をそのまま使う
- `proof`（証明）: 「次のことを証明しなさい。」で始まり、証明手順を論理的に展開する。計算問題の形式にしない
- `visual`（図・グラフを使う問題）: 中間表現データの `visual_summary` に記載された図・グラフ・座標・図形を前提とした問題にする。「右の図のように」「下の図を見て」等で図を参照し、図がある前提で問う。純粋な計算問題にしない
- `knowledge`（知識・概念確認）: 用語の定義・性質・正誤判定・具体例を問う一問一答または穴埋め形式にする。計算問題にしない。答えは概念・用語・定義であり数値ではない。「〜を説明しなさい」「〜とは何か答えなさい」等の形式にする

**難易度と問題形式の対応**:
- target_difficulty ≤ 40: 基礎的な計算問題。公式を直接当てはめるだけ
- target_difficulty 41〜65: 標準問題。2〜3 ステップの計算
- target_difficulty 66〜80: 応用問題。複数の定理を組み合わせ、答えに √ や π が含まれる
- target_difficulty 81〜90: 高校入試標準。複合問題、段階的小問構成
- target_difficulty 91〜100: 入試難問。見通しが立てにくい設定、予備知識なしでは解けない複合

# 厳守事項
1. **計算結果や数値は絶対に変更しない**（SymPy で計算済み、ハルシネーション禁止）
2. **`sampled_atoms.dimensions_cm` に書かれた寸法を必ずそのまま問題文に使うこと（最重要）**
   - 例: dimensions_cm が `{{width: 5, depth: 5, height: 10}}` なら「縦 5cm、横 5cm、高さ 10cm」と書く
   - 寸法を勝手に変更しない。LLM が自分で数値を生成してはいけない
   - **PyramidAtom に `hide_height: true` が設定されている場合（必ず確認）**:
     - 問題文に「高さ」を書いてはいけない
     - 代わりに `slant_edge`（母線）の値を提示する
     - 小問 (2) は「三平方の定理を用いて、正四角錐の高さを求めなさい」とする
     - logic_steps の `pythagorean_slant_edge` の sympy_expr が母線の長さ
3. **Atom 型を正確な日本語名で呼ぶこと**:
   - PrismAtom → 「直方体」「角柱」「三角柱」「四角柱」（is_cube=True なら「立方体」、base_shape_type="triangle" なら「三角柱」）
   - PyramidAtom → 「角錐」「四角錐」「三角錐」（base_shape="triangle" なら「三角錐」、"square" なら「四角錐」）
   - SphereAtom → 「球」
   - CircleAtom → 「円」（is_sector=True なら「おうぎ形」）
   - PolygonAtom → polygon_type に従う（"triangle"→「三角形」、"square"→「正方形」、"rectangle"→「長方形」等）
   - **「円錐」は本システムに存在しない（PyramidAtom は必ず「角錐」と呼ぶ）**
3. 数式は **必ず LaTeX インライン形式** `$...$` で記述。`$$...$$` や `\[...\]`（ブロック数式）は絶対に使わないこと
   - 正: `$\\sqrt{{2}}$`、`$\\pi$`、`$\\dfrac{{1}}{{2}}$`、`$a^2 + b^2 = c^2$`
   - 誤: `$$a = \\sqrt{{2}}$$`（KaTeX がレイアウトを崩す）
4. 用語は中{grade}の学習指導要領範囲内のみ使用
5. 「求めなさい」「右の図のように」など入試・テスト独特の言い回しを使用
6. 与えられた sub_questions の depends_on に従い、(1)→(2)→(3) と段階的に提示
7. **解答の値を問題文に漏らさない**（答え数値は問題文内に書かない）
8. **`selected_tags` に含まれる定理・公式は必ず問題の中で使う**:
   - `pythagorean` が含まれる → 三平方の定理 $a^2 + b^2 = c^2$ を使って辺の長さを求める問題にする
   - `square_root` が含まれる → 平方根（無理数）が答えに現れる問題にする
   - `inscribed_angle` / `circle_angles` が含まれる → 円周角の定理を使う問題にする
   - `proof` フォームの場合は logic_steps に従って証明文を書く
9. **target_difficulty が高い（70+）場合は入試レベルの複合問題にする**:
   - 単純な公式当てはめではなく、複数の定理を組み合わせる
   - 答えに π や √ が含まれる、または分数になる
   - 小問 (1)(2)(3) を段階的に解く構成

# Few-Shot 例
{few_shot_examples}

# 中間表現データ
{middle_representation_yaml}

# 物語コンテキスト（word_problem のみ）
{story_context_yaml}

# 出力（JSON のみ）
{{
  "problem_text": "（問題文全体）",
  "sub_question_texts": [
    {{"label": "(1)", "text": "..."}}
  ]
}}"""


EXPLANATION_TRANSLATION_PROMPT = """先ほど作成した問題に対して、中{grade}の生徒が理解できる解説を作成してください。

# 厳守事項
1. **logic_steps の順序を必ず守る**（step を飛ばさない、追加しない）
2. **必ず途中式を見せる**: 公式 → 数値代入 → 計算 → 結果 の流れを LaTeX で明示する
   - 例: 「直方体の体積 $V$ は $V = w \\times d \\times h$。$w=4, d=4, h=10$ を代入して $V = 4 \\times 4 \\times 10 = 160$（cm³）」
3. 各 step の `narration_hint` を参考に、なぜその計算をするかの理由を添える
4. (2) の解説では (1) で求めた値を引用する
5. 数式は **必ず LaTeX インライン形式** `$...$`（`$$..$$` や `\\[..\\]` は絶対不可）
   - 途中式も 1 行に収める: `$V = \\dfrac{{1}}{{3}} \\times 4 \\times 3 = 4$（cm³）`
   - 改行が必要な場合は `$式1$` のあと通常テキストで補足し、次の `$式2$` を続ける
6. **円錐・球・おうぎ形の体積/表面積は $\\pi$ を必ず明示**（数値で $\\pi \\approx 3.14$ に近似しない）
7. 用語は中{grade}の学習指導要領範囲内
8. 1 サブ問題につき最低 3 文以上、公式→代入→計算 を全て書く

# 問題文
{problem_text}

# 解答の logic_steps（順序通り、sympy_expr が真の答えで絶対に変更しない）
{logic_steps_yaml}

# Few-Shot 例
{few_shot_examples}

# 出力（JSON のみ）
{{
  "explanation_text": "（解説全体、各 sub_question を含む。途中式・公式・代入を明示）",
  "sub_question_explanations": [
    {{"label": "(1)", "text": "公式 ... 代入 ... 計算 ... 結果"}}
  ]
}}"""


PROOF_TRANSLATION_PROMPT = """以下の ProofOutput を、入試・定期テスト形式の証明文章に翻訳してください。

# 厳守事項
1. **ProofStep の step_number 順序と references 関係を絶対に保つ**
2. 「① ② ③」形式で各ステップに番号を振る
3. 中{grade}の証明スタイル（定型句）を使う

# ProofOutput
{proof_output_yaml}

# Few-Shot 例
{few_shot_examples}

# 出力（テキスト）"""
