"""
Import new PO data from TSV file (June-July 2026).
Auto-assigns serial numbers starting from current max + 1.
Skips existing PO numbers.
Usage: python import_new_data.py [tsv_file]
"""
import csv, os, sys, io
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, Supplier, LocalAgent, BudgetSource, PurchaseOrder, LineItem, PerformanceGuarantee, LetterOfCredit, Shipment, BIOfficer, ShipmentOfficer, POStatus, parse_date, parse_float, budget_year

BUDGET_MAP = {
    'RDF': 'RDF', 'SDG': 'SDG', 'GF': 'GF',
    'SDG-MH': 'SDG', 'SDG-LAB': 'SDG', 'SDG-FH': 'SDG',
    'SDG-MAL': 'SDG', 'SDG-NUT': 'SDG', 'SDG-HIV': 'SDG',
    'SDG-ME': 'SDG',
    'GF-HIV': 'GF', 'GF-CBHIV': 'GF', 'GF-NFM': 'GF', 'GF-NFM2': 'GF',
    'MOH-HIV': 'SDG', 'MOH-RMNCH': 'SDG', 'MOH-RMNCH-CMPT': 'SDG',
    'MOH-MAL': 'SDG', 'MOH-NCD': 'SDG', 'MOH-ME': 'SDG', 'MOH-TB': 'SDG',
    'MOF-NUT': 'Treasury', 'MOF-MH': 'Treasury', 'MOF-OTH': 'Treasury',
    'MOF-ME': 'Treasury',
    'MOH TB-TREASURE': 'Treasury',
    '-': None,
    '': None,
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

def import_tsv(filepath):
    print(f"Reading: {filepath}")
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        raw = f.read()
    reader = csv.reader(io.StringIO(raw), delimiter='\t')
    rows = list(reader)
    print(f"Loaded {len(rows)} rows")

    max_sn = db.session.query(db.func.max(PurchaseOrder.serial_number)).scalar() or 0
    next_sn = max_sn + 1
    print(f"Starting serial number: {next_sn}")

    existing_pnos = set()
    for p in db.session.query(PurchaseOrder.po_number).filter(
            PurchaseOrder.po_number != None, PurchaseOrder.po_number != ''
    ).all():
        existing_pnos.add(p[0])
    print(f"Existing POs in DB: {len(existing_pnos)}")

    po_count = 0
    item_count = 0
    current_po = None

    for row in rows:
        if not row or not any(cell.strip() for cell in row):
            continue

        po_number = row[3].strip().replace('\n', ' / ') if len(row) > 3 else ''

        if not po_number:
            if current_po and len(row) > 7 and row[7].strip():
                desc = row[7].strip()
                unit = row[8].strip() if len(row) > 8 else ''
                qty = parse_float(row[9]) if len(row) > 9 else None
                unit_price = parse_float(row[10]) if len(row) > 10 else None
                total_price = parse_float(row[11]) if len(row) > 11 else None
                if desc:
                    li = LineItem(po_id=current_po.id, description=desc,
                                  unit=unit, quantity=qty, unit_price=unit_price,
                                  total_price=total_price)
                    db.session.add(li)
                    item_count += 1
            continue

        if po_number in existing_pnos:
            print(f"  Skip existing: {po_number}")
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

        canonical_budget = BUDGET_MAP.get(budget_name, budget_name)
        budget_source = get_or_create(BudgetSource, name=canonical_budget) if canonical_budget else None

        supplier = None
        if supplier_name:
            existing = Supplier.query.filter_by(name=supplier_name).first()
            if existing:
                supplier = existing
            else:
                supplier = Supplier(name=supplier_name, country=country)
                db.session.add(supplier)
                db.session.flush()

        local_agent = get_or_create(LocalAgent, name=local_agent_name) if local_agent_name else None

        bi_officer_name = row[28].strip() if len(row) > 28 and row[28].strip() else ''
        bi_officer = get_or_create(BIOfficer, name=bi_officer_name) if bi_officer_name else None

        shipment_officer_name = row[33].strip() if len(row) > 33 and row[33].strip() else ''
        shipment_officer_obj = get_or_create(ShipmentOfficer, name=shipment_officer_name) if shipment_officer_name else None

        status_name = row[25].strip() if len(row) > 25 and row[25].strip() else ''
        po_status = get_or_create(POStatus, name=status_name) if status_name else None

        try:
            po = PurchaseOrder(
                serial_number=next_sn,
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
                biofficer_id=bi_officer.id if bi_officer else None,
                shipment_officer_id=shipment_officer_obj.id if shipment_officer_obj else None,
                status_id=po_status.id if po_status else None,
            )
            db.session.add(po)
            db.session.flush()
            po_count += 1
            current_po = po
            next_sn += 1
            existing_pnos.add(po_number)
        except Exception as e:
            print(f"  ERROR {po_number}: {e}")
            continue

        if desc:
            li = LineItem(po_id=po.id, description=desc, unit=unit,
                          quantity=qty, unit_price=unit_price, total_price=total_price)
            db.session.add(li)
            item_count += 1

        pg_requested = parse_date(row[17]) if len(row) > 17 else None
        pg_received = parse_date(row[18]) if len(row) > 18 else None
        pg_confirmed = parse_date(row[19]) if len(row) > 19 else None
        bank_name = row[20].strip() if len(row) > 20 else ''
        pg_ref = row[21].strip() if len(row) > 21 else ''
        pg_expiry = parse_date(row[22]) if len(row) > 22 else None
        status_date = parse_date(row[26]) if len(row) > 26 else None
        pg_receiver = row[27].strip() if len(row) > 27 else ''

        if pg_expiry or pg_requested or pg_received or pg_confirmed:
            pg = PerformanceGuarantee(
                po_id=po.id, requested_date=pg_requested,
                received_date=pg_received, confirmed_date=pg_confirmed,
                expiry_date=pg_expiry, bank_name=bank_name,
                pg_reference=pg_ref, status_date=status_date,
                pg_receiver_name=pg_receiver, bi_officer=bi_officer_name,
            )
            db.session.add(pg)

        lc_status = row[29].strip() if len(row) > 29 else ''
        if lc_status:
            lc_opened = parse_date(row[30]) if len(row) > 30 else None
            lc_expiry = parse_date(row[31]) if len(row) > 31 else None
            lc_age = parse_float(row[32]) if len(row) > 32 else None
            db.session.add(LetterOfCredit(po_id=po.id, opening_status=lc_status,
                                          opened_date=lc_opened, expiry_date=lc_expiry,
                                          age_days=lc_age))

        shipment_status = row[34].strip() if len(row) > 34 else ''
        order_closure = row[35].strip() if len(row) > 35 else ''
        if shipment_officer_name or shipment_status:
            db.session.add(Shipment(po_id=po.id, shipment_officer=shipment_officer_name,
                                    shipment_status=shipment_status, order_closure=order_closure))

        if po_count % 50 == 0:
            db.session.commit()
            print(f"  ... {po_count} POs, {item_count} items")

    db.session.commit()
    print(f"\n=== Import complete ===")
    print(f"  POs: {po_count}, Line Items: {item_count}")
    return po_count, item_count

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), 'new_data.tsv')
    with app.app_context():
        import_tsv(filepath)
