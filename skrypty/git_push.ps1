# Push na GitHub (logowanie: okno Git Credential Manager przy pierwszym razie).
$g = 'C:\Program Files\Git\cmd\git.exe'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (& $g remote)) { & $g remote add origin 'https://github.com/3Tran159/ntnu-model-plata-mpc.git' }
& $g push -u origin main
