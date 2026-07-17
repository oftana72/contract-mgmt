import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, PurchaseOrder, LineItem, PerformanceGuarantee, LetterOfCredit, Shipment, Supplier, LocalAgent

with app.app_context():
    test_pos = PurchaseOrder.query.filter(
        PurchaseOrder.po_number.in_(['TEST-PO-2026-001', 'TEST-PO-2026-002', 'PO-SIMPLE-001', 'TEST-PO-001'])
    ).all()
    
    for po in test_pos:
        supplier_name = po.supplier.name if po.supplier else '?'
        print(f'Deleting PO #{po.id}: {po.po_number} - {supplier_name}')
        LineItem.query.filter_by(po_id=po.id).delete()
        PerformanceGuarantee.query.filter_by(po_id=po.id).delete()
        LetterOfCredit.query.filter_by(po_id=po.id).delete()
        Shipment.query.filter_by(po_id=po.id).delete()
        db.session.delete(po)
    
    db.session.commit()
    print(f'Deleted {len(test_pos)} test POs')

    for name in ['Test Supplier Co.', 'Another Supplier', 'Clean Supplier']:
        s = Supplier.query.filter_by(name=name).first()
        if s and len(s.orders) == 0:
            db.session.delete(s)
            print(f'Cleaned up supplier: {name}')

    for name in ['Test Agent PLC', 'Local Agent 1']:
        a = LocalAgent.query.filter_by(name=name).first()
        if a and len(a.orders) == 0:
            db.session.delete(a)
            print(f'Cleaned up agent: {name}')

    db.session.commit()
    remaining = PurchaseOrder.query.count()
    print(f'Remaining POs: {remaining}')
