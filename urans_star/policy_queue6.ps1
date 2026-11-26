# policy_queue6.ps1 - 13.11 05:50. MPC padl po 0,55 s (HOLD_MPC: serwer Pythona sie wysypal na kolizji plikow w Windows, os.replace).
# Naprawione (ponawianie zapisu po obu stronach) i sprawdzone klientem testowym (1549 taktow, -69,6 % jak MPC bezposrednio).
# Czeka na koniec TD3_C338 (liczy sie od 05:40), przemianowuje OVS_MPC_WZ2 -> OVS_MPC_WZ2_BLAD_most, potem policy_queue5 (MPC, woda spokojna).
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy6: ' + $m) }
function Busy($tag){ return [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*run_*_ctrl.py $tag *" }) }
Log 'start (czeka na TD3_C338, potem MPC ponownie)'
while (Busy 'OVS_POL_TD3_C338') { Start-Sleep 60 }
if (Test-Path 'overset_runs\OVS_POL_TD3_C338\history.csv') { New-Item 'overset_runs\OVS_POL_TD3_C338\POLICY_OK' -ItemType File -Force | Out-Null }
Log ('TD3_C338 koniec: ' + (Get-Content 'overset_runs\OVS_POL_TD3_C338\RUN_RESULT.json' -Raw -EA SilentlyContinue))
$r = Get-Content 'overset_runs\OVS_MPC_WZ2\RUN_RESULT.json' -Raw -EA SilentlyContinue
if ($r -and $r -match 'HOLD_MPC') { Rename-Item 'overset_runs\OVS_MPC_WZ2' 'OVS_MPC_WZ2_BLAD_most'; Log 'OVS_MPC_WZ2 -> OVS_MPC_WZ2_BLAD_most' }
& powershell -NoProfile -ExecutionPolicy Bypass -File T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\policy_queue5.ps1
