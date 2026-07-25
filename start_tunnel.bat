@echo off
"C:\Users\oftan\AppData\Local\GitHubDesktop\app-3.5.12\resources\app\git\usr\bin\ssh.exe" -o StrictHostKeyChecking=no -o UserKnownHostsFile=NUL -R 80:localhost:5000 serveo.net > tunnel_out.txt 2>&1
