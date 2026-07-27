"""
Import PG data (columns R-W) from Google Sheet gid=259920423 for each PO.
Matches by PO Number (col 3).
"""
import csv, io, urllib.request, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, PurchaseOrder, PerformanceGuarantee, parse_date

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=259920423'

def import_pg_from_sheet(url=None):
    url = url or SHEET_URL
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    raw = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')
    reader = csv.reader(io.StringIO(raw))
    
    updated = 0
    errors = []
    seen_pos = set()
    
    for i, row in enumerate(reader):
        if i < 2:
            continue  # skip header rows
        po_number = row[3].strip() if len(row) > 3 else ''
        if not po_number or not po_number.isdigit():
            continue
        if po_number in seen_pos:
            continue
        seen_pos.add(po_number)
        
        pg_req = parse_date(row[17].strip()) if len(row) > 17 and row[17].strip() else None
        pg_recv = parse_date(row[18].strip()) if len(row) > 18 and row[18].strip() else None
        pg_conf = parse_date(row[19].strip()) if len(row) > 19 and row[19].strip() else None
        bank = row[20].strip() if len(row) > 20 and row[20].strip() else None
        ref = row[21].strip() if len(row) > 21 and row[21].strip() else None
        pg_exp = parse_date(row[22].strip()) if len(row) > 22 and row[22].strip() else None
        remain_days = row[23].strip() if len(row) > 23 and row[23].strip() else None
        submit_pg = row[24].strip() if len(row) > 24 and row[24].strip() else None
        pg_status = row[25].strip() if len(row) > 25 and row[25].strip() else None
        status_date = parse_date(row[26].strip()) if len(row) > 26 and row[26].strip() else None
        receiver = row[27].strip() if len(row) > 27 and row[27].strip() else None
        bi_officer = row[28].strip() if len(row) > 28 and row[28].strip() else None
        
        if not any([pg_req, pg_recv, pg_conf, bank, ref, pg_exp, pg_status, receiver, bi_officer]):
            continue
        
        po = PurchaseOrder.query.filter_by(po_number=po_number).first()
        if not po:
            errors.append(f'PO {po_number} not found')
            continue
        
        pg = po.performance_guarantees.first()
        if pg:
            if pg_req: pg.requested_date = pg_req
            if pg_recv: pg.received_date = pg_recv
            if pg_conf: pg.confirmed_date = pg_conf
            if bank: pg.bank_name = bank
            if ref: pg.pg_reference = ref
            if pg_exp: pg.expiry_date = pg_exp
            if pg_status: pg.status = pg_status
            if status_date: pg.status_date = status_date
            if receiver: pg.pg_receiver_name = receiver
            if bi_officer: pg.bi_officer = bi_officer
        else:
            db.session.add(PerformanceGuarantee(
                po_id=po.id,
                requested_date=pg_req,
                received_date=pg_recv,
                confirmed_date=pg_conf,
                bank_name=bank,
                pg_reference=ref,
                expiry_date=pg_exp,
                status=pg_status,
                status_date=status_date,
                pg_receiver_name=receiver,
                bi_officer=bi_officer,
            ))
        
        # Also update PO-level PG expiry if not set
        if pg_exp and not po.pg_expiry_date:
            po.pg_expiry_date = pg_exp
        
        updated += 1
        
        if updated % 100 == 0:
            db.session.commit()
    
    db.session.commit()
    return updated, errors

if __name__ == '__main__':
    with app.app_context():
        u, errs = import_pg_from_sheet()
        print(f'Updated POs: {u}')
        if errs:
            print(f'Errors ({len(errs)}):')
            for e in errs[:20]:
                print(f'  {e}')
