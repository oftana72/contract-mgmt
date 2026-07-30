import urllib.request, csv, io
url = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=2126924452'
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=120) as resp:
    raw = resp.read()
text = raw.decode('utf-8-sig')
reader = csv.reader(io.StringIO(text))
for i, row in enumerate(reader):
    # Print first 5 fields
    vals = [repr(x[:50]) for x in row[:5]]
    print(f'Row {i}: {vals}')
    if i >= 15:
        break
# Also check what's in sheet for first few row[0]
reader2 = csv.reader(io.StringIO(text))
print('\n--- Full rows 0-5 ---')
for i, row in enumerate(reader2):
    if i <= 5:
        for j, v in enumerate(row):
            if v.strip():
                print(f'  [{j}] {repr(v[:80])}')
    else:
        break
