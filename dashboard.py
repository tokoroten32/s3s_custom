import sqlite3
import json
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DB_PATH = 'splatoon3_battles.db'

@st.cache_data
def load_data():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, play_time, rule, stage, weapon, raw_json FROM battles", conn)
    conn.close()
    
    if df.empty:
        return df

    # raw_json のパース処理
    parsed_records = []
    for raw in df['raw_json']:
        try:
            data = json.loads(raw) if isinstance(raw, str) else (raw if isinstance(raw, dict) else {})
        except Exception:
            data = {}
        
        # 自プレイヤー情報の取得
        my_res = data.get('my_result') or data.get('my') or data.get('player') or {}
        
        # 勝敗 (judgement) の柔軟な判定 (大文字・小文字・別キー構造対応)
        raw_judgement = (
            data.get('judgement') or 
            (data.get('result', {}).get('judgement') if isinstance(data.get('result'), dict) else None) or
            my_res.get('judgement')
        )
        
        judgement = 'UNKNOWN'
        if raw_judgement:
            j_str = str(raw_judgement).strip().upper()
            if j_str in ['WIN', 'VICTORY', '勝', '勝利']:
                judgement = 'WIN'
            elif j_str in ['LOSE', 'DEFEAT', 'EXEMPTED_LOSE', '敗', '敗北', '負け']:
                judgement = 'LOSE'
            elif j_str in ['DRAW', '引き分け']:
                judgement = 'DRAW'
            else:
                judgement = j_str
        elif 'is_win' in data:
            judgement = 'WIN' if data['is_win'] else 'LOSE'

        knockout = data.get('knockout', 'NEITHER')
        
        # マッチモード (mode) の柔軟な抽出
        mode_val = None
        if 'mode' in data:
            m = data['mode']
            if isinstance(m, dict):
                mode_val = m.get('name') or m.get('mode')
            elif isinstance(m, str):
                mode_val = m
        elif 'vsMode' in data:
            vm = data['vsMode']
            if isinstance(vm, dict):
                mode_val = vm.get('name') or vm.get('mode')
            elif isinstance(vm, str):
                mode_val = vm

        if not mode_val:
            mode_val = data.get('mode_name') or data.get('match_mode')

        # モード表記の補正およびルール名からの自動推測フォールバック
        rule_val = str(data.get('rule', '') or df['rule'] if 'rule' in df else '')
        if mode_val:
            mode = str(mode_val)
        elif 'ナワバリ' in rule_val:
            mode = 'レギュラーマッチ'
        elif any(r in rule_val for r in ['ガチエリア', 'ガチヤグラ', 'ガチホコ', 'ガチアサリ']):
            mode = 'バンカラマッチ'
        else:
            mode = 'その他・未設定'

        # ギアパワーの抽出
        gears = data.get('gears', data.get('gear', {}))
        gear_powers = []
        if isinstance(gears, dict):
            for g_key in ['head', 'clothes', 'shoes']:
                g_info = gears.get(g_key, {})
                if isinstance(g_info, dict) and 'main' in g_info:
                    gear_powers.append(str(g_info['main']))
        gear_build_str = " / ".join(gear_powers) if gear_powers else "未設定・不明"

        # 表彰の抽出
        raw_awards = data.get('awards', [])
        awards_list = []
        if isinstance(raw_awards, list):
            for a in raw_awards:
                if isinstance(a, dict):
                    awards_list.append(a.get('name', ''))
                elif isinstance(a, str):
                    awards_list.append(a)

        parsed_records.append({
            'mode': mode,
            'judgement': judgement,
            'is_win': judgement == 'WIN',
            'is_valid': judgement in ['WIN', 'LOSE'],
            'is_ko': knockout in ['WIN', 'LOSE', True, 'YES'],
            'duration_sec': data.get('duration', 0) or 0,
            'kill': my_res.get('kill', 0) or 0,
            'assist': my_res.get('assist', 0) or 0,
            'death': my_res.get('death', 0) or 0,
            'special': my_res.get('special', 0) or 0,
            'paint': my_res.get('paint', my_res.get('weapon_paint_pt', 0)) or 0,
            'gear_build': gear_build_str,
            'awards': [a for a in awards_list if a]
        })

    parsed_df = pd.DataFrame(parsed_records)
    if 'mode' in df.columns:
        df = df.drop(columns=['mode'])
        
    df = pd.concat([df, parsed_df], axis=1)

    if 'play_time' in df.columns:
        df['play_time'] = pd.to_datetime(df['play_time'])
        df = df.sort_values('play_time').reset_index(drop=True)

    return df

def main():
    st.set_page_config(page_title="Splatoon 3 戦績アナリティクス", layout="wide")
    st.title("🦑 Splatoon 3 戦績アナリティクス")

    if st.sidebar.button("🔄 データを再読み込み"):
        st.cache_data.clear()
        st.rerun()

    df = load_data()

    if df.empty:
        st.warning("データがありません。スプラトゥーン3の戦績データを取得してください。")
        return

    # ------------------------------------------------------------------
    # サイドバー フィルター設定
    # ------------------------------------------------------------------
    st.sidebar.header("🎯 フィルター設定")
    
    modes = [m for m in df['mode'].dropna().unique() if str(m).strip()]
    rules = [r for r in df['rule'].dropna().unique() if str(r).strip()]
    weapons = [w for w in df['weapon'].dropna().unique() if str(w).strip()]

    selected_modes = st.sidebar.multiselect("マッチモード", modes, default=[])
    selected_rules = st.sidebar.multiselect("ルール", rules, default=[])
    selected_weapons = st.sidebar.multiselect("ブキ", weapons, default=[])

    filtered_df = df.copy()
    if selected_modes:
        filtered_df = filtered_df[filtered_df['mode'].isin(selected_modes)]
    if selected_rules:
        filtered_df = filtered_df[filtered_df['rule'].isin(selected_rules)]
    if selected_weapons:
        filtered_df = filtered_df[filtered_df['weapon'].isin(selected_weapons)]

    if filtered_df.empty:
        st.warning("条件に該当するデータがありません。フィルター条件を変更してください。")
        return

    # ------------------------------------------------------------------
    # 概要サマリー (ヘッダーKPI)
    # ------------------------------------------------------------------
    valid_df = filtered_df[filtered_df['is_valid']]
    if valid_df.empty:
        valid_df = filtered_df  # 安全策としてのフォールバック

    total_battles = len(valid_df)
    total_wins = valid_df['is_win'].sum()
    win_rate = (total_wins / total_battles * 100) if total_battles > 0 else 0
    
    kills = filtered_df['kill'].sum()
    assists = filtered_df['assist'].sum()
    deaths = filtered_df['death'].sum()
    kad = ((kills + assists) / deaths) if deaths > 0 else (kills + assists)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("総対戦数", f"{total_battles} 戦")
    c2.metric("勝率", f"{win_rate:.1f} %", f"{total_wins}勝 {total_battles - total_wins}敗")
    c3.metric("平均 KA/D", f"{kad:.2f}")
    c4.metric("平均 塗P / SP", f"{filtered_df['paint'].mean():.0f} P", f"SP {filtered_df['special'].mean():.1f} 回")

    st.markdown("---")

    # ------------------------------------------------------------------
    # タブ構成
    # ------------------------------------------------------------------
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "⚔️ ブキ×マップ詳細分析",
        "🗺️ ルール×ステージ相性",
        "📈 KPI & 推移",
        "⚡ スペシャル・試合時間",
        "🛡️ ギア & 🏆 表彰"
    ])

    # ==================================================================
    # タブ1: ⚔️ ブキ×マップ詳細分析
    # ==================================================================
    with tab1:
        st.subheader("⚔️ ブキ×マップ（ステージ）別 パフォーマンス分析")
        
        target_weapon = st.selectbox("分析対象のブキを選択:", ["全ブキ対象"] + weapons)
        
        w_df = filtered_df if target_weapon == "全ブキ対象" else filtered_df[filtered_df['weapon'] == target_weapon]

        if w_df.empty:
            st.info("選択されたブキのデータがありません。")
        else:
            stage_stats = w_df.groupby('stage').agg(
                試合数=('id', 'count'),
                勝利数=('is_win', 'sum'),
                キル=('kill', 'mean'),
                アシスト=('assist', 'mean'),
                デス=('death', 'mean'),
                平均SP=('special', 'mean'),
                平均塗P=('paint', 'mean')
            ).reset_index()

            stage_stats['勝率(%)'] = (stage_stats['勝利数'] / stage_stats['試合数'] * 100).round(1)
            stage_stats['KA/D'] = np.where(
                stage_stats['デス'] > 0,
                ((stage_stats['キル'] + stage_stats['アシスト']) / stage_stats['デス']).round(2),
                (stage_stats['キル'] + stage_stats['アシスト']).round(2)
            )
            stage_stats['平均SP'] = stage_stats['平均SP'].round(1)
            stage_stats['平均塗P'] = stage_stats['平均塗P'].round(0)

            st.markdown("##### 📊 図でみるマップ別指標")
            graph_col1, graph_col2 = st.columns(2)

            with graph_col1:
                fig_win_kad = px.bar(
                    stage_stats.sort_values('勝率(%)', ascending=True),
                    y='stage', x='勝率(%)', color='KA/D',
                    orientation='h', text='勝率(%)',
                    color_continuous_scale='Blugrn',
                    title=f"【{target_weapon}】マップ別 勝率 (%) と KA/D (色表示)"
                )
                fig_win_kad.update_traces(texttemplate='%{text}%', textposition='outside')
                st.plotly_chart(fig_win_kad, use_container_width=True)

            with graph_col2:
                fig_sp_paint = px.bar(
                    stage_stats.sort_values('平均SP', ascending=True),
                    y='stage', x='平均SP', color='平均塗P',
                    orientation='h', text='平均SP',
                    color_continuous_scale='Oranges',
                    title=f"【{target_weapon}】マップ別 平均スペシャル回数 と 平均塗P (色表示)"
                )
                fig_sp_paint.update_traces(texttemplate='%{text}回', textposition='outside')
                st.plotly_chart(fig_sp_paint, use_container_width=True)

            st.markdown("##### 🔢 数字でみるマップ別一覧")
            display_cols = ['stage', '試合数', '勝率(%)', 'KA/D', '平均SP', '平均塗P']
            table_df = stage_stats[display_cols].sort_values('試合数', ascending=False).set_index('stage')

            try:
                st.dataframe(
                    table_df.style.background_gradient(subset=['勝率(%)'], cmap='YlGn')
                                  .background_gradient(subset=['KA/D'], cmap='Blues')
                                  .background_gradient(subset=['平均SP'], cmap='Oranges')
                                  .format({'勝率(%)': '{:.1f}%', 'KA/D': '{:.2f}', '平均SP': '{:.1f}回', '平均塗P': '{:.0f}P'}),
                    use_container_width=True
                )
            except Exception:
                st.dataframe(
                    table_df.style.format({'勝率(%)': '{:.1f}%', 'KA/D': '{:.2f}', '平均SP': '{:.1f}回', '平均塗P': '{:.0f}P'}),
                    use_container_width=True
                )

    # ==================================================================
    # タブ2: 🗺️ ルール×ステージ相性
    # ==================================================================
    with tab2:
        st.subheader("ルール×ステージ別 相性ヒートマップ (勝率 %)")
        pivot_df = filtered_df.pivot_table(
            index='stage', columns='rule', values='is_win',
            aggfunc=lambda x: (x.sum() / len(x) * 100) if len(x) > 0 else 0
        ).fillna(0)

        if not pivot_df.empty:
            fig_heatmap = px.imshow(
                pivot_df, text_auto=".1f", aspect="auto",
                color_continuous_scale="Viridis",
                labels=dict(x="ルール", y="ステージ", color="勝率 (%)")
            )
            st.plotly_chart(fig_heatmap, use_container_width=True)

    # ==================================================================
    # タブ3: 📈 KPI & 推移
    # ==================================================================
    with tab3:
        st.subheader("直近対戦の移動平均勝率 (%) & KA/D 推移")
        filtered_df['win_int'] = filtered_df['is_win'].astype(int)
        filtered_df['win_rate_ma10'] = filtered_df['win_int'].rolling(window=10, min_periods=1).mean() * 100
        filtered_df['kad_rolling'] = (filtered_df['kill'] + filtered_df['assist']) / np.maximum(filtered_df['death'], 1)

        fig_trend = px.line(
            filtered_df, x=filtered_df.index, y=['win_rate_ma10', 'kad_rolling'],
            labels={'value': '数値', 'index': '試合数 (時系列)'},
            title="10試合移動平均勝率 および KA/D 推移"
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    # ==================================================================
    # タブ4: ⚡ スペシャル・試合時間
    # ==================================================================
    with tab4:
        col_sp, col_dur = st.columns(2)
        with col_sp:
            st.subheader("スペシャル発動回数 vs 勝率")
            sp_stats = filtered_df.groupby('special').agg(
                試合数=('id', 'count'),
                勝率=('is_win', lambda x: (x.sum() / len(x) * 100))
            ).reset_index()
            fig_sp = px.bar(sp_stats, x='special', y='勝率', text='試合数', title="スペシャル回数別 勝率")
            fig_sp.update_traces(texttemplate='%{text}戦', textposition='outside')
            st.plotly_chart(fig_sp, use_container_width=True)

        with col_dur:
            st.subheader("試合時間区分別 勝率")
            def duration_bucket(sec):
                if sec < 120: return "1. 早期決着 (<2分)"
                elif sec < 210: return "2. 中盤決着 (2-3.5分)"
                elif sec <= 300: return "3. フルタイム (3.5-5分)"
                else: return "4. 延長戦 (>5分)"

            filtered_df['dur_bucket'] = filtered_df['duration_sec'].apply(duration_bucket)
            dur_stats = filtered_df.groupby('dur_bucket').agg(
                試合数=('id', 'count'),
                勝率=('is_win', lambda x: (x.sum() / len(x) * 100))
            ).reset_index()

            fig_dur = px.bar(dur_stats, x='dur_bucket', y='勝率', color='dur_bucket', text='試合数', title="試合時間帯別 勝率")
            fig_dur.update_traces(texttemplate='%{text}戦', textposition='outside')
            st.plotly_chart(fig_dur, use_container_width=True)

    # ==================================================================
    # タブ5: 🛡️ ギア & 🏆 表彰
    # ==================================================================
    with tab5:
        col_g, col_a = st.columns(2)
        with col_g:
            st.subheader("ギア構成別 戦績")
            gear_stats = filtered_df.groupby('gear_build').agg(
                試合数=('id', 'count'), 勝利数=('is_win', 'sum')
            ).reset_index()
            gear_stats['勝率(%)'] = (gear_stats['勝利数'] / gear_stats['試合数'] * 100).round(1)
            st.dataframe(gear_stats.sort_values('試合数', ascending=False), use_container_width=True)

        with col_a:
            st.subheader("表彰 (Awards) TOP 10")
            all_awards = [award for awards in filtered_df['awards'] for award in awards]
            if all_awards:
                award_counts = pd.Series(all_awards).value_counts().reset_index()
                award_counts.columns = ['表彰名', '獲得回数']
                st.dataframe(award_counts.head(10), use_container_width=True)

if __name__ == "__main__":
    main()