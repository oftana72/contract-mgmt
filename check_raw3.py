import urllib.request, csv, io
url = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=2126924452'
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=120) as resp:
    raw = resp.read()
text = raw.decode('utf-8-sig')
reader = csv.reader(io.StringIO(text))
rows = list(reader)

# Find actual PO rows with empty budget source
print("=== PO rows with empty budget source ===")
for i, row in enumerate(rows):
    if i < 3:
        continue
    if len(row) > 0 and row[0].strip():  # has SN
        po = row[3].strip() if len(row) > 3 else ''
        if po:
            bs = row[14].strip() if len(row) > 14 and row[14] else ''
            if not bs:
                curr = row[13].strip() if len(row) > 13 and row[13] else ''
                print(f'  Row {i}: SN={row[0]}, PO={po}, curr={repr(curr)}')

# Also find total_po_amount with mixed format
print("\n=== Combined format in total_po_amount (not USD) ===")
import re
for i, row in enumerate(rows):
    if i < 3:
        continue
    if len(row) > 0 and row[0].strip():  # has SN
        if len(row) > 12:
            v = row[12].strip()
            if v and not re.match(r'^[\d,.\s]+$', v.replace(',','')):
                if not v.startswith('USD'):
                    print(f'  Row {i}: SN={row[0]}, PO={row[3]}, total={repr(v)}, curr_col={repr(row[13] if len(row)>13 else "")}')
