import pymysql
conn = pymysql.connect(host='localhost', user='root', database='contract_mgmt')
cur = conn.cursor()
# Check POs with NULL budget source
cur.execute("""
    SELECT serial_number, po_number, budget_source_id, currency, total_po_amount
    FROM purchase_orders 
    WHERE serial_number >= 1725 AND budget_source_id IS NULL 
    LIMIT 10
""")
print(f'NULL budget source POs:')
for r in cur.fetchall():
    print(f'  SN={r[0]}, PO={r[1]}, curr={r[3]}, amt={r[4]}')
    
# Check POs with BR or EUR currency
cur.execute("""
    SELECT serial_number, po_number, currency, total_po_amount, supplier_name_raw
    FROM purchase_orders 
    WHERE serial_number >= 1725 AND currency IN ('BR', 'EUR')
""")
print(f'\nBR/EUR currency POs:')
for r in cur.fetchall():
    print(f'  SN={r[0]}, PO={r[1]}, curr={r[2]}, amt={r[3]}, supp={r[4] if r[4] else ""}')

# Check POs with empty currency
cur.execute("""
    SELECT serial_number, po_number, currency, total_po_amount, supplier_name_raw
    FROM purchase_orders 
    WHERE serial_number >= 1725 AND (currency IS NULL OR currency = '')
    LIMIT 10
""")
print(f'\nEmpty currency POs:')
for r in cur.fetchall():
    print(f'  SN={r[0]}, PO={r[1]}, curr={r[2]!r}, amt={r[3]}, supp={r[4] if r[4] else ""}')

# Check budget sources with newlines
cur.execute("""
    SELECT name, COUNT(*) 
    FROM budget_sources 
    WHERE name LIKE '%\n%'
    GROUP BY name
""")
print(f'\nBudget sources with newlines:')
for r in cur.fetchall():
    print(f'  {repr(r[0])}: {r[1]}')

conn.close()
