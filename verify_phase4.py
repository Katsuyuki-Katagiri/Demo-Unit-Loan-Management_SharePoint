
import sqlite3
import os
from src.database import (
    DB_PATH, init_db, create_device_type, create_item, add_template_line,
    create_device_unit, get_device_units, update_unit_status,
    create_loan, create_check_session, create_check_line, create_issue,
    get_device_unit_by_id, get_open_issues, get_active_loan,
    migrate_phase4
)
from src.logic import process_loan, process_return, perform_issue_resolution, perform_cancellation

def setup_test_data():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    init_db()
    migrate_phase4() # Ensure columns exist
    
    # Master Data
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO categories (name) VALUES ('Test Category')")
    cat_id = c.lastrowid
    conn.commit()
    conn.close()
    
    type_id = create_device_type(cat_id, "Test Type A")
    item1 = create_item("Item 1")
    add_template_line(type_id, item1, 1)
    
    # Create Units
    create_device_unit(type_id, "LOT1", "2023-01-01", "Loc A")
    create_device_unit(type_id, "LOT2", "2023-01-01", "Loc B")
    create_device_unit(type_id, "LOT3", "2023-01-01", "Loc C")
    
    units = get_device_units(type_id)
    return units, item1

def verify():
    print("--- Starting Phase 4 Verification ---")
    
    units, item1 = setup_test_data()
    u1, u2, u3 = units[0], units[1], units[2]
    check_ok = [{'item_id': item1, 'name': 'Item 1', 'required_qty': 1, 'result': 'OK'}]
    check_ng = [{'item_id': item1, 'name': 'Item 1', 'required_qty': 1, 'result': 'NG', 'ng_reason': 'Lost'}]
    
    # --- Scenario 1: Issue Resolution ---
    print("\n[Test 1] Issue Resolution")
    # Loan -> NG Return -> Needs Attention
    process_loan(u1['id'], "2024-03-01", "Hosp A", "Demo", check_ok, "p", "User")
    status = process_return(u1['id'], "2024-03-05", check_ng, "p", "User")
    assert status == 'needs_attention'
    print("[x] Unit is Needs Attention (NG Return)")
    
    issues = get_open_issues(u1['id'])
    assert len(issues) == 1
    
    # Resolve
    print("Resolving Issue...")
    status = perform_issue_resolution(u1['id'], issues[0]['id'], "Admin")
    print(f"Status after resolution: {status}")
    assert status == 'in_stock'
    assert len(get_open_issues(u1['id'])) == 0
    print("[x] Issue Resolved, Unit In Stock")

    # --- Scenario 2: Loan Cancellation ---
    print("\n[Test 2] Loan Cancellation")
    # Loan -> Loaned
    process_loan(u2['id'], "2024-03-01", "Hosp B", "Demo", check_ok, "p", "User")
    u2_loaned = get_device_unit_by_id(u2['id'])
    assert u2_loaned['status'] == 'loaned'
    
    active_loan = get_active_loan(u2['id'])
    print(f"Cancelling Loan ID {active_loan['id']}...")
    
    perform_cancellation('loan', active_loan['id'], "Admin", "Mistake", u2['id'])
    
    u2_canceled = get_device_unit_by_id(u2['id'])
    print(f"Status after cancel: {u2_canceled['status']}")
    assert u2_canceled['status'] == 'in_stock'
    print("[x] Loan Cancelled, Unit In Stock")
    
    # --- Scenario 3: Return Cancellation ---
    print("\n[Test 3] Return Cancellation")
    # Loan -> Return -> In Stock
    process_loan(u3['id'], "2024-03-01", "Hosp C", "Demo", check_ok, "p", "User")
    process_return(u3['id'], "2024-03-05", check_ok, "p", "User")
    u3_returned = get_device_unit_by_id(u3['id'])
    assert u3_returned['status'] == 'in_stock'
    
    # Find the return (it was the last one closed)
    # We don't have get_last_return helper, assume we query DB
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM returns ORDER BY id DESC LIMIT 1")
    ret_id = c.fetchone()[0]
    conn.close()
    
    print(f"Cancelling Return ID {ret_id}...")
    perform_cancellation('return', ret_id, "Admin", "Wrong Date", u3['id'])
    
    u3_reopened = get_device_unit_by_id(u3['id'])
    print(f"Status after return cancel: {u3_reopened['status']}")
    assert u3_reopened['status'] == 'loaned'
    
    active_loan = get_active_loan(u3['id'])
    assert active_loan is not None
    print("[x] Return Cancelled, Loan Re-opened")

    print("\n--- Phase 4 Verification Completed Successfully ---")

if __name__ == "__main__":
    verify()
