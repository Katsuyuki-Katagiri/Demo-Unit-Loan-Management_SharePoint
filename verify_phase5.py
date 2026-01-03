
import sqlite3
import os
import json
import datetime
from src.database import (
    DB_PATH, init_db, migrate_phase5, create_device_type, create_item,
    create_device_unit, get_device_units, create_issue,
    add_notification_member, get_notification_logs, save_system_setting,
    get_unit_status_counts, create_loan, create_return
)
from src.logic import trigger_issue_notification, calculate_utilization

def setup_test_data():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    
    init_db() # Runs migrate_phase5 internal
    # Just in case
    migrate_phase5()
    
    # User
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO users (email, name, password_hash, role) VALUES ('admin@example.com', 'Admin User', 'hash', 'admin')")
    user_id = c.lastrowid
    
    c.execute("INSERT INTO categories (name) VALUES ('Cat A')")
    cat_id = c.lastrowid
    conn.commit()
    conn.close()
    
    type_id = create_device_type(cat_id, "Type A")
    return user_id, cat_id, type_id

def verify():
    print("--- Starting Phase 5 Verification ---")
    
    user_id, cat_id, type_id = setup_test_data()
    create_device_unit(type_id, "LOT1", "2024-01-01", "Loc A")
    # Fetch unit
    units = get_device_units(type_id)
    u1 = units[0]
    
    # --- Test 1: Notification ---
    print("\n[Test 1] Notification")
    # Add User to Group
    add_notification_member(cat_id, user_id)
    
    # Configure SMTP (Disabled)
    save_system_setting('smtp_config', json.dumps({"enabled": False}))
    
    # Create Issue -> Trigger
    print("Triggering Issue Notification...")
    # Manually creating issue to get ID
    # logic.process_loan calls create_issue -> trigger. Here we test trigger direct.
    issue_id = create_issue(u1['id'], 1, "Test Issue", "Admin") # 1 is fake session_id
    trigger_issue_notification(u1['id'], issue_id, "Test Summary")
    
    # Check Logs
    logs = get_notification_logs()
    assert len(logs) > 0
    l = logs[0]
    print(f"Log: {l['event_type']} -> {l['recipient']} ({l['status']})")
    assert l['status'] == 'logged_only'
    assert l['related_id'] == issue_id
    print("[x] Notification Logged Successfully")
    
    # --- Test 2: Utilization ---
    print("\n[Test 2] Utilization Calculation")
    
    # Scenario A: 3 days loan (Jan 1 - Jan 3)
    loan_id = create_loan(u1['id'], "2024-01-01", "Dest", "Purp", user_id)
    # create_loan DB function doesn't update status, logic does. Mock it here.
    from src.database import update_unit_status
    update_unit_status(u1['id'], 'loaned')
    
    create_return(loan_id, "2024-01-03", user_id)
    update_unit_status(u1['id'], 'in_stock')
    
    # Calc Period: Jan 1 - Jan 5 (5 days). Loan is 3 days.
    # Rate: 3/5 = 60%
    rate = calculate_utilization(u1['id'], "2024-01-01", "2024-01-05")
    print(f"Utilization (Jan 1-5, Loan 1-3): {rate}%")
    assert rate == 60.0
    
    # Scenario B: Single Day Loan (Jan 10)
    loan_id2 = create_loan(u1['id'], "2024-01-10", "Dest", "Purp", user_id)
    update_unit_status(u1['id'], 'loaned')
    create_return(loan_id2, "2024-01-10", user_id)
    update_unit_status(u1['id'], 'in_stock')
    
    # Calc Period: Jan 10 (1 day). Loan is 1 day.
    # Rate: 1/1 = 100%
    rate = calculate_utilization(u1['id'], "2024-01-10", "2024-01-10")
    print(f"Utilization (Jan 10, Loan 10): {rate}%")
    assert rate == 100.0
    
    # Scenario C: Open Loan (Jan 20 - ...)
    loan_id3 = create_loan(u1['id'], "2024-01-20", "Dest", "Purp", user_id)
    update_unit_status(u1['id'], 'loaned')
    # No return.
    
    # Calc Period: Jan 20 - Jan 22 (3 days).
    # Loan covers all 3 days.
    rate = calculate_utilization(u1['id'], "2024-01-20", "2024-01-22")
    print(f"Utilization (Jan 20-22, Open from 20): {rate}%")
    assert rate == 100.0
    
    # Calc Period: Jan 15 - Jan 25 (11 days).
    # Loan covers Jan 20-25 (6 days).
    # Rate: 6/11 = 54.5%
    rate = calculate_utilization(u1['id'], "2024-01-15", "2024-01-25")
    print(f"Utilization (Jan 15-25, Open from 20): {rate}%")
    assert rate == 54.5
    
    print("[x] Utilization Calculated Correctly")
    
    # --- Test 3: Dashboard Metrics ---
    print("\n[Test 3] Dashboard Metrics")
    stats = get_unit_status_counts()
    print(f"Stats: {stats}")
    # u1 status? create_loan sets 'loaned'. create_return sets 'in_stock'.
    # Last action was loan_id3 (open). So status should be 'loaned'.
    # Wait, create_loan updates status to 'loaned'.
    # So stats should be {'loaned': 1}
    assert stats.get('loaned', 0) == 1
    print("[x] Dashboard Metrics Correct")

    print("\n--- Phase 5 Verification Completed Successfully ---")

if __name__ == "__main__":
    verify()
