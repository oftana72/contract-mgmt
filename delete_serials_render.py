import requests, urllib3, re, json
urllib3.disable_warnings()

BASE = 'https://contract-mgmt-lnzy.onrender.com'
s = requests.Session()
s.verify = False

# Login
r = s.post(BASE + '/login', data={'username': 'admin', 'password': 'admin'}, timeout=30)
if r.status_code != 200 or '/login' in r.url:
    print('Login failed:', r.status_code)
    exit(1)

sns_to_delete = [3051,3037,3036,3035,3033,3032,3031,3029,3028,3026,3025,3024,3023,3022,3015,3014,3013,3012,3011,3010,3009,3008,3007,3006,3005,3004,3003,2921,2920,2919,2918,2917,2916]

total_deleted = 0
for sn in sns_to_delete:
    # Search the POs page for this serial
    r = s.get(BASE + f'/pos?search={sn}', timeout=30)
    if r.status_code != 200:
        print(f'SN {sn}: page error {r.status_code}')
        continue

    # Find PO IDs in the page - look for delete buttons/forms
    # Pattern: action="/pos/ID/delete"
    ids = set(re.findall(r'/pos/(\d+)/delete', r.text))
    if not ids:
        print(f'SN {sn}: no delete links found')
        continue

    for pid in ids:
        r2 = s.post(BASE + f'/pos/{pid}/delete', timeout=30)
        if r2.status_code in (200, 302):
            total_deleted += 1
            print(f'SN {sn} (ID {pid}): deleted')
        else:
            print(f'SN {sn} (ID {pid}): delete failed {r2.status_code}')

print(f'\nTotal deleted: {total_deleted}')
