# policy_queue7.ps1 - 13.11 12:30, zgoda Julka 12:27 ("tak"): po MPC wstawia test plata nieruchomego (zarzut R2-1/R2-2 z recenzji:
# czy dodatek oporu dCD ~0,0014 w URANS to numeryka ukladu overset). Zastepuje policy_queue5/6 (zabite; MPC liczy dalej jako osobny proces).
# Kolejnosc: czeka na koniec OVS_MPC_WZ2 -> sprzata most MPC -> OVS_FIX_TRIM (plat nieruchomy, fala, kat trymu 3,5 st, nurzanie zablokowane caly czas)
#            -> woda spokojna -0,3 / -0,6 m. Wznowienie: uruchom ponownie (pomija skonczone). Log: 70_godo_case\overnight_chain.log
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy7: ' + $m) }
function Done($tag){ $r = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue; return ($r -and $r -match '"(DONE|HOLD_LIMIT|HOLD_STOP_FILE|HOLD_CFL|HOLD_NAN|HOLD_MPC)"') }
function Busy($tag){ return [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*run_*_ctrl.py $tag *" }) }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$common = @('pitch_trim_deg=3.5','inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40')
Log 'start (czeka na koniec OVS_MPC_WZ2)'
Start-Process -FilePath $py -ArgumentList '..\20_supervisor\keep_awake_while.py','run_','30' -WindowStyle Hidden
while (Busy 'OVS_MPC_WZ2') { Start-Sleep 60 }
Log ("OVS_MPC_WZ2 koniec: " + (Get-Content "overset_runs\OVS_MPC_WZ2\RUN_RESULT.json" -Raw -EA SilentlyContinue))
New-Item "overset_runs\OVS_MPC_WZ2\MPC_STOP" -ItemType File -Force | Out-Null; Start-Sleep 5
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*mpc_bridge_server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }

$run = 'OVS_FIX_TRIM'
if (-not (Done $run)) {
  Log "start $run (plat nieruchomy na fali: mode=hold, release_s=99, kat 3,5 st, z=0)"
  & $py run_overset_ctrl.py $run $setup ((2..17) -join ',') mode=hold release_s=99 @common 2>&1 | Out-Null
  Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
foreach ($run in @('OVS_CALM_Z-0.3', 'OVS_CALM_Z-0.6')) {
  if (Done $run) { Log "$run juz skonczony"; continue }
  $zr = $run.Substring(10); $calm = 'T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset\CALM\GODO_OVERSET_SETUP_CALM.sim'
  Log "start $run (woda spokojna, z_ref $zr m)"
  & $py run_overset_ctrl.py $run $calm ((2..17) -join ',') mode=pid kp_deg_per_m=6.63 ki_deg_per_m_s=1.18 "z_ref_m=$zr" t_end_s=8.0 release_s=1.0 @common 2>&1 | Out-Null
  Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
Log 'koniec kolejki'
