# policy_queue8.ps1 - 13.11 20:25, zgoda Julka 20:12 ("tak"). Po policy_queue7 (woda spokojna -0,3 / -0,6 m) liczy przy OBCIAZENIU 90 %:
#   1. OVS_CALM_90   - woda spokojna, PID2 (6,63 / 1,18), z_ref 0, 8 s, masa 28,17 kg na pasek (90 %), trym 2,85 deg (CL 0,578 przy nachyleniu URANS 0,90*2pi)
#   2. OVS_K0_85_90  - fala Godø (H 1,5 m, T 5 s), PID1 Godø (2,01 / 0,196) + K0: kasowanie 85 % pionowej predkosci wody na placie (makro_k0, KOPIA makra)
# Oryginalne makra nietkniete. Wznowienie: uruchom ponownie (pomija skonczone). Log: 70_godo_case\overnight_chain.log
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy8: ' + $m) }
function Done($tag){ $r = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue; return ($r -and $r -match '"(DONE|HOLD_LIMIT|HOLD_STOP_FILE|HOLD_CFL|HOLD_NAN|HOLD_MPC)"') }
function Q7Busy(){ return [bool](Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*policy_queue7.ps1*' -or $_.CommandLine -like '*run_overset_ctrl.py OVS_CALM_Z*' }) }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$calm = 'T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset\CALM\GODO_OVERSET_SETUP_CALM.sim'
$common = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','pitch_trim_deg=2.85','mass_kg=28.17007')
Log 'start (czeka na koniec policy_queue7)'
Start-Process -FilePath $py -ArgumentList '..\20_supervisor\keep_awake_while.py','run_','30' -WindowStyle Hidden
while (Q7Busy) { Start-Sleep 60 }
Log 'policy_queue7 skonczona'
$run = 'OVS_CALM_90'
if (-not (Done $run)) {
  Log "start $run (woda spokojna, obciazenie 90 %, PID2, 8 s)"
  & $py run_overset_ctrl.py $run $calm ((2..17) -join ',') mode=pid kp_deg_per_m=6.63 ki_deg_per_m_s=1.18 z_ref_m=0 t_end_s=8.0 release_s=1.0 @common 2>&1 | Out-Null
  Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
$run = 'OVS_K0_85_90'
if (-not (Done $run)) {
  Log "start $run (fala Godø, obciazenie 90 %, PID1 + K0 85 %, makro_k0)"
  & $py ..\30_URANS_STAR\run_k0_ctrl.py $run $setup ((2..17) -join ',') mode=k0 k0_gain=0.85 kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=1.9367999917313226 t_end_s=11.620799950387935 @common 2>&1 | Out-Null
  Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
Log 'koniec kolejki'
