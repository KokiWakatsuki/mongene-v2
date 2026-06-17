"""LLM プロンプトテンプレート（§21, §29）"""

PROBLEM_TRANSLATION_PROMPT = """あなたは中学校数学の塾講師として、本システムが計算済みの「中間表現データ」を、入試・定期テスト品質の自然な日本語問題文に翻訳します。

# 厳守事項
1. **計算結果や数値は絶対に変更しない**（SymPy で計算済み、ハルシネーション禁止）
2. 数式は LaTeX インライン形式（$\\sqrt{{2}}$、$\\pi$、$\\dfrac{{1}}{{2}}$）で記述
3. 用語は中{grade}の学習指導要領範囲内のみ使用
4. 「求めなさい」「右の図のように」など入試・テスト独特の言い回しを使用
5. 与えられた sub_questions の depends_on に従い、(1)→(2)→(3) と段階的に提示

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
2. 各 step の `narration_hint` を参考に、なぜその計算をするかの理由を添える
3. (2) の解説では (1) で求めた値を引用する
4. 数式は LaTeX、用語は学年範囲内
5. 1 ステップを 1〜3 文に納める

# 問題文
{problem_text}

# 解答の logic_steps（順序通り）
{logic_steps_yaml}

# Few-Shot 例
{few_shot_examples}

# 出力（JSON のみ）
{{
  "explanation_text": "（解説全体）",
  "sub_question_explanations": [
    {{"label": "(1)", "text": "..."}}
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
