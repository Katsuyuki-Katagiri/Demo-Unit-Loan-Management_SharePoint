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
    page_title="機材貸出管理",
    page_icon="🏥",
    layout="wide", # Phase 1: Wide layout for better tables/grids
    initial_sidebar_state="expanded"
)

# Initialize DB on start
if 'db_initialized' not in st.session_state:
    init_db()
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
        st.write(f"User: **{st.session_state.get('user_name')}**")
        
        # Navigation Menu
        page_options = ["Home"]
        if st.session_state.get('user_role') == 'admin':
            page_options.append("Master Management")
            
        selected_page = st.radio("Menu", page_options)
        
        st.divider()
        if st.button("ログアウト", type="primary"):
            logout_user()
            st.rerun()

    # Routing
    if selected_page == "Home":
        render_home_view()
    elif selected_page == "Master Management":
        render_master_view()

if __name__ == "__main__":
    main()
