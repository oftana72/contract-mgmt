"""
Import system_contracts.tsv data with full columns (PG, LC, Shipment details).
Updates existing POs with additional data if they already exist.
"""
import csv, os, sys, io
sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, Supplier, LocalAgent, BudgetSource, PurchaseOrder, LineItem, PerformanceGuarantee, LetterOfCredit, Shipment, BIOfficer, ShipmentOfficer, POStatus, parse_date, parse_float, budget_year

BUDGET_MAP = {
    'RDF': 'RDF', 'SDG': 'SDG', 'SDG-MH': 'SDG', 'SDG-LAB': 'SDG', 'SDG-FH': 'SDG', 'SDG-MAL': 'SDG', 'SDG-HIV': 'SDG', 'SDG-NUT': 'SDG', 'SDG-ME': 'SDG',
    'GF': 'GF', 'GF-HIV': 'GF', 'GF-CBHIV': 'GF', 'GF-NFM2': 'GF',
    'MOH TB-TREASURE': 'Treasury', 'MOH-ME': 'Treasury', 'MOH-MAL': 'Treasury', 'MOH-TB': 'Treasury', 'MOH-NCD': 'Treasury', 'MOH-MH': 'Treasury', 'MOH-HIV': 'Treasury', 'MOH RMNCH-CMPT': 'Treasury', 'MOH-RMNCH': 'Treasury',
    'MOF-NUT': 'Treasury', 'MOF-OTH': 'Treasury', 'MOF-MH': 'Treasury',
    'Global Fund': 'GF', 'MOH': 'SDG',
    '-': None, '': None,
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

def import_system_contracts(filepath):
    print(f"Reading: {filepath}")
    with open(filepath, 'r', encoding='utf-8') as f:
        raw = f.read()
    reader = csv.reader(io.StringIO(raw), delimiter='\t')
    rows = list(reader)
    print(f"Loaded {len(rows)} rows")

    max_sn = db.session.query(db.func.max(PurchaseOrder.serial_number)).scalar() or 0
    next_sn = max_sn + 1

    existing_pnos = set()
    for p in db.session.query(PurchaseOrder.po_number).filter(
            PurchaseOrder.po_number != None, PurchaseOrder.po_number != ''
    ).all():
        existing_pnos.add(p[0])
    print(f"Existing POs in DB: {len(existing_pnos)}, starting SN: {next_sn}")

    po_count = 0
    item_count = 0
    update_count = 0
    current_po = None

    for row in rows:
        if not row or not any(cell.strip() for cell in row):
            continue

        po_number = row[3].strip() if len(row) > 3 else ''
        items = row[7].strip() if len(row) > 7 else ''

        # Skip header
        if po_number == 'PO Number' or po_number == 'PO No':
            continue

        # Continuation row (no PO number, has items)
        if not po_number:
            if current_po and items:
                unit = row[8].strip() if len(row) > 8 else ''
                qty = parse_float(row[9]) if len(row) > 9 else None
                uprice = parse_float(row[10]) if len(row) > 10 else None
                tprice = parse_float(row[11]) if len(row) > 11 else None
                li = LineItem(po_id=current_po.id, description=items, unit=unit,
                              quantity=qty, unit_price=uprice, total_price=tprice)
                db.session.add(li)
                item_count += 1
            continue

        if po_number in existing_pnos:
            po = PurchaseOrder.query.filter_by(po_number=po_number).first()
            if po:
                current_po = po
                if items:
                    unit = row[8].strip() if len(row) > 8 else ''
                    qty = parse_float(row[9]) if len(row) > 9 else None
                    uprice = parse_float(row[10]) if len(row) > 10 else None
                    tprice = parse_float(row[11]) if len(row) > 11 else None
                    li = LineItem(po_id=po.id, description=items, unit=unit,
                                  quantity=qty, unit_price=uprice, total_price=tprice)
                    db.session.add(li)
                    item_count += 1
                # Update additional data
                updated = False
                if len(row) > 15 and row[15].strip() and not po.mode_of_shipment:
                    po.mode_of_shipment = row[15].strip()
                    updated = True
                if len(row) > 22 and row[22].strip():
                    pg_expiry = parse_date(row[22])
                    if pg_expiry and not po.pg_expiry_date:
                        po.pg_expiry_date = pg_expiry
                        updated = True
                if len(row) > 28 and row[28].strip() and not po.biofficer_id:
                    bi_name = row[28].strip()
                    bi = BIOfficer.query.filter_by(name=bi_name).first()
                    if bi:
                        po.biofficer_id = bi.id
                        updated = True
                if updated:
                    db.session.flush()
                    update_count += 1
            continue

        # New PO
        received_date = parse_date(row[1]) if len(row) > 1 else None
        tender_ref = row[2].strip() if len(row) > 2 else ''
        supplier_name = ' '.join(row[4].strip().replace('\n', ' ').split()) if len(row) > 4 else ''
        country = ' '.join(row[5].strip().replace('\n', ' ').split()) if len(row) > 5 else ''
        local_agent_name = ' '.join(row[6].strip().replace('\n', ' ').split()) if len(row) > 6 else ''

        total_po_amount = parse_float(row[12]) if len(row) > 12 else None
        currency = row[13].strip() if len(row) > 13 and row[13].strip() else ''
        currency_aliases = {'USD': 'USD', 'ETB': 'ETB', 'BIRR': 'ETB', 'EUR': 'EUR', '': ''}
        if currency in currency_aliases:
            currency = currency_aliases[currency]

        budget_name = row[14].strip() if len(row) > 14 else ''
        budget_name_clean = ' '.join(budget_name.replace('\n', ' ').split())
        canonical = BUDGET_MAP.get(budget_name_clean, budget_name_clean)
        budget_source = get_or_create(BudgetSource, name=canonical) if canonical else None

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

        bi_officer_name = row[28].strip() if len(row) > 28 else ''
        bi_officer = get_or_create(BIOfficer, name=bi_officer_name) if bi_officer_name else None

        shipment_officer_name = row[33].strip() if len(row) > 33 else ''
        shipment_officer_obj = get_or_create(ShipmentOfficer, name=shipment_officer_name) if shipment_officer_name else None

        status_name = row[25].strip() if len(row) > 25 else ''
        po_status = get_or_create(POStatus, name=status_name) if status_name else None

        mode_of_shipment = row[15].strip() if len(row) > 15 else ''
        po_transferred = parse_date(row[16]) if len(row) > 16 else None
        pg_expiry = parse_date(row[22]) if len(row) > 22 else None
        status_date = parse_date(row[26]) if len(row) > 26 else None
        remark = row[35].strip() if len(row) > 35 else ''

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
                po_transferred_date=po_transferred,
                mode_of_shipment=mode_of_shipment,
                biofficer_id=bi_officer.id if bi_officer else None,
                shipment_officer_id=shipment_officer_obj.id if shipment_officer_obj else None,
                status_id=po_status.id if po_status else None,
                remark=remark,
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

        if items:
            unit = row[8].strip() if len(row) > 8 else ''
            qty = parse_float(row[9]) if len(row) > 9 else None
            uprice = parse_float(row[10]) if len(row) > 10 else None
            tprice = parse_float(row[11]) if len(row) > 11 else None
            li = LineItem(po_id=po.id, description=items, unit=unit,
                          quantity=qty, unit_price=uprice, total_price=tprice)
            db.session.add(li)
            item_count += 1

        # PG
        pg_requested = parse_date(row[17]) if len(row) > 17 and row[17].strip() else None
        pg_received = parse_date(row[18]) if len(row) > 18 and row[18].strip() else None
        pg_confirmed = parse_date(row[19]) if len(row) > 19 and row[19].strip() else None
        bank_name = row[20].strip() if len(row) > 20 and row[20].strip() else None
        pg_reference = row[21].strip() if len(row) > 21 and row[21].strip() else None
        pg_receiver = row[27].strip() if len(row) > 27 and row[27].strip() else None

        if pg_expiry or pg_reference or bi_officer_name:
            db.session.add(PerformanceGuarantee(
                po_id=po.id, expiry_date=pg_expiry,
                request_date=pg_requested, received_date=pg_received,
                confirmed_date=pg_confirmed,
                bank_name=bank_name, pg_reference=pg_reference,
                bi_officer=bi_officer_name,
                pg_receiver=pg_receiver,
                status_date=status_date,
            ))

        # LC
        lc_status = row[29].strip() if len(row) > 29 else ''
        if lc_status:
            lc_opened = parse_date(row[30]) if len(row) > 30 else None
            lc_expiry = parse_date(row[31]) if len(row) > 31 else None
            lc_age = parse_float(row[32]) if len(row) > 32 else None
            db.session.add(LetterOfCredit(
                po_id=po.id, opening_status=lc_status,
                opened_date=lc_opened, expiry_date=lc_expiry,
                age_days=lc_age,
            ))

        # Shipment
        shipment_status = row[34].strip() if len(row) > 34 else ''
        order_closure = row[35].strip() if len(row) > 35 else ''
        if shipment_officer_name or shipment_status:
            db.session.add(Shipment(
                po_id=po.id, shipment_officer=shipment_officer_name,
                shipment_status=shipment_status, order_closure=order_closure,
            ))

        if po_count % 25 == 0:
            db.session.commit()

    db.session.commit()
    print(f"\n=== Import complete ===")
    print(f"  New POs: {po_count}, Items: {item_count}, Updated: {update_count}")
    return po_count, item_count

if __name__ == '__main__':
    with app.app_context():
        import_system_contracts(os.path.join(os.path.dirname(__file__), 'system_contracts.tsv'))
