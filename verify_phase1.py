import os
import sqlite3
from src.database import (
    init_db, create_device_type, create_item, add_template_line, 
    create_device_unit, add_unit_override, UPLOAD_DIR, DB_PATH
)
from src.logic import get_synthesized_checklist

def verify_phase1():
    print("Starting Verification for Phase 1...")
    
    # 1. Setup
    init_db()
    
    # 2. Create Master Data
    print("Creating Master Data...")
    
    # Category ID 1 is "セルセーバー" (from seed)
    cat_id = 1
    
    # Create Type
    type_id = create_device_type(cat_id, "Test Device Type A")
    print(f"[x] Created Device Type: ID {type_id}")
    
    # Create Items
    item1_id = create_item("Power Cord", "Check for damage")
    item2_id = create_item("Main Unit", "Check screen")
    item3_id = create_item("Extra Adapter", "For special cases")
    print(f"[x] Created Items: {item1_id}, {item2_id}, {item3_id}")
    
    # Create Template (Device Type A requires Power Cord x1, Main Unit x1)
    add_template_line(type_id, item1_id, 1)
    add_template_line(type_id, item2_id, 1)
    print("[x] Created Template Lines")
    
    # 3. Create Unit and Overrides
    print("Creating Unit Data...")
    
    # Unit 1: Standard
    create_device_unit(type_id, "LOT-001", "2024-01-01", "Warehouse A")
    # Unit 2: With Override (Needs Extra Adapter, No Power Cord)
    create_device_unit(type_id, "LOT-002", "2024-01-02", "Warehouse B")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM device_units WHERE lot_number='LOT-002'")
    unit2_id = c.fetchone()[0]
    conn.close()
    
    # Add Overrides for Unit 2
    add_unit_override(unit2_id, item3_id, 'add', 1)     # Add Extra Adapter
    add_unit_override(unit2_id, item1_id, 'remove', 0)  # Remove Power Cord
    print(f"[x] Created Overrides for Unit {unit2_id} (LOT-002)")
    
    # 4. Verify Logic
    print("Verifying Checklist Logic...")
    
    checklist = get_synthesized_checklist(type_id, unit2_id)
    
    # Expected: Main Unit x1, Extra Adapter x1. Power Cord should be gone.
    item_names = [i['name'] for i in checklist]
    print(f"Checklist Items: {item_names}")
    
    if "Power Cord" not in item_names and "Extra Adapter" in item_names and "Main Unit" in item_names:
        print("[x] PASSED: Checklist synthesized correctly")
    else:
        print("[!] FAILED: Checklist logic incorrect")
        
    print("Verification Phase 1 Completed.")

if __name__ == "__main__":
    verify_phase1()
