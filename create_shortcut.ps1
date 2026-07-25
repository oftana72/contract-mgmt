$projectPath = "C:\Users\oftan\AppData\Local\Temp\opencode\contract-mgmt"
$MyPath = Join-Path $projectPath "start_app.bat"
$WshShell = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$Shortcut = $WshShell.CreateShortcut("$desktop\Contract Management.lnk")
$Shortcut.TargetPath = $MyPath
$Shortcut.WorkingDirectory = $projectPath
$Shortcut.Description = "Contract Management App - http://10.1.38.177:5000"
$Shortcut.WindowStyle = 1
$Shortcut.IconLocation = "shell32.dll, 1"
$Shortcut.Save()
Write-Host "Desktop shortcut created!"
