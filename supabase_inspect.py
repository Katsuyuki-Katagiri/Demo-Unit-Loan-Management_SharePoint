
import os
import streamlit as st
from supabase import create_client
import json

def inspect_supabase():
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        print("SUPABASE_URL or SUPABASE_KEY not set")
        return
    
    client = create_client(url, key)
    
    print("--- Inspecting 'items' table data ---")
    try:
        # Get all items
        response = client.table("items").select("*").execute()
        data = response.data
        print(f"Total items: {len(data)}")
        for idx, item in enumerate(data):
            print(f"Item {idx} keys: {list(item.keys())}")
            if 'photo_path' not in item:
                print(f"ALERT: 'photo_path' missing in item id {item.get('id')}")
            else:
                print(f"Item {idx} photo_path: {item['photo_path']}")
            
    except Exception as e:
        print(f"Error inspecting items: {e}")

if __name__ == "__main__":
    inspect_supabase()
