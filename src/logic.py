from src.database import (
    get_template_lines, get_unit_overrides
)

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
            create_issue(device_unit_id, session_id, summary, user_name)
            
    # 5. Update Status
    if has_ng:
        update_unit_status(device_unit_id, 'needs_attention')
        return "needs_attention"
    else:
        update_unit_status(device_unit_id, 'loaned')
        return "loaned"

# --- Phase 3: Return Logic ---

from src.database import create_return, get_active_loan

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
            create_issue(device_unit_id, session_id, summary, user_name)
            
    # 5. Update Status (Recalculate)
    # Check if ANY open issues exist (from this return OR previous)
    issues = get_open_issues(device_unit_id)
    if issues:
        update_unit_status(device_unit_id, 'needs_attention')
        return "needs_attention"
    else:
        update_unit_status(device_unit_id, 'in_stock')
        return "in_stock"
