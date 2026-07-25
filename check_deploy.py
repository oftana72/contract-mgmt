import urllib.request, json, ssl

API_KEY = 'rnd_KeacZajQPsN5gRW989Del9qDJyXU'
BASE = 'https://api.render.com/v1'
HEADERS = {'Authorization': f'Bearer {API_KEY}', 'Accept': 'application/json'}
ctx = ssl._create_unverified_context()

def api_get(path):
    req = urllib.request.Request(BASE + path, headers=HEADERS)
    r = urllib.request.urlopen(req, timeout=15, context=ctx)
    return json.loads(r.read())

# Get service
services = api_get('/services')
svc_id = None
for s in services:
    svc = s.get('service', s)
    if svc.get('name') == 'contract-mgmt':
        svc_id = svc.get('id')
        print(f'Service: {svc["name"]} (ID: {svc_id})')
        print(f'URL: {svc.get("serviceDetails", {}).get("url", "N/A")}')
        print(f'Status: {svc.get("suspended", "not_suspended")}')
        break

if svc_id:
    # Get deploys
    deploys = api_get(f'/services/{svc_id}/deploys?limit=3')
    for d in deploys:
        dep = d.get('deploy', d)
        did = dep.get('id', '?')
        status = dep.get('status', '?')
        created = dep.get('createdAt', '?')[:19]
        print(f'  Deploy: {did} status={status} at={created}')
    
    # Get recent logs
    logs = api_get(f'/services/{svc_id}/logs?limit=20')
    for log in logs[:10]:
        msg = log.get('message', '').strip()
        if msg:
            print(f'  Log: {msg[:200]}')

print('\nApp URL: https://contract-mgmt-lnzy.onrender.com')
print('Login: admin / admin')
