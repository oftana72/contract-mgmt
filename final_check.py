import pymysql
conn = pymysql.connect(host='localhost', user='root', database='contract_mgmt')
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM purchase_orders")
print(f'Total POs: {cur.fetchone()[0]}')
cur.execute("SELECT COUNT(*) FROM purchase_orders WHERE serial_number >= 1725")
print(f'New POs (SN>=1725): {cur.fetchone()[0]}')
cur.execute("SELECT MAX(serial_number) FROM purchase_orders")
print(f'Max SN: {cur.fetchone()[0]}')
cur.execute("""
    SELECT currency, COUNT(*) 
    FROM purchase_orders 
    WHERE serial_number >= 1725 
    GROUP BY currency 
    ORDER BY COUNT(*) DESC
""")
print(f'Currency dist: {dict(cur.fetchall())}')
cur.execute("""
    SELECT COALESCE(bs.name, '(NULL)'), COUNT(*) 
    FROM purchase_orders po 
    LEFT JOIN budget_sources bs ON po.budget_source_id=bs.id 
    WHERE po.serial_number >= 1725 
    GROUP BY bs.name 
    ORDER BY COUNT(*) DESC
""")
print(f'Budget sources: {dict(cur.fetchall())}')
conn.close()
