import pymysql
conn = pymysql.connect(host='localhost', user='root', database='contract_mgmt')
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM purchase_order")
print(f'Total POs: {cur.fetchone()[0]}')
cur.execute("SELECT MAX(serial_number) FROM purchase_order")
print(f'Max SN: {cur.fetchone()[0]}')
cur.execute("SELECT currency, COUNT(*) FROM purchase_order WHERE serial_number >= 1725 GROUP BY currency ORDER BY COUNT(*) DESC")
print(f'Currency dist: {cur.fetchall()}')
cur.execute("""
    SELECT bs.name, COUNT(*) 
    FROM purchase_order po 
    LEFT JOIN budget_source bs ON po.budget_source_id=bs.id 
    WHERE po.serial_number >= 1725 
    GROUP BY bs.name 
    ORDER BY COUNT(*) DESC
""")
print(f'Budget sources: {cur.fetchall()}')
conn.close()
