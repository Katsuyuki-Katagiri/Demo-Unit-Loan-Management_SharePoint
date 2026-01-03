import streamlit as st
from src.auth import login_user

def render_login_view():
    st.title("ログイン")
    
    with st.form("login_form"):
        email = st.text_input("メールアドレス")
        password = st.text_input("パスワード", type="password")
        
        submitted = st.form_submit_button("ログイン", use_container_width=True)
        
        if submitted:
            if login_user(email, password):
                st.success("ログインしました")
                st.rerun()
            else:
                st.error("メールアドレスまたはパスワードが間違っています。")
