import urllib.request, json, sys, time, ssl

API_KEY = 'rnd_KeacZajQPsN5gRW989Del9qDJyXU'
BASE = 'https://api.render.com/v1'
HEADERS = {
    'Authorization': f'Bearer {API_KEY}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

def api(method, path, body=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        ctx = ssl._create_unverified_context()
        r = urllib.request.urlopen(req, timeout=30, context=ctx)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f'  API Error {e.code}: {err[:400]}')
        return e.code, None
    except Exception as e:
        print(f'  Error: {e}')
        return 0, None

print('=== Step 1: Get workspace ID ===')
status, owners = api('GET', '/owners')
if not owners:
    sys.exit(1)
owner_data = None
for o in owners:
    ow = o.get('owner', {})
    if ow.get('type') in ('team', 'user'):
        owner_data = ow
        break
if not owner_data and owners:
    owner_data = owners[0].get('owner', {})
if not owner_data or not owner_data.get('id'):
    print('No workspace found'); sys.exit(1)

owner_id = owner_data['id']
print(f'Workspace: {owner_data["name"]} ({owner_id})')

print('\n=== Step 2: Create PostgreSQL database ===')
db_body = {
    'name': 'contract-mgmt-db',
    'plan': 'free',
    'ownerId': owner_id,
    'version': '16',
    'region': 'frankfurt'
}
status, db_result = api('POST', '/postgres', db_body)
db_id = None
if status == 201 and db_result:
    db_id = db_result.get('id')
    print(f'Database created! ID: {db_id}')
elif status == 402:
    print('Payment required. Please add billing info at https://dashboard.render.com/billing')
    print('Then re-run this script.')
    sys.exit(1)
else:
    print('Looking for existing databases...')
    status, dbs = api('GET', '/postgres')
    if dbs:
        for db in dbs:
            print(f'  DB: {db.get("name")} ({db.get("id")}) - {db.get("status")}')
        db_id = dbs[0].get('id') if dbs else None
    else:
        print('No existing databases found')
        sys.exit(1)

if db_id:
    print('\n=== Step 3: Wait for database ready (up to 60s) ===')
    for i in range(12):
        time.sleep(5)
        status, info = api('GET', f'/postgres/{db_id}')
        if info:
            st = info.get('status')
            print(f'  Status: {st}')
            if st == 'available':
                break

    print('\n=== Step 4: Get connection string ===')
    status, conn = api('GET', f'/postgres/{db_id}/connection-info')
    internal_conn = conn.get('internalConnectionString', '') if conn else ''
    if internal_conn:
        print(f'Internal connection string obtained ({len(internal_conn)} chars)')
    else:
        print('No internal connection string found')
        internal_conn = ''

print('\n=== Step 5: Create web service ===')
svc_body = {
    'type': 'web_service',
    'name': 'contract-mgmt',
    'ownerId': owner_id,
    'repo': 'https://github.com/oftana72/contract-mgmt',
    'branch': 'master',
    'autoDeploy': 'yes',
    'serviceDetails': {
        'runtime': 'python',
        'plan': 'free',
        'region': 'frankfurt',
        'numInstances': 1,
        'healthCheckPath': '/login',
        'envSpecificDetails': {
            'buildCommand': 'pip install -r requirements.txt',
            'startCommand': 'gunicorn app:app --bind 0.0.0.0:$PORT --workers 2'
        }
    },
    'envVars': [
        {'key': 'SECRET_KEY', 'generateValue': True},
        {'key': 'FLASK_ENV', 'value': 'production'},
    ]
}
if internal_conn:
    svc_body['envVars'].append({'key': 'DATABASE_URL', 'value': internal_conn})

status, svc_result = api('POST', '/services', svc_body)
if status == 201 and svc_result:
    svc = svc_result.get('service', {})
    svc_id = svc.get('id')
    svc_url = svc.get('serviceDetails', {}).get('url', '')
    print(f'Service created!')
    print(f'  Dashboard: https://dashboard.render.com/web/{svc_id}')
    print(f'  URL: {svc_url}')
    print(f'\nYour app will be live at {svc_url} once deployed (5-10 min)')
    print(f'Login: admin / admin')
    print(f'\nAfter deployment, import data by running:')
    print(f'  $env:DATABASE_URL="{internal_conn}"; python import_data.py')
elif status == 402:
    print('Payment required. Add billing at https://dashboard.render.com/billing')
elif status == 409:
    print('Service may already exist. Check: https://dashboard.render.com')
else:
    print(f'Service creation returned status {status}')

print('\n=== Deploy complete ===')
