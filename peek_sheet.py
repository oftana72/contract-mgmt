import csv, io, urllib.request
url = 'https://docs.google.com/spreadsheets/d/1gkEZyg5I07OkuEB0cfQxEmXNUQvdYT08UWSt9eahERA/export?format=csv&gid=259920423'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
raw = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
reader = csv.reader(io.StringIO(raw))
for i, row in enumerate(reader):
    if i < 2:
        continue
    if i >= 7:
        break
    # Print all non-empty columns for rows 2-6
    print(f'--- Row {i} ---')
    for j, val in enumerate(row):
        if val.strip():
            print(f'  Col {j}: {repr(val[:80])}')
