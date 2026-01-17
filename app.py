import streamlit as st
import os
from src.database import init_db, check_users_exist, seed_categories
from src.auth import is_logged_in, logout_user
from src.views.setup import render_setup_view
from src.views.login import render_login_view
from src.views.home import render_home_view
from src.views.master import render_master_view

# Page configuration
st.set_page_config(
    page_title="デモ機管理アプリ",
    page_icon="🏥",
    layout="wide", # Phase 1: Wide layout for better tables/grids
    initial_sidebar_state="expanded"
)

# Apply Global Styles
from src.styles import apply_custom_css
apply_custom_css()

# Initialize DB on start
if 'db_initialized' not in st.session_state:
    init_db()
    # Migration for new features - すべてのマイグレーションを起動時に実行
    from src.database import (
        migrate_category_visibility,
        migrate_loans_assetment_check,
        migrate_loans_notes,
        migrate_returns_assetment_check,
        migrate_returns_notes
    )
    migrate_category_visibility()
    migrate_loans_assetment_check()
    migrate_loans_notes()
    migrate_returns_assetment_check()
    migrate_returns_notes()
    
    seed_categories()
    st.session_state['db_initialized'] = True

def main():
    # 1. Check if Setup is needed
    if not check_users_exist():
        render_setup_view()
        return

    # 2. Check Authentication
    if not is_logged_in():
        render_login_view()
        return

    # 3. Main Logic (Logged In)
    
    # Sidebar Navigation
    with st.sidebar:
        st.write(f"ユーザー: **{st.session_state.get('user_name')}**")
        st.caption(f"権限: {st.session_state.get('user_role')}")
        
        # Navigation Menu
        # Key-Value pair for cleaner code or just list? List is fine for simple app.
        page_options = ["ホーム"]
        
        page_options.append("分析")
        
        if st.session_state.get('user_role') == 'admin':
            page_options.append("マスタ管理")
            page_options.append("通知設定")
            
        selected_page = st.radio("メニュー", page_options)
        
        st.divider()
        if st.button("ログアウト", type="primary"):
            logout_user()
            st.rerun()

    # Routing
    if selected_page == "ホーム":
        render_home_view()
    elif selected_page == "分析":
        from src.views.analytics import render_analytics_view
        render_analytics_view()
    elif selected_page == "マスタ管理":
        render_master_view()
    elif selected_page == "通知設定":
        from src.views.settings import render_settings_view
        render_settings_view()

if __name__ == "__main__":
    main()
