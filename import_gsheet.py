"""
Import Google Sheet data into contract management database.

Google Sheet column layout (0-indexed):
  0  S.N
  1  Received date from TMD
  2  Tender reference number
  3  PO No
  4  Supplier
  5  Country of Origin
  6  Local A.
  7  Description of the product
  8  Unit
  9  Quantity
  10 Unit Price
  11 Total price
  12 Total PO Amount
  13 Currency
  14 Budget Source
  15 Mode of Shipment
  16 PO Transferred to BIT/LT Date
  17 PG Requested Date
  18 PG received Date
  19 PG Confirmed Date
  20 Bank/Insurance Name
  21 PG Reference
  22 PG Expiry Date
  23 Remaining Days for PG Expiry
  24 Submit PG
  25 Status
  26 Status Date
  27 PG Receiver name
  28 BI Officer
  29 LC Opening Status
  30 LC Opened Date
  31 LC Expiry Date
  32 LC Age (Days)
  33 Shipment Officer
  34 Shipment Status
  35 Order Closure
"""
import csv, os, sys, io, urllib.request
from datetime import datetime, date
from dateutil import parser as dateparser

sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, Supplier, LocalAgent, BudgetSource, PurchaseOrder, LineItem, PerformanceGuarantee, LetterOfCredit, Shipment, BIOfficer, ShipmentOfficer, POStatus, parse_date, parse_float, budget_year

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=1197797932'


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


def import_gsheet(url=SHEET_URL, skip_pnos=None):
    print(f"Downloading: {url}")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode('utf-8')
    lines = raw.splitlines()
    reader = csv.reader(lines)
    rows = list(reader)
    print(f"Loaded {len(rows)} rows")

    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == 'S.N':
            header_idx = i
            break
    if header_idx is None:
        print("ERROR: Could not find header row (S.N)")
        return 0, 0

    data_start = header_idx + 1
    po_count = 0
    item_count = 0
    current_po = None

    i = data_start
    while i < len(rows):
        row = rows[i]

        # Skip empty rows
        if not row or not any(cell.strip() for cell in row):
            i += 1
            continue

        try:
            sn_int = int(float(row[0].strip().replace(',', '')))
        except (ValueError, AttributeError):
            i += 1
            continue

        # Continuation row (has S.N but no PO number)
        po_number = row[3].strip().replace('\n', ' / ') if len(row) > 3 else ''
        if not po_number:
            if current_po and len(row) > 7 and row[7].strip():
                desc = row[7].strip()
                unit = row[8].strip() if len(row) > 8 else ''
                qty = parse_float(row[9]) if len(row) > 9 else None
                unit_price = parse_float(row[10]) if len(row) > 10 else None
                total_price = parse_float(row[11]) if len(row) > 11 else None
                li = LineItem(po_id=current_po.id, description=desc, unit=unit, quantity=qty, unit_price=unit_price, total_price=total_price)
                db.session.add(li)
                item_count += 1
            i += 1
            continue

        received_date = parse_date(row[1]) if len(row) > 1 else None
        tender_ref = row[2].strip() if len(row) > 2 else ''
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
        mode_of_shipment = row[15].strip() if len(row) > 15 else ''
        po_transferred = parse_date(row[16]) if len(row) > 16 else None

        # Remark
        remark = row[35].strip() if len(row) > 35 and row[35].strip() else ''

        if not po_number:
            i += 1
            continue

        # Supplier
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
        budget_source = get_or_create(BudgetSource, name=budget_name) if budget_name else None

        # BI Officer (col 28)
        bi_officer_name = row[28].strip() if len(row) > 28 and row[28].strip() else ''
        bi_officer = get_or_create(BIOfficer, name=bi_officer_name) if bi_officer_name else None

        # Shipment Officer (col 33)
        shipment_officer_name = row[33].strip() if len(row) > 33 and row[33].strip() else ''
        shipment_officer_obj = get_or_create(ShipmentOfficer, name=shipment_officer_name) if shipment_officer_name else None

        # PO Status (col 25)
        status_name = row[25].strip() if len(row) > 25 and row[25].strip() else ''
        po_status = get_or_create(POStatus, name=status_name) if status_name else None

        if skip_pnos and po_number in skip_pnos:
            i += 1
            continue

        # Create PurchaseOrder
        try:
            po = PurchaseOrder(
                serial_number=sn_int,
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
                remark=remark,
                biofficer_id=bi_officer.id if bi_officer else None,
                shipment_officer_id=shipment_officer_obj.id if shipment_officer_obj else None,
                status_id=po_status.id if po_status else None,
            )
            db.session.add(po)
            db.session.flush()
            po_count += 1
            current_po = po
        except Exception as e:
            print(f"  ERROR creating PO (SN {sn_int}): {e}")
            i += 1
            continue

        # First line item
        if desc:
            li = LineItem(po_id=po.id, description=desc, unit=unit, quantity=qty, unit_price=unit_price, total_price=total_price)
            db.session.add(li)
            item_count += 1

        # PG fields
        pg_requested = parse_date(row[17]) if len(row) > 17 else None
        pg_received = parse_date(row[18]) if len(row) > 18 else None
        pg_confirmed = parse_date(row[19]) if len(row) > 19 else None
        bank_name = row[20].strip() if len(row) > 20 else ''
        pg_ref = row[21].strip() if len(row) > 21 else ''
        pg_expiry = parse_date(row[22]) if len(row) > 22 else None
        status_date = parse_date(row[26]) if len(row) > 26 else None
        pg_receiver = row[27].strip() if len(row) > 27 else ''

        pgs = []
        if pg_expiry or pg_requested or pg_received or pg_confirmed:
            pg = PerformanceGuarantee(
                po_id=po.id,
                requested_date=pg_requested,
                received_date=pg_received,
                confirmed_date=pg_confirmed,
                expiry_date=pg_expiry,
                bank_name=bank_name,
                pg_reference=pg_ref,
                status_date=status_date,
                pg_receiver_name=pg_receiver,
                bi_officer=bi_officer_name,
            )
            db.session.add(pg)
            pgs.append(pg)

        # LC fields (col 29-32)
        lc_status = row[29].strip() if len(row) > 29 else ''
        if lc_status:
            lc_opened = parse_date(row[30]) if len(row) > 30 else None
            lc_expiry = parse_date(row[31]) if len(row) > 31 else None
            lc_age = parse_float(row[32]) if len(row) > 32 else None
            lc = LetterOfCredit(
                po_id=po.id,
                opening_status=lc_status,
                opened_date=lc_opened,
                expiry_date=lc_expiry,
                age_days=lc_age,
            )
            db.session.add(lc)

        # Shipment fields (col 33-35)
        shipment_status = row[34].strip() if len(row) > 34 else ''
        order_closure = row[35].strip() if len(row) > 35 else ''
        if shipment_officer_name or shipment_status:
            sh = Shipment(
                po_id=po.id,
                shipment_officer=shipment_officer_name,
                shipment_status=shipment_status,
                order_closure=order_closure,
            )
            db.session.add(sh)

        if po_count % 20 == 0:
            db.session.commit()
            print(f"  ... {po_count} POs, {item_count} items committed")

        i += 1

    db.session.commit()
    print(f"\nImport complete!")
    print(f"  Purchase Orders: {po_count}")
    print(f"  Line Items: {item_count}")
    return po_count, item_count


def main():
    with app.app_context():
        existing = set()
        for p in db.session.query(PurchaseOrder.po_number).filter(PurchaseOrder.po_number != None, PurchaseOrder.po_number != '').all():
            existing.add(p[0])
        print(f"Existing PO numbers in DB: {len(existing)}")
        po, items = import_gsheet(skip_pnos=existing)
        print(f"\n{'='*50}")
        print(f"Imported: {po} POs, {items} line items")


if __name__ == '__main__':
    main()
