import urllib.request, csv, io
url = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=2126924452'
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=120) as resp:
    raw = resp.read()
text = raw.decode('utf-8-sig')
reader = csv.reader(io.StringIO(text))
rows = list(reader)

# Find rows where PO number is 7227, 7381, etc. in col 3
po_checks = ['7227', '7381', '7366', '7374', '7238', '7239', '7388']
for i, row in enumerate(rows):
    if len(row) > 14:
        po = row[3].strip() if row[3] else ''
        budget = row[14].strip() if row[14] else ''
        curr = row[13].strip() if row[13] else ''
        for check in po_checks:
            if check in po:
                print(f'Row {i}: PO={po}, budget=repr({budget}), curr=repr({curr})')
                break
