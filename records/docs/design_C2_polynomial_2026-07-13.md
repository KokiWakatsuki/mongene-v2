# C2 式の計算 残23セル 設計書（sonnetサブエージェント成果）

## ファイル構成: 新規 polynomial.py(solvers/recipes/checkers/templates 各1) + __init__.py 4本に1行追記
##   例外: g2_l16(連立)/g2_l10(代入)は linear.py に追記(既存連立資産の隣・intersection/verify流用)

## 実装順: l16 → l10 → l2(polynomial.py初) → l3 → l5 → l4 → l6 → l1 → l9 → l7 → l8

## 各セル(solver独立再計算はsympy一般関数: expand/Poly.degree/together/solve)
- l16 calc Lv1: 整数係数連立. intersection_of_two_lines(elimination)流用. g2_l11と別構造に=「y係数絶対値等しく符号逆→足す」(l11は引く). recipe solve_system_elimination_add(linear.py). concept solve_by_elimination_add(別concept). 
- l10 calc Lv1: 代入検証. ★knowledge l10 Lv2(ChoiceAnswer判定)と別: asked=value・answer=左辺の計算値(SymbolicAnswer). solver verify_single_equation. given=equation+candidate. concept substitute_and_evaluate(別). template「左辺の値を求めよ」
- l2 calc Lv1/Lv2: 同類項. solver simplify_polynomial(sympy.expand). asked=simplified_expr(既存語彙OK). Lv1 op[group_like_terms,add_coefficients] / Lv2 op[identify_like_terms,group,add](複数文字混在で選別必須=構造差). 
- l3 calc Lv1/Lv2: 多項式加減. solver add_or_subtract_polynomials(expand(a±b)). ★given_vocab に expression_a/expression_b 追加. Lv1 op[remove_parentheses,add_like_terms] / Lv2 op[distribute_negative_sign,add_like_terms](減法の符号反転)
- l5 calc Lv1/Lv2: 分配法則. solver distribute_constant. given_vocab に coefficient 追加. Lv1 op[distribute_multiplication] / Lv2 op[convert_division_to_multiplication,distribute](除法→逆数)
- l4 calc Lv1/Lv2/Lv3: 単項式乗除. solver compute_monomial_expression. given=expression(演算式全体を1文字列). ★新フォーマッタ _fmt_monomial_chain(terms,ops)で ×/÷ 結合. Lv1/2/3でop列変える(符号決定/累乗指数加算/除法逆数変換を段階追加)
- l6 calc Lv2/Lv3: 通分. solver combine_fractional_expressions(together+expand分子). ★分数フォーマッタ _fmt_fraction_expr(numer,denom)新設. Lv2 op[find_common_denominator,combine_numerators] / Lv3 op[+distribute_signs,+add_integer_term]
- l1 calc Lv1: 次数. 2小問(単項式次数/多項式次数). solver degree_of_monomial/polynomial(Poly.total_degree). ★given_vocab に expression_b, asked_vocab に degree 追加. G-Q5t高リスク(次数=小整数)だがgiven指数由来でwhitelist. 次数域1-3に制限(⁴不要)
- l9 calc Lv1/Lv2/Lv3: 等式変形. ★solve_equation_for_y(y固定)流用不可→一般化 solve_for_variable(eq,target)新設(sympy.solve). given=equation+target_variable, asked=expression(calculation.asked_vocabに追加要). Lv1 op[isolate_target]/Lv2[+divide_by_coefficient]/Lv3[multiply_both_sides,...](積・分母にある文字=質的差)
- l7 calc Lv1: 偶数奇数の式. solver express_number_property(expand). ★dup_rate高риск(property_type数種のみ)→個数/演算をsurface paramで広げる. given expression_a/b. concept consecutive_even_odd_sum
- l8 calc Lv1: 10a+b. ★dup_rate構造的困難(数値パラメータなし=毎回同じ). 対策: source_desc明記+preview検収委ね or 文字ペア(a,b)/(m,n)ランダムで見かけ差(要理由明記). template固定文・given空. 和のみ(source_desc忠実)

## frame拡張(test_frames.py同時更新必須): 
##   given_vocab += expression_a,expression_b,expression_b(次数),coefficient,candidate,target_variable
##   asked_vocab += degree, expression(等式変形の解)
## 表示整形: _fmt_expr(**2→²,*除去)は多項式でも概ね可. 除算「÷」/分数/3項符号は polynomial.py 専用フォーマッタ新設
## dup_rate: l8(構造的1通り)>l7(type数種)>l1(次数域小) が高リスク. 係数を広域で引く. 実装後100seed実測必須
## G-Q5t: narrationに数字書かない. 式答え(free_symbol含む)はdisplay全体一致のみ検査=相対安全. 「けた」→「桁」で統一(_COUNTER_EXPR_RE既存)
