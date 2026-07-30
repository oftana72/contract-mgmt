import urllib.request, csv, io
url = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=2126924452'
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=120) as resp:
    raw = resp.read()
text = raw.decode('utf-8-sig')
reader = csv.reader(io.StringIO(text))
rows = list(reader)

# Find rows where col[13] has "BR" or "BIRR" or col[12] has BR prefix
print("=== Currency column values ===")
currencies = set()
for i, row in enumerate(rows):
    if len(row) > 13:
        c = row[13].strip()
        if c:
            if c not in ('USD', 'ETB', 'BIRR'):
                print(f'  Row {i}: curr={repr(c)}, col12={repr(row[12][:30])}')
                currencies.add(c)

# Show all unique currency values
print(f'\nAll unique currencies: {currencies}')

# Check total_po_amount column for combined format
print("\n=== Combined format in total_po_amount ===")
for i, row in enumerate(rows):
    if len(row) > 12:
        v = row[12].strip()
        if v:
            import re
            if re.match(r'[A-Za-z]+', v) and not re.match(r'^[\d,.\s]+$', v.replace(',','')):
                print(f'  Row {i}: po={row[3]}, total={repr(v)}')
