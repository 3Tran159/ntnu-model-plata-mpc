# policy_queue11.ps1 - 14.11 20:15 (koordynator, zgoda Julka 19:56): T3 - fala od plata w URANS.
# Czeka na koniec policy_queue10, potem OVS_CALM_100_FALA: woda spokojna, 100 %, PID2 (jak OVS_CALM_PID2), 20 s, natywne sondy wzniesienia
# za platem (wake_gauges, tworzone przez makro_k0 w .sim przebiegu - edytowalne w GUI). Cel: amplituda fali od plata (teoria ok. 0,19 m, lambda 98 m)
# i opor w stanie ustalonym. Ok. 6,5 h. Wznowienie: uruchom ponownie. Log: 70_godo_case\overnight_chain.log
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy11: ' + $m) }
function Done($tag){ $r = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue; return ($r -and $r -match '"(DONE|HOLD_LIMIT|HOLD_STOP_FILE|HOLD_CFL|HOLD_NAN|HOLD_MPC)"') }
function Q10Busy(){ return [bool](Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*policy_queue10.ps1*' }) }
$calm = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\CALM\GODO_OVERSET_SETUP_CALM.sim'
Log 'start (czeka na koniec policy_queue10)'
while (Q10Busy) { Start-Sleep 60 }
$run = 'OVS_CALM_100_FALA'
if (-not (Done $run)) {
  Log "start $run (woda spokojna 100 %, PID2, 20 s, sondy fali za platem)"
  & $py ..\30_URANS_STAR\run_k0_ctrl.py $run $calm ((2..17) -join ',') mode=pid kp_deg_per_m=6.63 ki_deg_per_m_s=1.18 z_ref_m=0 t_end_s=20.0 release_s=1.0 pitch_trim_deg=2.93 mass_kg=31.30078 inner=8 iface_alpha_lo=0.1 cfl_max=1.5 actuator=lag2 servo_wn_rad_s=40 'wake_gauges=-10,5,10,20,30,40,50,60,70,78,90,100' 2>&1 | Out-File -Append "overset_runs\queue11_$run.out" -Encoding utf8
  Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
Log 'koniec kolejki'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
