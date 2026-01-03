
import sqlite3
import os
from src.database import (
    DB_PATH, init_db, create_device_type, create_item, add_template_line,
    create_device_unit, get_device_units, update_unit_status,
    create_loan, create_check_session, create_check_line, create_issue,
    get_active_loan, get_device_unit_by_id, get_open_issues
)
from src.logic import process_loan, process_return

def setup_test_data():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    init_db()
    
    # 1. Create Master Data
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO categories (name) VALUES ('Test Category')")
    cat_id = c.lastrowid
    conn.commit()
    conn.close()
    
    type_id = create_device_type(cat_id, "Test Type A")
    item1 = create_item("Item 1")
    item2 = create_item("Item 2")
    
    add_template_line(type_id, item1, 1)
    add_template_line(type_id, item2, 2)
    
    # 2. Create Units
    create_device_unit(type_id, "LOT100", "2023-01-01", "Shelf A")
    create_device_unit(type_id, "LOT200", "2023-01-01", "Shelf B")
    
    units = get_device_units(type_id)
    return units[0], units[1], item1, item2

def verify():
    print("--- Starting Phase 3 Verification ---")
    
    unit1, unit2, item1, item2 = setup_test_data()
    print(f"Created Test Units: U1={unit1['id']}, U2={unit2['id']}")
    
    check_ok = [
        {'item_id': item1, 'name': 'Item 1', 'required_qty': 1, 'result': 'OK'},
        {'item_id': item2, 'name': 'Item 2', 'required_qty': 2, 'result': 'OK'}
    ]
    
    # --- Scenario 1: Normal Loan -> Normal Return ---
    print("\n[Test 1] Normal Flow: Loan -> Return")
    
    # Loan
    process_loan(unit1['id'], "2024-02-01", "Hospital A", "Demo", check_ok, "photo_L1", "Tester")
    u1_loaned = get_device_unit_by_id(unit1['id'])
    assert u1_loaned['status'] == 'loaned'
    print("[x] Loan Created. Status: loaned")
    
    # Return
    status = process_return(unit1['id'], "2024-02-05", check_ok, "photo_R1", "Tester")
    
    print(f"Return Result: {status}")
    assert status == 'in_stock'
    
    u1_returned = get_device_unit_by_id(unit1['id'])
    print(f"Unit Status in DB: {u1_returned['status']}")
    assert u1_returned['status'] == 'in_stock'
    
    # Verify active loan is gone
    l = get_active_loan(unit1['id'])
    assert l is None
    print("[x] No active loan found.")

    # --- Scenario 2: Loan -> NG Return -> Needs Attention ---
    print("\n[Test 2] NG Flow: Loan -> Return (NG)")
    
    # Loan
    process_loan(unit2['id'], "2024-02-01", "Hospital B", "Rent", check_ok, "photo_L2", "Tester")
    u2_loaned = get_device_unit_by_id(unit2['id'])
    assert u2_loaned['status'] == 'loaned'
    print("[x] Loan Created. Status: loaned")
    
    # Return with NG
    check_ng = [
        {'item_id': item1, 'name': 'Item 1', 'required_qty': 1, 'result': 'NG', 'ng_reason': '紛失'},
        {'item_id': item2, 'name': 'Item 2', 'required_qty': 2, 'result': 'OK'}
    ]
    
    status_ng = process_return(unit2['id'], "2024-02-10", check_ng, "photo_R2", "Tester")
    
    print(f"Return Result: {status_ng}")
    assert status_ng == 'needs_attention'
    
    u2_needs = get_device_unit_by_id(unit2['id'])
    print(f"Unit Status in DB: {u2_needs['status']}")
    assert u2_needs['status'] == 'needs_attention'
    
    issues = get_open_issues(unit2['id'])
    print(f"Open Issues: {len(issues)}")
    assert len(issues) > 0
    print(f"Issue: {issues[0]['summary']}")
    
    # Verify active loan closed despite Isuses
    l2 = get_active_loan(unit2['id'])
    assert l2 is None
    print("[x] Active loan closed successfully.")

    print("\n--- Phase 3 Verification Completed Successfully ---")

if __name__ == "__main__":
    verify()
