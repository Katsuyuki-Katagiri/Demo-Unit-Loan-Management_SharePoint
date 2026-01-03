import streamlit as st
from src.database import create_initial_admin
import time

def render_setup_view():
    st.title("初期セットアップ")
    st.warning("管理者が登録されていません。最初の管理者を作成してください。")
    
    with st.form("setup_form"):
        name = st.text_input("氏名 (Name)")
        email = st.text_input("メールアドレス (IDとして使用)")
        password = st.text_input("パスワード", type="password")
        password_confirm = st.text_input("パスワード (確認)", type="password")
        
        submitted = st.form_submit_button("管理者を作成して開始")
        
        if submitted:
            if not name or not email or not password:
                st.error("全ての項目を入力してください。")
            elif password != password_confirm:
                st.error("パスワードが一致しません。")
            else:
                success = create_initial_admin(email, name, password)
                if success:
                    st.success("管理者を作成しました。ログイン画面へ移動します。")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("作成に失敗しました。既にユーザーが存在する可能性があります。")
