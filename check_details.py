import pymysql
conn = pymysql.connect(host='localhost', user='root', database='contract_mgmt')
cur = conn.cursor()

# Check empty currency POs - are they all related to certain suppliers?
cur.execute("""
    SELECT serial_number, po_number, total_po_amount, 
           (SELECT name FROM suppliers WHERE id=po.supplier_id) as supplier_name,
           (SELECT name FROM budget_sources WHERE id=po.budget_source_id) as budget_name
    FROM purchase_orders po 
    WHERE serial_number >= 1725 AND (currency IS NULL OR currency = '')
    ORDER BY serial_number
""")
rows = cur.fetchall()
print(f'Empty currency POs: {len(rows)}')
for r in rows:
    print(f'  SN={r[0]}, PO={r[1]}, amt={r[2]}, supp={r[3]}, budget={r[4]}')

# Check "BR" currency
cur.execute("""
    SELECT serial_number, po_number, total_po_amount, 
           (SELECT name FROM budget_sources WHERE id=po.budget_source_id),
           currency
    FROM purchase_orders po
    WHERE serial_number >= 1725 AND currency = 'BR'
""")
print(f'\nBR currency POs:')
for r in cur.fetchall():
    print(f'  SN={r[0]}, PO={r[1]}, amt={r[2]}, budget={r[3]}, curr={r[4]}')

# Check budget sources with newlines
cur.execute("""
    SELECT name, id FROM budget_sources WHERE name LIKE '%\n%'
""")
print(f'\nBudget sources with newlines:')
for r in cur.fetchall():
    print(f'  ID={r[1]}, name={repr(r[0])}')

# Check how many POs reference those weird budget sources
cur.execute("""
    SELECT po.serial_number, po.po_number, bs.name
    FROM purchase_orders po
    JOIN budget_sources bs ON po.budget_source_id = bs.id
    WHERE bs.name LIKE '%\n%'
""")
print(f'\nPOs with weird budget sources:')
for r in cur.fetchall():
    print(f'  SN={r[0]}, PO={r[1]}, bs={repr(r[2])}')

conn.close()
