import pymysql
conn = pymysql.connect(host='localhost', user='root', database='contract_mgmt')
cur = conn.cursor()
# Check all unique currency values in new POs
cur.execute("SELECT DISTINCT currency FROM purchase_orders WHERE serial_number >= 1725 ORDER BY currency")
print(f'All currencies: {cur.fetchall()}')

# Check POs where currency might be 'BR' or 'BIRR'
cur.execute("SELECT serial_number, po_number, currency, total_po_amount FROM purchase_orders WHERE serial_number >= 1725 AND currency IN ('BR', 'BIRR')")
print(f'BR/BIRR POs: {cur.fetchall()}')

# Check raw total_po_amount for rows with empty currency to see if they have embedded currency
cur.execute("""
    SELECT serial_number, po_number, total_po_amount, currency
    FROM purchase_orders 
    WHERE serial_number >= 1725 AND (currency IS NULL OR currency = '')
    LIMIT 10
""")
print(f'Empty currency POs sample: {cur.fetchall()}')

# Actually, let me check what the first failed run committed vs didn't
# Re-run the check on total count
cur.execute("SELECT COUNT(*), MAX(serial_number) FROM purchase_orders")
print(f'Total/MAX: {cur.fetchall()}')

conn.close()
