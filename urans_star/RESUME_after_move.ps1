# Resume after moving the laptop (11 Nov 2026).
# Continues OVS_PID_SINE_A2 from its last checkpoint (CP_006750_t6.7500.sim + .ctrl, t = 6.75 s of 11.62 s),
# cores 2-17, servo model, keep-awake on, dashboard restarted.  Run:  powershell -ExecutionPolicy Bypass -File RESUME_after_move.ps1
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
Remove-Item overset_runs\OVS_PID_SINE_A2\RUN_RESULT.json, overset_runs\OVS_PID_SINE_A2\STOP -ErrorAction SilentlyContinue
Start-Process -FilePath $py -ArgumentList 'run_overset_ctrl.py','OVS_PID_SINE_A2',$setup,((2..17) -join ','),'mode=pid_sine','exc_amp_deg=2.0','exc_period_s=1.9368','exc_phase_deg=0','inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40' -WindowStyle Hidden -RedirectStandardOutput ovs_sine.out -RedirectStandardError ovs_sine.err
Start-Process -FilePath $py -ArgumentList 'T:\NTNU_GODO_CONTROL_20261109\20_supervisor\keep_awake_while.py','run_overset_ctrl','20' -WindowStyle Hidden
if (-not (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*keep_server.ps1*' })) {
  Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','T:\NTNU_GODO_CONTROL_20261109\60_dashboard\keep_server.ps1' -WindowStyle Hidden }
Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' RESUME_after_move: OVS_PID_SINE_A2 from CP_006750')
Write-Host 'Resumed. Dashboard: http://127.0.0.1:8792/overset'
