"""
Import data from Google Sheet tab gid=2126924452 (second data tab).
Column layout (0-indexed):
  0 S.N
  1 Received date
  2 Tender reference
  3 PO No
  4 Supplier
  5 Country
  6 Local agent
  7 Description
  8 Unit
  9 Quantity
  10 Unit Price
  11 Total Price
  12 Total PO Amount
  13 Currency
  14 Budget Source
  15 PG Expiry Date
  16 File Transferred to BI date
  17 BI Officer
  18 LC Opening status
  19 LC Opened Date
  20 LC Expiry Date
  21 LC Age Days
  22 Shipment Officer
  23 Shipment Status
  24 Current LC Status (skip)
  25 Bill/Shipped date (skip)
  26 Supply Status (skip)
  27 Port Arrival Date (skip)
  28 Clearance to WH Date (skip)
  29 Port Dwell Time (skip)
  30 Order Closure
  31 Remaining Days for PG (skip)
  32 Status (POStatus)
  33 Status Date
  34 Remark
"""
import csv, os, sys, io, urllib.request
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, Supplier, LocalAgent, BudgetSource, PurchaseOrder, LineItem, PerformanceGuarantee, LetterOfCredit, Shipment, BIOfficer, ShipmentOfficer, POStatus, parse_date, parse_float, budget_year

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=2126924452'

BUDGET_MAP = {
    'RDF': 'RDF', 'SDG': 'SDG', 'Global Fund': 'GF', 'MOH': 'SDG',
    'Ministry of Finance': 'Treasury',
    'GF-AHPCO/NFMIII/ARV/OI': 'GF',
    'FW/PIMA CD4/Analyzer/': None,
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

def import_sheet(url=SHEET_URL):
    print(f"Downloading: {url}")
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=120) as resp:
        raw = resp.read().decode('utf-8')
    reader = csv.reader(io.StringIO(raw))
    rows = list(reader)
    print(f"Loaded {len(rows)} rows")

    # Row 0-1: title/team headers; Row 2: column headers; Row 3+: data
    header_idx = 2
    data_start = 3
    print(f"Using header at row {header_idx}, data starts at {data_start}")
    # Verify header
    if not rows[header_idx] or rows[header_idx][1].strip() != 'Recevied date from TMD':
        print(f"WARNING: Header row check failed, using anyway")

    max_sn = db.session.query(db.func.max(PurchaseOrder.serial_number)).scalar() or 0
    next_sn = max_sn + 1

    existing_pnos = set()
    for p in db.session.query(PurchaseOrder.po_number).filter(
            PurchaseOrder.po_number != None, PurchaseOrder.po_number != ''
    ).all():
        existing_pnos.add(p[0])
    print(f"Existing POs: {len(existing_pnos)}, starting SN: {next_sn}")

    po_count = 0
    item_count = 0
    current_po = None

    for row in rows[data_start:]:
        if not row or not any(cell.strip() for cell in row):
            continue

        sn_str = row[0].strip() if len(row) > 0 else ''

        # Continuation row (no S.N, no PO number, has description)
        if not sn_str:
            po_number = ''
        else:
            po_number = row[3].strip().replace('\n', ' / ') if len(row) > 3 else ''

        if not sn_str and not po_number and current_po:
            if len(row) > 7 and row[7].strip():
                desc = row[7].strip()
                unit = row[8].strip() if len(row) > 8 else ''
                qty = parse_float(row[9]) if len(row) > 9 else None
                uprice = parse_float(row[10]) if len(row) > 10 else None
                tprice = parse_float(row[11]) if len(row) > 11 else None
                li = LineItem(po_id=current_po.id, description=desc, unit=unit,
                              quantity=qty, unit_price=uprice, total_price=tprice)
                db.session.add(li)
                item_count += 1
            continue

        if not sn_str or not po_number:
            continue

        # Skip rows with "DESCRIPTION" text (freight description rows)
        if len(row) > 7 and row[7].strip().startswith('DESCRIPTION'):
            continue

        # Try to parse SN
        try:
            sn_int = int(float(sn_str.replace(',', '')))
        except (ValueError, AttributeError):
            continue

        if po_number in existing_pnos:
            print(f"  Skip existing: {po_number}")
            continue

        received_date = parse_date(row[1]) if len(row) > 1 else None
        tender_ref = row[2].strip().replace('\n', ' / ') if len(row) > 2 else ''
        supplier_name = ' '.join(row[4].strip().replace('\n', ' ').replace('\r', '').split()) if len(row) > 4 else ''
        country = ' '.join(row[5].strip().replace('\n', ' ').replace('\r', '').split()) if len(row) > 5 else ''
        local_agent_name = ' '.join(row[6].strip().replace('\n', ' ').replace('\r', '').split()) if len(row) > 6 else ''

        desc = row[7].strip() if len(row) > 7 and row[7].strip() else ''
        unit = row[8].strip() if len(row) > 8 else ''
        qty = parse_float(row[9]) if len(row) > 9 else None
        uprice = parse_float(row[10]) if len(row) > 10 else None
        tprice = parse_float(row[11]) if len(row) > 11 else None

        total_po_amount_raw = row[12].strip() if len(row) > 12 else ''
        currency_raw = row[13].strip() if len(row) > 13 else ''

        # Handle combined amount+currency like "USD8074.89", "BR1,247,850.00", "761625 birr"
        total_po_amount = None
        currency = ''
        if total_po_amount_raw:
            total_po_amount = parse_float(total_po_amount_raw)
            if total_po_amount is None:
                import re
                m = re.match(r'([A-Za-z]+)([\d,.-]+)', total_po_amount_raw.replace(' ', ''))
                if m:
                    currency = m.group(1)
                    total_po_amount = parse_float(m.group(2))
                else:
                    m = re.match(r'([\d,.-]+)\s*([A-Za-z]*)', total_po_amount_raw)
                    if m:
                        total_po_amount = parse_float(m.group(1))
                        if m.group(2).lower() in ('birr', 'etb'):
                            currency = 'ETB'

        # Normalize extracted currency prefixes
        currency_prefix_map = {'BR': 'ETB', 'BIRR': 'ETB', 'USD': 'USD', 'EUR': 'EUR'}
        if currency and currency in currency_prefix_map:
            currency = currency_prefix_map[currency]

        # Currency column
        currency_aliases = {'USD': 'USD', 'BIRR': 'ETB', 'ETB': 'ETB', '': ''}
        if not currency and currency_raw in currency_aliases:
            currency = currency_aliases[currency_raw]
        elif not currency:
            currency = currency_raw

        budget_name = row[14].strip() if len(row) > 14 else ''
        budget_name_clean = ' '.join(budget_name.replace('\n', ' ').replace('\r', '').split())
        canonical = BUDGET_MAP.get(budget_name_clean, budget_name_clean)
        budget_source = get_or_create(BudgetSource, name=canonical) if canonical else None

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

        bi_officer_name = row[17].strip() if len(row) > 17 and row[17].strip() else ''
        bi_officer = get_or_create(BIOfficer, name=bi_officer_name) if bi_officer_name else None

        shipment_officer_name = row[22].strip() if len(row) > 22 and row[22].strip() else ''
        shipment_officer_obj = get_or_create(ShipmentOfficer, name=shipment_officer_name) if shipment_officer_name else None

        status_name = row[32].strip() if len(row) > 32 and row[32].strip() else ''
        po_status = get_or_create(POStatus, name=status_name) if status_name else None

        pg_expiry = parse_date(row[15]) if len(row) > 15 else None
        po_transferred = parse_date(row[16]) if len(row) > 16 else None
        status_date = parse_date(row[33]) if len(row) > 33 else None
        remark = row[34].strip() if len(row) > 34 else ''

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

        if desc and unit:
            li = LineItem(po_id=po.id, description=desc, unit=unit,
                          quantity=qty, unit_price=uprice, total_price=tprice)
            db.session.add(li)
            item_count += 1

        # PG
        if pg_expiry or bi_officer_name:
            pg = PerformanceGuarantee(
                po_id=po.id, expiry_date=pg_expiry,
                bi_officer=bi_officer_name, status_date=status_date,
            )
            db.session.add(pg)

        # LC
        lc_status = row[18].strip() if len(row) > 18 else ''
        if lc_status:
            lc_opened = parse_date(row[19]) if len(row) > 19 else None
            lc_expiry = parse_date(row[20]) if len(row) > 20 else None
            lc_age = parse_float(row[21]) if len(row) > 21 else None
            db.session.add(LetterOfCredit(po_id=po.id, opening_status=lc_status,
                                          opened_date=lc_opened, expiry_date=lc_expiry,
                                          age_days=lc_age))

        # Shipment
        shipment_status = row[23].strip() if len(row) > 23 else ''
        order_closure = row[30].strip() if len(row) > 30 else ''
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
    with app.app_context():
        import_sheet()
