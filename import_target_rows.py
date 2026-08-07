"""
Import the 10 target rows (SN 24-31, 34-35) from Google Sheet gid=1197797932.
Creates missing POs; enriches existing PO 4500010303.
Matches by PO number. Skips everything else.
"""
import csv, os, sys, io, urllib.request
sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, Supplier, LocalAgent, BudgetSource, PurchaseOrder, LineItem, PerformanceGuarantee, LetterOfCredit, Shipment, BIOfficer, ShipmentOfficer, POStatus, parse_date, parse_float, budget_year

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=1197797932'

TARGET_PNOS = {
    '4500012204', '4500012205', '4500012221', '4500012324', '4500012898',
    '4500012294', '4500012322', '4500012911', '4500010303', '4500013049',
}


def get_or_create(model, **kwargs):
    if not kwargs:
        return None
    existing = model.query.filter_by(**kwargs).first()
    if existing:
        return existing
    obj = model(**kwargs)
    db.session.add(obj)
    db.session.flush()
    return obj


def import_target_rows(url=SHEET_URL):
    print(f"Downloading: {url}")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode('utf-8')
    rows = list(csv.reader(io.StringIO(raw)))
    print(f"Loaded {len(rows)} rows")

    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == 'S.N':
            header_idx = i
            break
    if header_idx is None:
        print("ERROR: could not find header row")
        return 0, 0

    created = 0
    enriched = 0
    skipped = 0

    for i in range(header_idx + 1, len(rows)):
        row = rows[i]
        if not row or not any(cell.strip() for cell in row):
            continue
        po_number = row[3].strip().replace('\n', ' / ') if len(row) > 3 else ''
        if po_number not in TARGET_PNOS:
            continue

        received_date = parse_date(row[1]) if len(row) > 1 else None
        tender_ref = row[2].strip() if len(row) > 2 else ''
        supplier_name = row[4].strip() if len(row) > 4 else ''
        country = row[5].strip() if len(row) > 5 else ''
        local_agent_name = row[6].strip() if len(row) > 6 else ''

        desc = row[7].strip() if len(row) > 7 and row[7].strip() else ''
        unit = row[8].strip() if len(row) > 8 else ''
        qty = parse_float(row[9]) if len(row) > 9 else None
        unit_price = parse_float(row[10]) if len(row) > 10 else None
        total_price = parse_float(row[11]) if len(row) > 11 else None

        total_po_amount = parse_float(row[12]) if len(row) > 12 else None
        currency = row[13].strip() if len(row) > 13 else ''
        budget_name = row[14].strip() if len(row) > 14 else ''
        mode_of_shipment = row[15].strip() if len(row) > 15 else ''
        po_transferred = parse_date(row[16]) if len(row) > 16 else None

        supplier = None
        if supplier_name:
            supplier = Supplier.query.filter_by(name=supplier_name).first()
            if not supplier:
                supplier = Supplier(name=supplier_name, country=country)
                db.session.add(supplier)
                db.session.flush()
        local_agent = get_or_create(LocalAgent, name=local_agent_name) if local_agent_name else None
        budget_source = get_or_create(BudgetSource, name=budget_name) if budget_name else None

        existing_po = PurchaseOrder.query.filter_by(po_number=po_number).first()

        if existing_po:
            po = existing_po
            po.received_date = received_date
            po.budget_year = budget_year(received_date)
            po.tender_reference = tender_ref
            po.supplier_id = supplier.id if supplier else po.supplier_id
            po.country_raw = country
            po.local_agent_id = local_agent.id if local_agent else po.local_agent_id
            po.total_po_amount = total_po_amount
            po.currency = currency
            po.budget_source_id = budget_source.id if budget_source else po.budget_source_id
            po.mode_of_shipment = mode_of_shipment
            po.po_transferred_date = po_transferred
            enriched += 1
            print(f"  Enriched {po_number} (id {po.id})")
        else:
            po = PurchaseOrder(
                serial_number=None,
                received_date=received_date,
                budget_year=budget_year(received_date),
                tender_reference=tender_ref,
                po_number=po_number,
                supplier_id=supplier.id if supplier else None,
                supplier_name_raw=supplier_name if not supplier else None,
                country_raw=country,
                local_agent_id=local_agent.id if local_agent else None,
                local_agent_raw=local_agent_name if not local_agent else None,
                total_po_amount=total_po_amount,
                currency=currency,
                budget_source_id=budget_source.id if budget_source else None,
                mode_of_shipment=mode_of_shipment,
                po_transferred_date=po_transferred,
            )
            db.session.add(po)
            db.session.flush()
            created += 1
            print(f"  Created {po_number}")

        # Line item (only if none exist)
        if desc and po.line_items.count() == 0:
            db.session.add(LineItem(po_id=po.id, description=desc, unit=unit,
                                    quantity=qty, unit_price=unit_price, total_price=total_price))

        # PG fields
        pg_req = parse_date(row[17]) if len(row) > 17 else None
        pg_recv = parse_date(row[18]) if len(row) > 18 else None
        pg_conf = parse_date(row[19]) if len(row) > 19 else None
        bank_name = row[20].strip() if len(row) > 20 else ''
        pg_ref = row[21].strip() if len(row) > 21 else ''
        pg_exp = parse_date(row[22]) if len(row) > 22 else None
        if any([pg_req, pg_recv, pg_conf, bank_name, pg_ref, pg_exp]):
            pg = po.performance_guarantees.first()
            if pg:
                if pg_req: pg.requested_date = pg_req
                if pg_recv: pg.received_date = pg_recv
                if pg_conf: pg.confirmed_date = pg_conf
                if bank_name: pg.bank_name = bank_name
                if pg_ref: pg.pg_reference = pg_ref
                if pg_exp: pg.expiry_date = pg_exp
            else:
                db.session.add(PerformanceGuarantee(
                    po_id=po.id, requested_date=pg_req, received_date=pg_recv,
                    confirmed_date=pg_conf, bank_name=bank_name, pg_reference=pg_ref,
                    expiry_date=pg_exp))
            if pg_exp and not po.pg_expiry_date:
                po.pg_expiry_date = pg_exp

        db.session.commit()
        skipped += 1

    print(f"\n=== Target import complete ===")
    print(f"  Created: {created}, Enriched: {enriched}, Processed: {skipped}")
    return created, enriched


if __name__ == '__main__':
    with app.app_context():
        import_target_rows()
