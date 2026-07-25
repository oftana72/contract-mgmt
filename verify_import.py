from app import app, db
from sqlalchemy import text
with app.app_context():
    total = db.session.execute(text('SELECT COUNT(*) FROM purchase_orders')).scalar()
    max_sn = db.session.execute(text('SELECT MAX(serial_number) FROM purchase_orders')).scalar()
    items = db.session.execute(text('SELECT COUNT(*) FROM line_items')).scalar()
    etb = db.session.execute(text("SELECT COUNT(*) FROM purchase_orders WHERE currency='ETB'")).scalar()
    usd = db.session.execute(text("SELECT COUNT(*) FROM purchase_orders WHERE currency='USD'")).scalar()
    eur = db.session.execute(text("SELECT COUNT(*) FROM purchase_orders WHERE currency='EUR'")).scalar()
    empty_cur = db.session.execute(text("SELECT COUNT(*) FROM purchase_orders WHERE currency IS NULL OR currency=''")).scalar()
    print(f'Total POs: {total}')
    print(f'Max SN: {max_sn}')
    print(f'Line items: {items}')
    print(f'ETB: {etb}, USD: {usd}, EUR: {eur}, No currency: {empty_cur}')
    new_count = db.session.execute(text('SELECT COUNT(*) FROM purchase_orders WHERE serial_number >= 1620')).scalar()
    print(f'New POs (SN >= 1620): {new_count}')
    rows = db.session.execute(text('SELECT serial_number, po_number, total_po_amount, currency FROM purchase_orders WHERE serial_number >= 1620 ORDER BY serial_number LIMIT 5')).fetchall()
    for r in rows:
        print(f'  SN={r.serial_number} PO={r.po_number} {r.total_po_amount} {r.currency}')
    print('VERIFY DONE')
