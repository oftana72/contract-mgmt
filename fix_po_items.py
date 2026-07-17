import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, PurchaseOrder, LineItem

with app.app_context():
    po = PurchaseOrder.query.filter_by(po_number='4500011316').first()
    if not po:
        print('PO 4500011316 not found')
        sys.exit(1)
    print(f'PO #{po.id}: {po.po_number} - {po.supplier.name if po.supplier else "?"}')
    
    items = LineItem.query.filter_by(po_id=po.id).all()
    print(f'Current items ({len(items)}):')
    for item in items:
        print(f'  [{item.id}] {item.description} | {item.quantity} {item.unit} @ {item.unit_price}')
    
    keep_desc = 'Chemical gadolinium chelate 1mmol/ml solution for injection of 7.5ml'
    keep = None
    removed = 0
    for item in items:
        if item.description and keep_desc in item.description:
            keep = item
        else:
            db.session.delete(item)
            removed += 1
    
    db.session.commit()
    print(f'\nRemoved {removed} items, keeping:')
    if keep:
        print(f'  [{keep.id}] {keep.description} | {keep.quantity} {keep.unit} @ {keep.unit_price}')
    else:
        print('  (not found - nothing kept)')
        remaining = LineItem.query.filter_by(po_id=po.id).all()
        print(f'Remaining items: {len(remaining)}')
