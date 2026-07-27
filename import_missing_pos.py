import csv, io, urllib.request, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from app import app, db, PurchaseOrder, LineItem, Supplier, BudgetSource, PerformanceGuarantee, LetterOfCredit, Shipment, parse_date, parse_float, budget_year

SHEET_URL = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=259920423'

BUDGET_MAP = {
    'RDF': 'RDF', 'SDG': 'SDG', 'SDG-MH': 'SDG', 'SDG-LAB': 'SDG', 'SDG-FH': 'SDG', 'SDG-MAL': 'SDG', 'SDG-HIV': 'SDG', 'SDG-NUT': 'SDG', 'SDG-ME': 'SDG',
    'GF': 'GF', 'GF-HIV': 'GF', 'GF-CBHIV': 'GF', 'GF-NFM2': 'GF',
    'MOH TB-TREASURE': 'Treasury', 'MOH-ME': 'Treasury', 'MOH-MAL': 'Treasury', 'MOH-TB': 'Treasury', 'MOH-NCD': 'Treasury', 'MOH-MH': 'Treasury', 'MOH-HIV': 'Treasury', 'MOH RMNCH-CMPT': 'Treasury', 'MOH-RMNCH': 'Treasury',
    'MOF-NUT': 'Treasury', 'MOF-OTH': 'Treasury', 'MOF-MH': 'Treasury',
    'RTI-NTD': 'RTI-NTD',
    'Global Fund': 'GF', 'MOH': 'SDG',
    '-': None, '': None,
}

def import_missing_pos(url=None):
    url = url or SHEET_URL
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    raw = urllib.request.urlopen(req, timeout=60).read().decode('utf-8')
    reader = csv.reader(io.StringIO(raw))

    existing = set(r[0] for r in db.session.query(PurchaseOrder.po_number).filter(PurchaseOrder.po_number.isnot(None)).all())

    rows_by_po = {}
    for i, row in enumerate(reader):
        if i < 2:
            continue
        po_number = row[3].strip() if len(row) > 3 else ''
        if not po_number or not po_number.isdigit():
            continue
        if po_number in existing:
            continue
        rows_by_po.setdefault(po_number, []).append(row)

    added = 0
    for po_number in sorted(rows_by_po):
        rows = rows_by_po[po_number]
        first = rows[0]

        supplier_name = first[4].strip() if len(first) > 4 else ''
        country = first[5].strip() if len(first) > 5 else ''
        local_agent = first[6].strip() if len(first) > 6 else ''
        received = parse_date(first[1].strip()) if len(first) > 1 and first[1].strip() else None
        tender_ref = first[2].strip() if len(first) > 2 else ''
        total_amt = parse_float(first[12].strip().replace(',', '')) if len(first) > 12 and first[12].strip() else None
        currency = first[13].strip() if len(first) > 13 else ''
        budget_raw = first[14].strip() if len(first) > 14 else ''
        budget_name = BUDGET_MAP.get(budget_raw, budget_raw)
        mode = first[15].strip() if len(first) > 15 else ''
        transferred = parse_date(first[16].strip()) if len(first) > 16 and first[16].strip() else None

        supplier = None
        if supplier_name:
            supplier = Supplier.query.filter_by(name=supplier_name).first()
            if not supplier:
                supplier = Supplier(name=supplier_name, country=country)
                db.session.add(supplier)
                db.session.flush()

        budget_source = None
        if budget_name:
            budget_source = BudgetSource.query.filter_by(name=budget_name).first()
            if not budget_source:
                budget_source = BudgetSource(name=budget_name)
                db.session.add(budget_source)
                db.session.flush()

        po = PurchaseOrder(
            po_number=po_number,
            received_date=received,
            budget_year=budget_year(received),
            tender_reference=tender_ref,
            supplier_id=supplier.id if supplier else None,
            supplier_name_raw=supplier_name if not supplier else None,
            local_agent_raw=local_agent,
            total_po_amount=total_amt,
            currency=currency,
            budget_source_id=budget_source.id if budget_source else None,
            mode_of_shipment=mode,
            po_transferred_date=transferred,
        )
        db.session.add(po)
        db.session.flush()

        # Line items
        for r in rows:
            desc = r[7].strip() if len(r) > 7 else ''
            unit = r[8].strip() if len(r) > 8 else ''
            qty = parse_float(r[9].strip().replace(',', '')) if len(r) > 9 and r[9].strip() else None
            up = parse_float(r[10].strip().replace(',', '')) if len(r) > 10 and r[10].strip() else None
            tp = parse_float(r[11].strip().replace(',', '')) if len(r) > 11 and r[11].strip() else None
            if desc:
                db.session.add(LineItem(po_id=po.id, description=desc, unit=unit,
                    quantity=qty, unit_price=up, total_price=tp))

        # PG
        pg_req = parse_date(first[17].strip()) if len(first) > 17 and first[17].strip() else None
        pg_recv = parse_date(first[18].strip()) if len(first) > 18 and first[18].strip() else None
        pg_conf = parse_date(first[19].strip()) if len(first) > 19 and first[19].strip() else None
        bank = first[20].strip() if len(first) > 20 and first[20].strip() else None
        ref = first[21].strip() if len(first) > 21 and first[21].strip() else None
        pg_exp = parse_date(first[22].strip()) if len(first) > 22 and first[22].strip() else None
        pg_status = first[25].strip() if len(first) > 25 and first[25].strip() else None
        status_date = parse_date(first[26].strip()) if len(first) > 26 and first[26].strip() else None
        receiver = first[27].strip() if len(first) > 27 and first[27].strip() else None
        bi = first[28].strip() if len(first) > 28 and first[28].strip() else None
        if any([pg_req, pg_recv, pg_conf, bank, ref, pg_exp]):
            db.session.add(PerformanceGuarantee(
                po_id=po.id, requested_date=pg_req, received_date=pg_recv,
                confirmed_date=pg_conf, bank_name=bank, pg_reference=ref,
                expiry_date=pg_exp, status=pg_status, status_date=status_date,
                pg_receiver_name=receiver, bi_officer=bi))
            if pg_exp and not po.pg_expiry_date:
                po.pg_expiry_date = pg_exp

        # LC
        lc_status = first[29].strip() if len(first) > 29 and first[29].strip() else None
        lc_opened = parse_date(first[30].strip()) if len(first) > 30 and first[30].strip() else None
        lc_expiry = parse_date(first[31].strip()) if len(first) > 31 and first[31].strip() else None
        if lc_status:
            db.session.add(LetterOfCredit(po_id=po.id, opening_status=lc_status,
                opened_date=lc_opened, expiry_date=lc_expiry))

        # Shipment
        sh_officer = first[33].strip() if len(first) > 33 and first[33].strip() else None
        sh_status = first[34].strip() if len(first) > 34 and first[34].strip() else None
        sh_closure = first[35].strip() if len(first) > 35 and first[35].strip() else None
        if sh_officer or sh_status or sh_closure:
            db.session.add(Shipment(po_id=po.id, shipment_officer=sh_officer,
                shipment_status=sh_status, order_closure=sh_closure))

        added += 1
        if added % 50 == 0:
            db.session.commit()

    db.session.commit()
    return added

if __name__ == '__main__':
    with app.app_context():
        a = import_missing_pos()
        print(f'Imported POs: {a}')
