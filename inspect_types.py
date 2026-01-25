
import os
import sys

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = current_dir
sys.path.insert(0, project_root)

# Mock streamlit secrets if needed or just use environment if set, but we saw secrets.toml
# src.database checks st.secrets
# We might need to mock st.secrets
import streamlit as st
import toml

secrets_path = os.path.join(project_root, ".streamlit", "secrets.toml")
if os.path.exists(secrets_path):
    with open(secrets_path, "r") as f:
        secrets = toml.load(f)
    # Mock st.secrets
    st.secrets = secrets
else:
    print("No secrets.toml found")

from src.database_supabase import get_all_categories, get_device_types

try:
    categories = get_all_categories()
    print("Categories:")
    for cat in categories:
        print(f"ID: {cat['id']}, Name: {cat['name']}")
        
    print("\nDevice Types:")
    # Get for all categories
    # We might need to iterate or get all if allowed. 
    # get_device_types takes optional category_id.
    # We can fetch all types if we don't pass category_id?
    # Checking code: query = client.table("device_types").select("*"); if category_id: ...
    # Yes, it returns all if None.
    types = get_device_types()
    for t in types:
        print(f"ID: {t['id']}, CategoryID: {t['category_id']}, Name: {t['name']}")

except Exception as e:
    print(f"Error: {e}")
