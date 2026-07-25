import subprocess, sys, re, time, threading, urllib.request, urllib.error

def start_tunnel():
    ssh = r'C:\Users\oftan\AppData\Local\GitHubDesktop\app-3.5.12\resources\app\git\usr\bin\ssh.exe'
    proc = subprocess.Popen(
        [ssh, '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=NUL', '-R', '80:localhost:5000', 'serveo.net'],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    )
    url = None
    for line in proc.stdout:
        print(line.rstrip())
        m = re.search(r'https://[^\s]+', line)
        if m:
            url = m.group().rstrip('.')
            print(f'\n=== PUBLIC URL: {url} ===')
            print('=== Login: admin / admin ===\n')
        sys.stdout.flush()
    return url

def verify(url):
    while True:
        try:
            r = urllib.request.urlopen(url + '/login', timeout=10)
            if r.status == 200:
                print(f'Tunnel verified: {r.status}')
            return
        except urllib.error.HTTPError as e:
            if e.code in (502, 503):
                time.sleep(3)
                continue
            print(f'Tunnel error: {e.code}')
            return
        except Exception as e:
            print(f'Waiting for tunnel: {e}')
            time.sleep(3)

t = threading.Thread(target=verify, args=('https://serveo.net',), daemon=True)
t.start()
start_tunnel()
