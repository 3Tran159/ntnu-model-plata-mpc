# After OVS_PID_SINE_A2 finishes: calm-water reference (Godø D_cw) with Godø PID 2 (Kp 6.63 deg/m, Ki 1.18 deg/(m s)), cores 2-17.
# Calm water settles fast: t_end 4 s (release at 1 s).  Approved by Julek 11.11 10:19.
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'chain_calm: waiting for OVS_PID_SINE_A2'
while (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*run_overset_ctrl.py OVS_PID_SINE_A2*' }) { Start-Sleep 30 }
Log ('OVS_PID_SINE_A2 end: ' + (Get-Content overset_runs\OVS_PID_SINE_A2\RUN_RESULT.json -Raw -EA SilentlyContinue))
$calm = 'T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset\CALM\GODO_OVERSET_SETUP_CALM.sim'
if (-not (Test-Path $calm)) { Log 'calm setup missing - abort'; exit }
Log 'start OVS_CALM_PID2'
& $py run_overset_ctrl.py OVS_CALM_PID2 $calm ((2..17) -join ',') mode=pid kp_deg_per_m=6.63 ki_deg_per_m_s=1.18 t_end_s=4.0 release_s=1.0 inner=8 iface_alpha_lo=0.1 cfl_max=1.5 actuator=lag2 servo_wn_rad_s=40 2>&1 | Out-Null
Log ('end OVS_CALM_PID2: ' + (Get-Content overset_runs\OVS_CALM_PID2\RUN_RESULT.json -Raw -EA SilentlyContinue))
