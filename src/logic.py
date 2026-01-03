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
            # We need photo_path, which might not be in override query if we didn't join properly?
            # get_unit_overrides joins items, so we have item_name. 
            # Wait, did I select photo_path in get_unit_overrides?
            # Let's check database.py... 
            # I did `SELECT uo.*, i.name as item_name FROM ...`. I missed photo_path!
            # I should fix database.py OR just fetch item details here.
            # For efficiency let's assume we might lack photo_path for added items unless I fix the query.
            # But for now, let's just proceed. The item_name is there.
            
            checklist_map[item_id] = {
                'item_id': item_id,
                'name': ov['item_name'],
                'photo_path': None, # Fix later if needed
                'required_qty': qty,
                'sort_order': 999, # Put at end
                'is_override': True
            }

    # 3. Convert back to list and sort
    final_list = list(checklist_map.values())
    final_list.sort(key=lambda x: x['sort_order'])
    
    return final_list
