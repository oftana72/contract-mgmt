import urllib.request, csv, io
url = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=2126924452'
req = urllib.request.Request(url)
with urllib.request.urlopen(req, timeout=120) as resp:
    raw = resp.read()
print('First bytes hex:', raw[:20].hex())
text = raw.decode('utf-8-sig')
reader = csv.reader(io.StringIO(text))
for i, row in enumerate(reader):
    first = row[0][:60] if row else 'EMPTY'
    print(f'Row {i}: len={len(row)}, first_col={repr(first)}')
    if i >= 15:
        break
