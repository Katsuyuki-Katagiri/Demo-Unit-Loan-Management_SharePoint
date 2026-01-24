
import streamlit as st
import datetime
import pandas as pd
from src.database import get_device_types, get_all_categories, get_all_device_units
from src.logic import calculate_utilization_batch

def render_analytics_view():
    from src.ui import render_header
    render_header("分析", "analytics")
    
    st.markdown("### 📊 稼働率レポート")
    st.caption("指定期間内におけるデバイスの稼働状況を分析します。稼働率 = (貸出日数 / 期間日数) * 100")
    
    # --- 1. Filter Settings ---
    with st.container():
        c1, c2, c3 = st.columns([2, 2, 3])
        today = datetime.date.today()
        this_month_start = today.replace(day=1)
        
        start_date = c1.date_input("開始日", value=this_month_start)
        end_date = c2.date_input("終了日", value=today)
        
        # Category Filter
        categories = get_all_categories()
        cat_names = ["All"] + [c['name'] for c in categories]
        selected_cat = c3.selectbox("カテゴリ絞り込み", cat_names)

    if start_date > end_date:
        st.error("開始日は終了日より前である必要があります。")
        return

    s_str = start_date.strftime('%Y-%m-%d')
    e_str = end_date.strftime('%Y-%m-%d')
    days_in_period = (end_date - start_date).days + 1

    # --- 2. Data Aggregation (バッチクエリ最適化版) ---
    raw_data = []
    cat_rates = {}
    type_rates = {}
    
    types = get_device_types()
    
    # カテゴリIDでマップ作成
    cat_map = {c['id']: c['name'] for c in categories}
    
    # 全個体を一括取得（バッチクエリ）
    all_units = get_all_device_units()
    
    # 機種IDでユニットをグループ化
    units_by_type = {}
    for u in all_units:
        type_id = u['device_type_id']
        if type_id not in units_by_type:
            units_by_type[type_id] = []
        units_by_type[type_id].append(u)
    
    # 対象個体のIDを収集
    target_unit_ids = []
    unit_metadata = {}  # {unit_id: (cat_name, type_name, unit)}
    
    with st.spinner('データを集計中...'):
        for t in types:
            cat_name = cat_map.get(t['category_id'], "Unknown")
            
            if selected_cat != "All" and cat_name != selected_cat:
                continue
            
            units = units_by_type.get(t['id'], [])
            for u in units:
                target_unit_ids.append(u['id'])
                unit_metadata[u['id']] = (cat_name, t['name'], u)
        
        # 稼働率を一括計算（バッチクエリ）
        if target_unit_ids:
            utilization_rates = calculate_utilization_batch(target_unit_ids, s_str, e_str)
        else:
            utilization_rates = {}
        
        # 結果を構築
        for unit_id, (cat_name, type_name, u) in unit_metadata.items():
            rate = utilization_rates.get(unit_id, 0.0)
            
            raw_data.append({
                "カテゴリ": cat_name,
                "機種名": type_name,
                "ロット": u['lot_number'],
                "保管場所": u['location'],
                "稼働率 (%)": rate,
                "RawRate": rate 
            })
            
            # Aggregate
            if cat_name not in cat_rates: cat_rates[cat_name] = []
            cat_rates[cat_name].append(rate)
            
            if type_name not in type_rates: type_rates[type_name] = []
            type_rates[type_name].append(rate)

    if not raw_data:
        st.info("対象期間・条件に一致するデータがありません。")
        return

    df = pd.DataFrame(raw_data)

    # --- 3. Visualization Dashboard ---
    
    # KPI Metrics
    avg_total = df["RawRate"].mean()
    active_units = len(df[df["RawRate"] > 0])
    total_units = len(df)
    
    st.divider()
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.metric("平均稼働率", f"{avg_total:.1f}%")
    kpi2.metric("稼働台数 / 全台数", f"{active_units} / {total_units}")
    kpi3.metric("集計期間", f"{days_in_period} 日間")
    
    st.divider()

    # Graphs
    import altair as alt

    # Helper to create labeled bar chart
    def create_labeled_bar_chart(data_dict, x_col, y_col, color_hex):
        # Scale down to 0.0-1.0 for percentage formatting
        scaled_data = {k: v/100.0 for k, v in data_dict.items()}
        df_chart = pd.DataFrame(list(scaled_data.items()), columns=[x_col, y_col])
        
        # Base chart
        base = alt.Chart(df_chart).encode(
            x=alt.X(x_col, sort='-y'),
            y=alt.Y(y_col, axis=alt.Axis(format='%', title="平均稼働率"))
        )
        
        # Bars
        bars = base.mark_bar(color=color_hex).encode(
            tooltip=[x_col, alt.Tooltip(y_col, format='.1%', title="平均稼働率")]
        )
        
        # Text Labels
        text = base.mark_text(
            align='center',
            baseline='bottom',
            dy=-5  # Shift text up
        ).encode(
            text=alt.Text(y_col, format='.1%')  # Show value with 1 decimal percentage
        )
        
        return (bars + text).properties(height=400)

    # A. Category Comparison (Only show if multiple categories present or All selected)
    if selected_cat == "All" and len(cat_rates) > 0:
        st.subheader("📈 カテゴリ別 平均稼働率")
        cat_avg = {k: sum(v)/len(v) for k, v in cat_rates.items()}
        chart_cat = create_labeled_bar_chart(cat_avg, "カテゴリ", "平均稼働率", "#4CAF50")
        st.altair_chart(chart_cat, use_container_width=True)

    # B. Device Type Comparison
    st.subheader("📊 機種別 平均稼働率")
    if type_rates:
        type_avg = {k: sum(v)/len(v) for k, v in type_rates.items()}
        chart_type = create_labeled_bar_chart(type_avg, "機種名", "平均稼働率", "#2196F3")
        st.altair_chart(chart_type, use_container_width=True)

    # --- 4. Detailed Data Table ---
    st.subheader("📋 詳細データ")
    with st.expander("詳細データテーブルを表示", expanded=True):
        # Formatting for display
        df_display = df.drop(columns=["RawRate"]).copy()
        
        # Style the dataframe (Highlight high utilization)
        st.dataframe(
            df_display,
            column_config={
                "稼働率 (%)": st.column_config.NumberColumn(
                    "稼働率 (%)",
                    help="期間中の稼働率",
                    format="%.1f%%"
                )
            },
            use_container_width=True,
            hide_index=True
        )

