import sys, os
sys.path.insert(0, r'C:\Users\oftan\AppData\Local\Temp\opencode\contract-mgmt')
from app import app, db, PurchaseOrder, BudgetSource
with app.app_context():
    total = PurchaseOrder.query.count()
    print(f'Total POs: {total}')
    max_sn = db.session.query(db.func.max(PurchaseOrder.serial_number)).scalar()
    print(f'Max SN: {max_sn}')
    # Check currencies in new POs
    from sqlalchemy import text
    currs = db.session.execute(text("SELECT currency, COUNT(*) FROM purchase_order WHERE serial_number >= 1725 GROUP BY currency ORDER BY COUNT(*) DESC")).fetchall()
    print(f'Currency distribution (new POs): {currs}')
    # Check budget sources in new POs
    sources = db.session.execute(text("SELECT bs.name, COUNT(*) FROM purchase_order po LEFT JOIN budget_source bs ON po.budget_source_id=bs.id WHERE po.serial_number >= 1725 GROUP BY bs.name ORDER BY COUNT(*) DESC")).fetchall()
    print(f'Budget sources (new POs): {sources}')
    # Check if there's "GF-CBHIV" or "RDF-O" etc in budget_source
    all_bs = BudgetSource.query.all()
    print(f'All budget sources: {[(b.id, b.name) for b in all_bs]}')
