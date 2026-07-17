"""
Import data from the exported CSV into the contract management database.
Run: python import_data.py
"""
import csv
import os
import sys
from datetime import datetime, timedelta, date
from dateutil import parser as dateparser

sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, Supplier, LocalAgent, BudgetSource, PurchaseOrder, LineItem, PerformanceGuarantee, LetterOfCredit, Shipment, User, parse_date, parse_float

CSV_PATH = os.path.join(os.path.dirname(__file__), 'exported_data.csv')

def load_csv_rows():
    if not os.path.exists(CSV_PATH):
        print(f"ERROR: CSV file not found at {CSV_PATH}")
        print("Please export the Google Sheet as CSV and save it as 'exported_data.csv' in this directory.")
        sys.exit(1)

    with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
    return rows

def get_or_create(model, name_field, name):
    if not name or str(name).strip() == '':
        return None
    name = str(name).strip()
    existing = model.query.filter_by(**{name_field: name}).first()
    if existing:
        return existing
    obj = model(**{name_field: name})
    db.session.add(obj)
    db.session.flush()
    return obj

def process_rows(rows):
    """Parse the CSV rows and import data."""
    # Find header row (row index 2 = third row has S.N)
    data_start = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == '1':
            data_start = i
            break

    if data_start is None:
        print("ERROR: Could not find data start row")
        return

    print(f"Data starts at row {data_start + 1}")

    # Track current PO being built (for multi-row POs)
    current_po = None
    current_sn = None
    po_count = 0
    item_count = 0
    skip_count = 0

    i = data_start
    while i < len(rows):
        row = rows[i]
        if not row or not row[0].strip():
            # Continuation row (additional line items for current PO)
            if current_po and len(row) > 7:
                desc = row[7].strip() if len(row) > 7 and row[7].strip() else ''
                unit = row[8].strip() if len(row) > 8 else ''
                qty = parse_float(row[9]) if len(row) > 9 else None
                unit_price = parse_float(row[10]) if len(row) > 10 else None
                total_price = parse_float(row[11]) if len(row) > 11 else None

                if desc:
                    li = LineItem(
                        po_id=current_po.id,
                        description=desc,
                        unit=unit,
                        quantity=qty,
                        unit_price=unit_price,
                        total_price=total_price
                    )
                    db.session.add(li)
                    item_count += 1
            i += 1
            continue

        sn = row[0].strip()

        # Check if this is a numeric serial number
        try:
            sn_int = int(float(sn.replace(',', '')))
        except (ValueError, AttributeError):
            i += 1
            continue

        # If we built a previous PO, check if its PO number matches the continuation
        # Reset
        current_sn = sn_int

        received_date = parse_date(row[1]) if len(row) > 1 else None
        tender_ref = row[2].strip() if len(row) > 2 else ''
        po_number = row[3].strip() if len(row) > 3 else ''
        supplier_name = row[4].strip() if len(row) > 4 else ''
        country = row[5].strip() if len(row) > 5 else ''
        local_agent_name = row[6].strip() if len(row) > 6 else ''

        # First line item
        desc = row[7].strip() if len(row) > 7 and row[7].strip() else ''
        unit = row[8].strip() if len(row) > 8 else ''
        qty = parse_float(row[9]) if len(row) > 9 else None
        unit_price = parse_float(row[10]) if len(row) > 10 else None
        total_price = parse_float(row[11]) if len(row) > 11 else None
        total_po_amount = parse_float(row[12]) if len(row) > 12 else None
        currency = row[13].strip() if len(row) > 13 else ''
        budget_name = row[14].strip() if len(row) > 14 else ''
        mode_shipment = row[15].strip() if len(row) > 15 else ''
        po_transferred = parse_date(row[16]) if len(row) > 16 else None

        # PG fields
        pg_requested = parse_date(row[17]) if len(row) > 17 else None
        pg_received = parse_date(row[18]) if len(row) > 18 else None
        pg_confirmed = parse_date(row[19]) if len(row) > 19 else None
        bank_name = row[20].strip() if len(row) > 20 else ''
        pg_ref = row[21].strip() if len(row) > 21 else ''
        pg_expiry = parse_date(row[22]) if len(row) > 22 else None
        remaining_days = parse_float(row[23]) if len(row) > 23 else None
        submit_pg = row[24].strip() if len(row) > 24 else ''
        pg_status = row[25].strip() if len(row) > 25 else ''
        status_date = parse_date(row[26]) if len(row) > 26 else None
        pg_receiver = row[27].strip() if len(row) > 27 else ''
        bi_officer = row[28].strip() if len(row) > 28 else ''

        # LC fields
        lc_status = row[29].strip() if len(row) > 29 else ''
        lc_opened = parse_date(row[30]) if len(row) > 30 else None
        lc_expiry = parse_date(row[31]) if len(row) > 31 else None
        lc_age = parse_float(row[32]) if len(row) > 32 else None

        # Shipment fields
        shipment_officer = row[33].strip() if len(row) > 33 else ''
        shipment_status = row[34].strip() if len(row) > 34 else ''
        order_closure = row[35].strip() if len(row) > 35 else ''

        # Remark
        remark = ''
        if len(row) > 36 and row[36].strip():
            remark = row[36].strip()
        if not remark and len(row) > 37 and row[37].strip():
            remark = row[37].strip()

        # Get or create related entities
        supplier = None
        if supplier_name:
            existing = Supplier.query.filter_by(name=supplier_name).first()
            if existing:
                supplier = existing
            else:
                supplier = Supplier(name=supplier_name, country=country)
                db.session.add(supplier)
                db.session.flush()

        local_agent = get_or_create(LocalAgent, 'name', local_agent_name) if local_agent_name else None
        budget_source = get_or_create(BudgetSource, 'name', budget_name) if budget_name else None

        # Create PO
        try:
            po = PurchaseOrder(
                serial_number=sn_int,
                received_date=received_date,
                tender_reference=tender_ref,
                po_number=po_number,
                supplier_id=supplier.id if supplier else None,
                supplier_name_raw=supplier_name if not supplier else None,
                country_raw=country if not supplier else None,
                local_agent_id=local_agent.id if local_agent else None,
                local_agent_raw=local_agent_name if not local_agent else None,
                total_po_amount=total_po_amount,
                currency=currency,
                budget_source_id=budget_source.id if budget_source else None,
                mode_of_shipment=mode_shipment,
                po_transferred_date=po_transferred,
                remark=remark
            )
            db.session.add(po)
            db.session.flush()
            po_count += 1
            current_po = po
        except Exception as e:
            print(f"  ERROR creating PO: {e}")
            i += 1
            continue

        # Create first line item
        if desc:
            li = LineItem(
                po_id=po.id,
                description=desc,
                unit=unit,
                quantity=qty,
                unit_price=unit_price,
                total_price=total_price
            )
            db.session.add(li)
            item_count += 1

        # Create PG if any date exists
        if pg_requested or pg_received or pg_confirmed or bank_name:
            pg = PerformanceGuarantee(
                po_id=po.id,
                requested_date=pg_requested,
                received_date=pg_received,
                confirmed_date=pg_confirmed,
                bank_name=bank_name,
                pg_reference=pg_ref,
                expiry_date=pg_expiry,
                remaining_days=remaining_days if remaining_days and remaining_days != -1 else None,
                submit_pg=submit_pg,
                status=pg_status,
                status_date=status_date,
                pg_receiver_name=pg_receiver,
                bi_officer=bi_officer
            )
            db.session.add(pg)

        # Create LC if any status
        if lc_status:
            lc = LetterOfCredit(
                po_id=po.id,
                opening_status=lc_status,
                opened_date=lc_opened,
                expiry_date=lc_expiry,
                age_days=lc_age
            )
            db.session.add(lc)

        # Create Shipment
        if shipment_officer or shipment_status:
            sh = Shipment(
                po_id=po.id,
                shipment_officer=shipment_officer,
                shipment_status=shipment_status,
                order_closure=order_closure
            )
            db.session.add(sh)

        # Flush periodically
        if po_count % 50 == 0:
            db.session.commit()
            print(f"  ... committed {po_count} POs, {item_count} items")

        i += 1

    db.session.commit()
    print(f"\nImport complete!")
    print(f"  Purchase Orders: {po_count}")
    print(f"  Line Items: {item_count}")

def ensure_admin():
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', is_admin=1)
        admin.set_password('admin')
        db.session.add(admin)
        db.session.commit()

def main():
    with app.app_context():
        db.drop_all()
        db.create_all()
        ensure_admin()
        print("Database reset. Starting import...")
        rows = load_csv_rows()
        print(f"Loaded {len(rows)} rows from CSV")
        process_rows(rows)

if __name__ == '__main__':
    main()
