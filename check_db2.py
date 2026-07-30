import pymysql
conn = pymysql.connect(host='localhost', user='root', database='contract_mgmt')
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM purchase_orders")
print(f'Total POs: {cur.fetchone()[0]}')
cur.execute("SELECT MAX(serial_number) FROM purchase_orders")
print(f'Max SN: {cur.fetchone()[0]}')
cur.execute("SELECT currency, COUNT(*) FROM purchase_orders WHERE serial_number >= 1725 GROUP BY currency ORDER BY COUNT(*) DESC")
print(f'Currency dist: {cur.fetchall()}')
cur.execute("""
    SELECT bs.name, COUNT(*) 
    FROM purchase_orders po 
    LEFT JOIN budget_sources bs ON po.budget_source_id=bs.id 
    WHERE po.serial_number >= 1725 
    GROUP BY bs.name 
    ORDER BY COUNT(*) DESC
""")
print(f'Budget sources: {cur.fetchall()}')
cur.execute("SELECT COUNT(*), serial_number FROM purchase_orders WHERE po_number LIKE '%7234%' GROUP BY serial_number")
print(f'7234 match: {cur.fetchall()}')
cur.execute("SELECT COUNT(*) FROM purchase_orders WHERE serial_number >= 1725 AND budget_source_id IS NULL")
print(f'New POs with NULL budget source: {cur.fetchone()[0]}')
conn.close()
