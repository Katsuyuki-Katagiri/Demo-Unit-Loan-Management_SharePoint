
import os
import streamlit as st
from supabase import create_client

def delete_dirt_check():
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    client = create_client(url, key)
    
    target_name = "汚れチェック"
    
    print(f"Searching for '{target_name}'...")
    items = client.table("items").select("*").eq("name", target_name).execute()
    
    if items.data:
        for item in items.data:
            print(f"Found Item ID: {item['id']}, Name: {item['name']}")
            # Delete
            client.table("items").delete().eq("id", item['id']).execute()
            print("Deleted.")
    else:
        print(f"'{target_name}' not found.")

if __name__ == "__main__":
    delete_dirt_check()
