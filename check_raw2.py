import urllib.request, csv, io
url = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=2126924452'
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=120) as resp:
    raw = resp.read()
text = raw.decode('utf-8-sig')
reader = csv.reader(io.StringIO(text))
rows = list(reader)

# Find rows where budget source (col 14) has newlines
print("=== Budget sources with newlines ===")
for i, row in enumerate(rows):
    if len(row) > 14:
        bs = row[14] if row[14] else ''
        if '\n' in bs:
            print(f'  Row {i}: SN={row[0]}, PO={row[3]}, bs={repr(bs)}')

# Also find null budget sources (empty)
print("\n=== Null/empty budget sources (sample) ===")
count = 0
for i, row in enumerate(rows):
    if i < 3:
        continue  # skip headers
    if len(row) > 14:
        bs = row[14].strip() if row[14] else ''
        if not bs:
            print(f'  Row {i}: SN={row[0]}, PO={row[3]}, curr={repr(row[13])}')
            count += 1
            if count > 10:
                break

# Check some EUR rows
print("\n=== EUR rows ===")
for i, row in enumerate(rows):
    if len(row) > 13 and row[13].strip() == 'EUR':
        print(f'  Row {i}: SN={row[0]}, PO={row[3]}, bs={repr(row[14])}')
