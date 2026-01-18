import bcrypt
import streamlit as st
from src.database import get_user_by_email

def check_password(password: str, hashed) -> bool:
    """Check if the provided password matches the hash."""
    # Supabaseはpassword_hashを文字列として返すため、バイト型に変換
    if isinstance(hashed, str):
        hashed = hashed.encode('utf-8')
    return bcrypt.checkpw(password.encode('utf-8'), hashed)


def login_user(email: str, password: str) -> bool:
    """
    Attempt to log in a user. 
    If successful, sets session state and returns True.
    """
    user = get_user_by_email(email)
    if not user:
        return False
        
    # user is a Row object or tuple: (id, email, password_hash, name, role)
    # database.py creates table with: id, email, password_hash, name, role
    # So index 2 is hash, index 0 is id, index 3 is name, index 4 is role
    
    stored_hash = user['password_hash']
    
    if check_password(password, stored_hash):
        st.session_state['user_id'] = user['id']
        st.session_state['user_name'] = user['name']
        st.session_state['user_email'] = user['email'] # Fixed: Save email to session
        st.session_state['user_role'] = user['role']
        st.session_state['logged_in'] = True
        return True
    
    return False

def logout_user():
    """Clear session state to log out."""
    st.session_state['user_id'] = None
    st.session_state['user_name'] = None
    st.session_state['user_role'] = None
    st.session_state['logged_in'] = False

def is_logged_in() -> bool:
    return st.session_state.get('logged_in', False)
