import pymysql
conn = pymysql.connect(host='localhost', user='root')
cur = conn.cursor()
cur.execute("SHOW DATABASES")
dbs = [r[0] for r in cur.fetchall()]
print(f'Databases: {dbs}')
if 'contract_mgmt' in dbs:
    cur.execute("USE contract_mgmt")
    cur.execute("SHOW TABLES")
    tables = [r[0] for r in cur.fetchall()]
    print(f'Tables in contract_mgmt: {tables}')
# Also check if maybe the data is in contract_mgmt2 or similar
for db in dbs:
    if 'contract' in db.lower():
        print(f'  Checking {db}...')
        cur.execute(f"USE {db}")
        cur.execute("SHOW TABLES")
        print(f'    Tables: {[r[0] for r in cur.fetchall()]}')
conn.close()
