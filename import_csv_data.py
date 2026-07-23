"""
Import CSV data from Google Sheets exports into the contract management database.
Correctly maps the actual CSV column layout.

Usage:
    python import_csv_data.py "path/to/file.csv"

The CSV columns (from Google Sheet export) are:
  0 S.N                        -> serial_number
  1 From TMD / received date   -> received_date
  2 Tender reference number    -> tender_reference
  3 PO No                      -> po_number
  4 Supplier                   -> supplier_name_raw
  5 Country of Origin          -> country_raw
  6 Local A.                   -> local_agent_raw
  7 Description of product     -> LineItem.description
  8 Unit                       -> LineItem.unit
  9 Quantity                   -> LineItem.quantity
  10 Unit Price                -> LineItem.unit_price
  11 Total Price               -> LineItem.total_price
  12 Total PO Amount           -> total_po_amount
  13 Currency                  -> currency
  14 Budget Source             -> budget_source name
  15 PG Expiry Date            -> PerformanceGuarantee.expiry_date
  16 File Transferred to (BI)  -> po_transferred_date
  17 BI Officer                -> BIOfficer + PG.bi_officer
  18 LC Opening status         -> LetterOfCredit.opening_status
  19 LC Opened Date            -> LetterOfCredit.opened_date
  20 LC Expiry Date            -> LetterOfCredit.expiry_date
  21 Days After LC Opened      -> LetterOfCredit.age_days
  22 Shipment Officer          -> ShipmentOfficer + Shipment.shipment_officer
  23 Shipment Status           -> Shipment.shipment_status
  24 Current LC Status         -> (skipped - redundant)
  25 Bill/Shipped date         -> (skipped - not in model)
  26 Supply Status             -> (skipped - not in model)
  27 Port Arrival Date         -> (skipped - not in model)
  28 Clearance to WH Date      -> (skipped - not in model)
  29 Port Dwell Time           -> (skipped - not in model)
  30 Order Closure             -> Shipment.order_closure
  31 Remaining Days PG / note  -> remark
  32 Status                    -> POStatus name
  33 Status Date               -> PerformanceGuarantee.status_date
  34 Remark                    -> remark (appended)
"""
import csv
import os
import sys
from datetime import datetime, date
from dateutil import parser as dateparser

sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, Supplier, LocalAgent, BudgetSource, PurchaseOrder, LineItem, PerformanceGuarantee, LetterOfCredit, Shipment, BIOfficer, ShipmentOfficer, POStatus, User, parse_date, parse_float, budget_year


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


def import_csv(filepath, skip_pnos=None):
    print(f"Importing: {filepath}")
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        return 0, 0

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
    print(f"Loaded {len(rows)} rows")

    # Find header row (contains 'S.N')
    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip() == 'S.N':
            header_idx = i
            break
    if header_idx is None:
        print("ERROR: Could not find header row (S.N)")
        return 0, 0

    data_start = header_idx + 1
    total_data = len(rows) - data_start
    print(f"Header at row {header_idx}, data from row {data_start} ({total_data} data rows)")

    po_count = 0
    item_count = 0
    current_po = None

    i = data_start
    while i < len(rows):
        row = rows[i]

        # Continuation row (additional line item, no S.N)
        if not row or not row[0].strip():
            if current_po and len(row) > 7:
                desc = row[7].strip() if len(row) > 7 and row[7].strip() else ''
                unit = row[8].strip() if len(row) > 8 else ''
                qty = parse_float(row[9]) if len(row) > 9 else None
                unit_price = parse_float(row[10]) if len(row) > 10 else None
                total_price = parse_float(row[11]) if len(row) > 11 else None
                if desc:
                    li = LineItem(po_id=current_po.id, description=desc, unit=unit, quantity=qty, unit_price=unit_price, total_price=total_price)
                    db.session.add(li)
                    item_count += 1
            i += 1
            continue

        # Parse serial number
        try:
            sn_int = int(float(row[0].strip().replace(',', '')))
        except (ValueError, AttributeError):
            i += 1
            continue

        # Basic fields
        received_date = parse_date(row[1]) if len(row) > 1 else None
        tender_ref = row[2].strip() if len(row) > 2 else ''
        po_number = row[3].strip().replace('\n', ' / ') if len(row) > 3 else ''
        supplier_name = row[4].strip() if len(row) > 4 else ''
        country = row[5].strip() if len(row) > 5 else ''
        local_agent_name = row[6].strip() if len(row) > 6 else ''

        # First line item
        desc = row[7].strip() if len(row) > 7 and row[7].strip() else ''
        unit = row[8].strip() if len(row) > 8 else ''
        qty = parse_float(row[9]) if len(row) > 9 else None
        unit_price = parse_float(row[10]) if len(row) > 10 else None
        total_price = parse_float(row[11]) if len(row) > 11 else None

        # PO-level fields
        total_po_amount = parse_float(row[12]) if len(row) > 12 else None
        currency = row[13].strip() if len(row) > 13 else ''
        budget_name = row[14].strip() if len(row) > 14 else ''
        po_transferred = parse_date(row[16]) if len(row) > 16 else None

        # Remark: combine col 31 note and col 34
        remark_parts = []
        if len(row) > 31 and row[31].strip():
            remark_parts.append(row[31].strip())
        if len(row) > 34 and row[34].strip():
            remark_parts.append(row[34].strip())
        remark = ' | '.join(remark_parts)

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

        # Local agent
        local_agent = get_or_create(LocalAgent, name=local_agent_name) if local_agent_name else None
        # Budget source
        budget_source = get_or_create(BudgetSource, name=budget_name) if budget_name else None

        # BI Officer
        bi_officer_name = row[17].strip() if len(row) > 17 and row[17].strip() else ''
        bi_officer = get_or_create(BIOfficer, name=bi_officer_name) if bi_officer_name else None

        # Shipment Officer
        shipment_officer_name = row[22].strip() if len(row) > 22 and row[22].strip() else ''
        shipment_officer_obj = get_or_create(ShipmentOfficer, name=shipment_officer_name) if shipment_officer_name else None

        # PO Status
        status_name = row[32].strip() if len(row) > 32 and row[32].strip() else ''
        po_status = get_or_create(POStatus, name=status_name) if status_name else None

        # Skip if po_number already exists
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
        pg_expiry = parse_date(row[15]) if len(row) > 15 else None
        status_date = parse_date(row[33]) if len(row) > 33 else None
        if pg_expiry or bi_officer_name or status_date:
            pg = PerformanceGuarantee(
                po_id=po.id,
                expiry_date=pg_expiry,
                status_date=status_date,
                bi_officer=bi_officer_name,
            )
            db.session.add(pg)

        # LC fields
        lc_status = row[18].strip() if len(row) > 18 else ''
        if lc_status:
            lc_opened = parse_date(row[19]) if len(row) > 19 else None
            lc_expiry = parse_date(row[20]) if len(row) > 20 else None
            lc_age = parse_float(row[21]) if len(row) > 21 else None
            lc = LetterOfCredit(
                po_id=po.id,
                opening_status=lc_status,
                opened_date=lc_opened,
                expiry_date=lc_expiry,
                age_days=lc_age,
            )
            db.session.add(lc)

        # Shipment fields
        shipment_status = row[23].strip() if len(row) > 23 else ''
        order_closure = row[30].strip() if len(row) > 30 else ''
        if shipment_officer_name or shipment_status:
            sh = Shipment(
                po_id=po.id,
                shipment_officer=shipment_officer_name,
                shipment_status=shipment_status,
                order_closure=order_closure,
            )
            db.session.add(sh)

        # Periodic flush (less frequent for speed)
        if po_count % 200 == 0:
            db.session.commit()
            print(f"  ... {po_count} POs, {item_count} items committed")

        i += 1

    db.session.commit()
    print(f"\nImport complete for: {filepath}")
    print(f"  Purchase Orders: {po_count}")
    print(f"  Line Items: {item_count}")
    return po_count, item_count


def main():
    if len(sys.argv) < 2:
        print("Usage: python import_csv_data.py <csv_file> [csv_file2 ...]")
        sys.exit(1)

    with app.app_context():
        total_po = 0
        total_items = 0
        for filepath in sys.argv[1:]:
            po, items = import_csv(filepath)
            total_po += po
            total_items += items
        print(f"\n{'='*50}")
        print(f"Grand total: {total_po} POs, {total_items} line items")


if __name__ == '__main__':
    main()
