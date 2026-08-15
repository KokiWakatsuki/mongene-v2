# C5 graph_table 作図残り6セル 設計書（sonnetサブエージェント成果）
対象: l22Lv3(分数傾き)/l23Lv2(端点線分)/l26Lv2(特殊直線)/l28Lv2(対応表)/l29Lv3(折れ線)/l30Lv2(ダイヤ交点読み)

## 実装順(流用度高い順): l30 → l26 → l28 → l22 → l23 → l29

## visuals/graph.py 拡張(後方互換: render_grid_svg シグネチャ不変・既存golden不変)
- render_segment_svg(params, *, draw_segment): 線分[x_lo,x_hi]+端点マーカー(closed=●塗り/open=○白抜き・色以外で区別=N-4適合). l23
- render_grid_with_special_lines_svg(params,*,draw_line,draw_vline,draw_hline): vline_x/hline_y追加. l26
- render_polyline_svg(params,*,draw_polyline): table_pts隣接点を線分連結. l28/l29共用
- l22分数傾き: 描画拡張不要(既存render_grid_svg draw_line=Trueがsympy.Rational係数で動く). solver側でFeature(lattice_point)追加とsteps op列変更で対応
- VisualElement.kind/Feature.kind は str型なのでスキーマ変更不要(新kind文字列を足すだけ)

## 各セル要点
- l30Lv2: intersection_of_two_lines再利用(新solverゼロ). l27 graphのrecipeコピー+ダイヤ文脈ラベル+傾き制約(meet=異符号/catchup=同符号大小). 問題図=空グリッド(l27前例). concept新設 diagram_intersection. source_descに「式は既知として与えグラフ読解のみ・立式はwp l30」明記
- l26Lv2: 2小問構成推奨((1)ax+by=c直線を切片法, (2)x=k/y=k特殊直線). solver draw_special_line(k,axis). given に equation2("y=3"のk)追加必須(whitelist用). steps: find_x_intercept→find_y_intercept→draw_line でLv1と差別化
- l28Lv2: data_table(既存frame語彙)からa,b逆算(答え-first: a,b先決め→等間隔x4点でy逆算). solver=_draw_linear_features_core合成. 描画は既存line(4点共線). data_tableのextract_numbers動作を実装前に確認
- l22Lv3: slope=frac_range{num:[-6,6],den:[2,4]}. solver draw_linear_features_fraction: 格子点(0,b)と(q,p+b)をFeature(lattice_point)追加→Lv1の2特徴とfp相異=level_sep. steps: plot_intercept→apply_slope_denominator→apply_slope_numerator→mark_lattice_point→draw_line. _to_fraction が"-2/3"をパースできるか実装前に確認
- l23Lv2: asked_vocab に draw_segment 追加. given_vocab に x_domain 追加. Feature kind=endpoint_closed/endpoint_open で開閉区別(double-solve堅い). solver draw_segment_features(a,b,x_lo,x_hi,closed_lo,closed_hi). 「かく」一本化(読むはl21/25/27で既出)しsource_desc明記. _FORBIDDEN_BY_ASKED["draw_segment"]=空集合を明示登録
- l29Lv3: 動点面積の折れ線. answer-first(頂点先決め→矛盾ない辺長/速さをsituation_paramsに逆算構成). 区間頂点座標はgivenに出さない. render_polyline_svg. source_descに「頂点座標を固定パラメータとして与え折れ線をかく技能のみ・立式はwp l29」明記. G-Q5t: 面積値と本文数値の偶然一致を広域監視

## 幾何リーク: 全セル問題図=空グリッド(l27前例で forbidden規則不発). 新規forbidden規則不要
## 着手前確認: _to_fraction分数パース / data_table複数行のextract_numbers / frame語彙追加時 test_frames.py更新 / __pycache__一掃 / 100+seed拒否0 / dup_rate実測
