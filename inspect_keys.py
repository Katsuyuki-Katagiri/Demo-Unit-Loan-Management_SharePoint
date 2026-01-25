
import os
import streamlit as st
from supabase import create_client
import json

def inspect_items_deep():
    url = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    key = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not url or not key:
        print("SUPABASE_URL or SUPABASE_KEY not set")
        return
    
    client = create_client(url, key)
    
    print("--- Inspecting 'items' table for missing keys ---")
    try:
        response = client.table("items").select("*").execute()
        data = response.data
        print(f"Total items: {len(data)}")
        
        required_keys = ['id', 'name', 'tips', 'photo_path']
        missing_report = {k: 0 for k in required_keys}
        
        for idx, item in enumerate(data):
            keys = set(item.keys())
            for rk in required_keys:
                if rk not in keys:
                    missing_report[rk] += 1
                    if missing_report[rk] <= 5: # Show first 5 examples
                        print(f"ALERT: '{rk}' missing in item ID {item.get('id', 'UNKNOWN')}")
        
        print("\n--- Summary of missing keys ---")
        for k, v in missing_report.items():
            print(f"Key '{k}': missing in {v} items")
            
    except Exception as e:
        print(f"Error inspecting items: {e}")

if __name__ == "__main__":
    inspect_items_deep()
