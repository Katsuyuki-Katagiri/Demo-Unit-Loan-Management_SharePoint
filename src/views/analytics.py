
import streamlit as st
import datetime
import pandas as pd
from src.database import get_device_units, get_device_types, get_all_categories
from src.logic import calculate_utilization

def render_analytics_view():
    st.title("📊 分析 (Analytics)")
    
    st.subheader("稼働率レポート (Utilization Rate)")
    st.caption("定義: 期間内の (貸出日数 / 期間日数) * 100。同日貸出は1日、メンテナンス/Issue対応中も貸出(占有)とみなす場合はロジック調整が必要（現在はLoanレコードのみ集計）。")
    
    # 1. Period Selection
    col1, col2 = st.columns(2)
    today = datetime.date.today()
    this_month_start = today.replace(day=1)
    
    start_date = col1.date_input("開始日", value=this_month_start)
    end_date = col2.date_input("終了日", value=today)
    
    if start_date > end_date:
        st.error("開始日は終了日より前である必要があります。")
        return
        
    s_str = start_date.strftime('%Y-%m-%d')
    e_str = end_date.strftime('%Y-%m-%d')
    
    # 2. Get Units
    # For now, list all units or filter by category
    categories = get_all_categories()
    cat_names = ["All"] + [c['name'] for c in categories]
    selected_cat = st.selectbox("カテゴリ絞り込み", cat_names)
    
    # Fetch Units
    # We don't have get_all_units, so iterate types...
    # Efficient approach: Get all types, then units for each.
    
    results = []
    
    types = get_device_types()
    for t in types:
        # Filter by category if selected
        if selected_cat != "All":
            # Need to check category name. get_device_types returns row including category_id.
            # But we only have cat_names.
            # Simplified: just check if category_id matches the one for selected_cat.
            # Need to map name->id first.
            cat_obj = next((c for c in categories if c['name'] == selected_cat), None)
            if cat_obj and t['category_id'] != cat_obj['id']:
                 continue
                 
        units = get_device_units(t['id'])
        for u in units:
            rate = calculate_utilization(u['id'], s_str, e_str)
            results.append({
                "Type": t['name'],
                "Lot": u['lot_number'],
                "Location": u['location'],
                "Utilization (%)": f"{rate}%"
            })
            
    # 3. Display Dataframe
    if results:
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
    else:
        st.info("対象期間・カテゴリのデータがありません。")

