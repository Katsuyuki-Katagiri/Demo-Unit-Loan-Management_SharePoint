from src.database import (
    get_template_lines, get_unit_overrides, DB_PATH
)
import sqlite3
import sqlite3
from PIL import Image, ImageOps # type: ignore
import base64
from io import BytesIO

def get_image_base64(image_path):
    """Convert image to base64 string for HTML embedding, max 500px."""
    try:
        img = Image.open(image_path)
        img.thumbnail((500, 500), Image.Resampling.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        print(f"Error encoding image: {e}")
        return None

def get_synthesized_checklist(device_type_id: int, device_unit_id: int):
    """
    Synthesize the final checklist for a specific unit.
    Base: Template Lines for device_type_id
    Apply: Unit Overrides (add/remove/qty)
    Return: List of items dict {id, name, photo_path, required_qty, ...}
    """
    
    # 1. Get Base Template
    # returns list of Row(id, device_type_id, item_id, required_qty, sort_order, item_name, photo_path)
    base_lines = get_template_lines(device_type_id)
    
    # Convert to a dict for easier manipulation: item_id -> dict
    checklist_map = {}
    for line in base_lines:
        checklist_map[line['item_id']] = {
            'item_id': line['item_id'],
            'name': line['item_name'],
            'photo_path': line['photo_path'],
            'required_qty': line['required_qty'],
            'sort_order': line['sort_order'],
            'is_override': False
        }
        
    # 2. Get Overrides
    # returns list of Row(id, device_unit_id, item_id, action, qty, item_name)
    overrides = get_unit_overrides(device_unit_id)
    
    for ov in overrides:
        item_id = ov['item_id']
        action = ov['action']
        qty = ov['qty']
        
        if action == 'remove':
            if item_id in checklist_map:
                del checklist_map[item_id]
        
        elif action == 'qty':
            if item_id in checklist_map:
                checklist_map[item_id]['required_qty'] = qty
                checklist_map[item_id]['is_override'] = True
        
        elif action == 'add':
            # Add new item
            checklist_map[item_id] = {
                'item_id': item_id,
                'name': ov['item_name'],
                'photo_path': ov['photo_path'],
                'required_qty': qty,
                'sort_order': 999, # Put at end
                'is_override': True
            }

    # 3. Convert back to list and sort
    final_list = list(checklist_map.values())
    final_list.sort(key=lambda x: x['sort_order'])
    
    return final_list

# --- Phase 2: Loan Logic ---

from src.database import (
    create_loan, create_check_session, create_check_line, 
    create_issue, update_unit_status, get_open_issues,
    get_device_unit_by_id
)
import datetime

def process_loan(
    device_unit_id: int,
    checkout_date: str,
    destination: str,
    purpose: str,
    check_results: list, # List of dict: {item_id, result, ng_reason, found_qty, comment}
    photo_dir: str,
    user_id: int = None,
    user_name: str = "Unknown"
):
    """
    Process a loan request.
    1. Validation: Unit IN_STOCK? No Open Issues?
    2. Create Loan
    3. Create Check Session
    4. Create Check Lines -> If NG, flag issues
    5. Update Unit Status (Loaned or Needs Attention)
    """
    
    # 1. Validation
    # get_device_unit_by_id returns the row, so we can check status
    unit = get_device_unit_by_id(device_unit_id)
    
    if unit['status'] != 'in_stock':
        raise ValueError(f"Unit is not in stock (current: {unit['status']})")
        
    issues = get_open_issues(device_unit_id)
    if issues:
        raise ValueError("Unit has open issues and cannot be loaned.")

    # 2. Create Loan
    loan_id = create_loan(
        device_unit_id=device_unit_id,
        checkout_date=checkout_date,
        destination=destination,
        purpose=purpose,
        checker_user_id=user_id
    )
    
    # 3. Create Check Session
    session_id = create_check_session(
        session_type='checkout',
        device_unit_id=device_unit_id,
        loan_id=loan_id,
        performed_by=user_name,
        device_photo_dir=photo_dir
    )
    
    # 4. Process Check Lines & Check for NG
    has_ng = False
    
    for res in check_results:
        # result: 'OK' or 'NG'
        is_ng = (res['result'] == 'NG')
        if is_ng:
            has_ng = True
            
        create_check_line(
            check_session_id=session_id,
            item_id=res['item_id'],
            required_qty=res['required_qty'],
            result=res['result'],
            ng_reason=res.get('ng_reason'),
            found_qty=res.get('found_qty'),
            comment=res.get('comment')
        )
        
        if is_ng:
            # Create Issue
            summary = f"NG Item: {res['name']} - {res.get('ng_reason')}"
            issue_id = create_issue(device_unit_id, session_id, summary, user_name)
            trigger_issue_notification(device_unit_id, issue_id, summary)
            
    # 5. Update Status
    if has_ng:
        update_unit_status(device_unit_id, 'needs_attention')
        return "needs_attention"
    else:
        update_unit_status(device_unit_id, 'loaned')
        return "loaned"

# --- Phase 3: Return Logic ---

        update_unit_status(device_unit_id, 'in_stock')
        return "in_stock"

# --- Phase 4 Logic ---

from src.database import (
    resolve_issue, cancel_record, get_related_records,
    get_open_issues, get_active_loan, update_unit_status,
    create_return, create_check_session, create_check_line
)

def recalculate_unit_status(device_unit_id: int):
    """
    Recalculate and update the status of a unit based on current Loans and Issues.
    Priority:
    1. Open Issues (not canceled) -> 'needs_attention'
    2. Active Loan (not canceled) -> 'loaned'
    3. Else -> 'in_stock'
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check Issues
    issues = get_open_issues(device_unit_id)
    if issues:
        new_status = 'needs_attention'
    else:
        # Check Loan
        loan = get_active_loan(device_unit_id)
        if loan:
            new_status = 'loaned'
        else:
            new_status = 'in_stock'
            
    conn.close()
    update_unit_status(device_unit_id, new_status)
    return new_status

def perform_issue_resolution(device_unit_id: int, issue_id: int, user_name: str):
    resolve_issue(issue_id, user_name)
    return recalculate_unit_status(device_unit_id)

def perform_cancellation(target_type: str, target_id: int, user_name: str, reason: str, device_unit_id: int):
    """
    Cancel a record and its dependents.
    target_type: 'loan', 'return' (, 'issue' - maybe)
    """
    if target_type == 'loan':
        # Cancel Loan
        cancel_record('loans', target_id, user_name, reason)
        
        # Cascade: Find related CheckSessions (checkout)
        related = get_related_records(loan_id=target_id)
        
        for sess_id in related['check_sessions']:
            cancel_record('check_sessions', sess_id, user_name, "Cascade from Loan Cancel")
            
        for iss_id in related['issues']:
            cancel_record('issues', iss_id, user_name, "Cascade from Loan Cancel")
            
        # If there were linked returns, we should probably cancel them too?
        # A loan shouldn't be cancelled if it was returned? Or strictly cancel everything?
        # User requirement: "All cancellation OK".
        for ret_id in related['returns']:
            cancel_record('returns', ret_id, user_name, "Cascade from Loan Cancel")
            
    elif target_type == 'return':
        # Cancel Return
        cancel_record('returns', target_id, user_name, reason)
        
        # We need to find the Loan ID to RE-OPEN it
        # But get_related_records doesn't give us the loan ID from return ID easily unless we query.
        # Let's assume the caller passes the loan_id or we fetch it.
        # Fetch return to get loan_id
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT loan_id FROM returns WHERE id = ?", (target_id,))
        ret_row = c.fetchone()
        conn.close()
        
        if ret_row:
            loan_id = ret_row['loan_id']
            # Re-open Loan
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE loans SET status = 'open' WHERE id = ?", (loan_id,))
            conn.commit()
            conn.close()
            
            # Cascade: Cancel Return CheckSession and its Issues
            # We need to find the check session linked to this return.
            # CheckSession has no return_id column directly, but session_type='return' and loan_id=?
            # Wait, `check_sessions` has `loan_id`. If multiple returns for same loan (re-return?), creates ambiguity.
            # But typically 1 loan = 1 return.
            # However, safer to search check_session by timestamp proximity or assume strict 1:1 if possible.
            # For this phase, let's look for session_type='return' and loan_id=loan_id AND not canceled.
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id FROM check_sessions WHERE loan_id = ? AND session_type = 'return' AND (canceled=0 OR canceled IS NULL)", (loan_id,))
            sessions = c.fetchall()
            conn.close()
            
            for (sess_id,) in sessions:
                cancel_record('check_sessions', sess_id, user_name, "Cascade from Return Cancel")
                # Cancel issues linked to this session
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT id FROM issues WHERE check_session_id = ? AND (canceled=0 OR canceled IS NULL)", (sess_id,))
                issues = c.fetchall()
                conn.close()
                for (iss_id,) in issues:
                    cancel_record('issues', iss_id, user_name, "Cascade from Return Cancel")

    recalculate_unit_status(device_unit_id)


def process_return(
    device_unit_id: int,
    return_date: str,
    check_results: list,
    photo_dir: str,
    user_id: int = None,
    user_name: str = "Unknown"
):
    """
    Process a return request.
    1. Validation: Unit has Active Loan?
    2. Create Return & Close Loan
    3. Create Check Session (type='return')
    4. Create Check Lines -> Flag Issues
    5. Update Unit Status (In Stock or Needs Attention)
    """
    
    # 1. Validation
    active_loan = get_active_loan(device_unit_id)
    if not active_loan:
        raise ValueError("No active loan found for this unit.")
        
    loan_id = active_loan['id']

    # 2. Create Return (Closes Loan)
    create_return(
        loan_id=loan_id,
        return_date=return_date,
        checker_user_id=user_id
    )
    
    # 3. Create Check Session
    session_id = create_check_session(
        session_type='return',
        device_unit_id=device_unit_id,
        loan_id=loan_id,
        performed_by=user_name,
        device_photo_dir=photo_dir
    )
    
    # 4. Process Check Lines
    has_ng = False
    
    for res in check_results:
        is_ng = (res['result'] == 'NG')
        if is_ng:
            has_ng = True
            
        create_check_line(
            check_session_id=session_id,
            item_id=res['item_id'],
            required_qty=res['required_qty'],
            result=res['result'],
            ng_reason=res.get('ng_reason'),
            found_qty=res.get('found_qty'),
            comment=res.get('comment')
        )
        
        if is_ng:
            # Create Issue
            summary = f"[Return] NG Item: {res['name']} - {res.get('ng_reason')}"
            issue_id = create_issue(device_unit_id, session_id, summary, user_name)
            trigger_issue_notification(device_unit_id, issue_id, summary)
            
    # 5. Update Status (Recalculate)
    # Check if ANY open issues exist (from this return OR previous)
    issues = get_open_issues(device_unit_id)
    if issues:
        update_unit_status(device_unit_id, 'needs_attention')
        return "needs_attention"
    else:
        update_unit_status(device_unit_id, 'in_stock')
        return "in_stock"

# --- Phase 5 Logic ---

from src.database import (
    get_notification_members, get_system_setting, log_notification,
    get_device_unit_by_id, get_device_type_by_id
)
import smtplib
import json
from email.mime.text import MIMEText

def trigger_issue_notification(device_unit_id: int, issue_id: int, summary: str):
    """
    Trigger notification for a new issue.
    1. Identify Category -> Group Members
    2. Check SMTP Settings
    3. Log and Send (if enabled)
    """
    # 1. Get Unit -> Type -> Category
    unit = get_device_unit_by_id(device_unit_id)
    type_info = get_device_type_by_id(unit['device_type_id'])
    category_id = type_info['category_id']
    
    members = get_notification_members(category_id)
    if not members:
        return # No one to notify
        
    # 2. SMTP Settings
    smtp_config_json = get_system_setting('smtp_config')
    smtp_enabled = False
    smtp_config = {}
    if smtp_config_json:
        try:
            smtp_config = json.loads(smtp_config_json)
            smtp_enabled = smtp_config.get('enabled', False)
        except:
            pass
            
    # 3. Process Members
    for m in members:
        recipient_email = m['email']
        recipient_name = m['name']
        
        # Always Log
        log_status = 'logged_only'
        error_msg = None
        
        if smtp_enabled and recipient_email:
            try:
                # Send Email
                msg = MIMEText(f"""
                Hello {recipient_name},
                
                An issue has been reported for {type_info['name']} (Lot: {unit['lot_number']}).
                
                Issue: {summary}
                
                Please check the system for details.
                """)
                msg['Subject'] = f"[Alert] Issue Reported: {type_info['name']}"
                msg['From'] = smtp_config.get('from_addr', 'noreply@example.com')
                msg['To'] = recipient_email
                
                with smtplib.SMTP(smtp_config.get('host', 'localhost'), int(smtp_config.get('port', 25))) as server:
                    if smtp_config.get('user') and smtp_config.get('password'):
                         # Optional: StartTLS if port 587? For now simple implementation.
                         if int(smtp_config.get('port', 25)) == 587:
                             server.starttls()
                         server.login(smtp_config.get('user'), smtp_config.get('password'))
                    server.send_message(msg)
                
                log_status = 'sent'
            except Exception as e:
                log_status = 'failed'
                error_msg = str(e)
                
        log_notification('issue_created', issue_id, f"{recipient_name} ({recipient_email})", log_status, error_msg)


def calculate_utilization(device_unit_id: int, start_date_str: str, end_date_str: str):
    """
    Calculate utilization rate (%) for a specific period.
    Formula: (Occupied Days / Total Days) * 100
    Occupied: Loan periods overlapping the range. Same day loan = 1 day.
    """
    start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    total_days = (end_date - start_date).days + 1
    if total_days <= 0:
        return 0.0
        
    occupied_days = 0
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT l.checkout_date, r.return_date, l.status, l.canceled 
        FROM loans l
        LEFT JOIN returns r ON l.id = r.loan_id AND (r.canceled = 0 OR r.canceled IS NULL)
        WHERE l.device_unit_id = ? AND (l.canceled = 0 OR l.canceled IS NULL)
    """, (device_unit_id,))
    loans = c.fetchall()
    conn.close()
    
    occupied_dates = set()
    
    for l in loans:
        l_start = datetime.datetime.strptime(l['checkout_date'], '%Y-%m-%d').date()
        
        if l['return_date']:
             l_end = datetime.datetime.strptime(l['return_date'], '%Y-%m-%d').date()
        else:
             # Open loan: up to period end
             l_end = end_date
             
        # Clip to Period
        eff_start = max(start_date, l_start)
        eff_end = min(end_date, l_end)
        
        if eff_start <= eff_end:
            # Inclusive range
            curr = eff_start
            while curr <= eff_end:
                occupied_dates.add(curr)
                curr += datetime.timedelta(days=1)
                
    occupied_count = len(occupied_dates)
    return round((occupied_count / total_days) * 100, 1)

