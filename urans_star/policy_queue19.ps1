# policy_queue19.ps1 - 18.11 20:35 (koordynator, prosba Julka 20:21 "lec z tym samouczacym sie MPC").
# OVS_MPCL_T4_90: SAMOUCZACE SIE MPC na NOWEJ fali (T 4 s, H 1,0 m - jak OVS_PID1_T4_90), bez strojenia pod te fale:
# most mpc_learn_bridge.py = adaptacyjne MPC (RLS sily nosnej) + czestosc fali wyznaczana na biezaco z sondy 3 m (start od wartosci dla fali God0).
# W_A 2,2, KI 0,2 - jak OVS_MPCA_90. W modelu (test 18.11 20:30): w_e wyuczone 4,676 = prawdziwe, -8,5 % przy z'' RMS 0,32 m/s2.
# Czeka na koniec kolejki 18. Rdzenie 2-17, ok. 8 h. Log: queue19.log.
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue19.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'czekam na koniec kolejki 18'
while (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'policy_queue(18|21)' }) { Start-Sleep 120 }
$tag = 'OVS_MPCL_T4_90'; $case = "T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\$tag"
New-Item -ItemType Directory -Force $case | Out-Null
Remove-Item "$case\MPC_STOP" -EA SilentlyContinue; Remove-Item "$case\STOP" -EA SilentlyContinue
$setup = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\WAVE_T4\GODO_OVERSET_SETUP_T4.sim'
$br = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort\mpc_learn_bridge.py'
$env:MPC_PROBE_D = '3.0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'
$bp = Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',$br,$case,'2.2','0.2' -WindowStyle Hidden -PassThru -RedirectStandardError "$case\bridge.err"
Log "start $tag, most samouczacy pid $($bp.Id)"
$c = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','mass_kg=28.17007','t_end_s=30.0','scenes=1','scene_every_steps=100','mpc_timeout_s=180','wake_gauges=-3.0','mpc_probe=GODO_eta_x-3.0','wave_period_s=4.0','encounter_period_s=1.3433')
& $py run_mpcf_ctrl.py $tag $setup ((2..17) -join ',') mode=mpc_bridge kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=1.9367999917313226 pitch_trim_deg=2.338 @c 2>&1 | Out-File -Append "overset_runs\queue19_MPCL.out" -Encoding utf8
Log ("end $tag : " + (Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue))
New-Item -ItemType File -Force "$case\MPC_STOP" | Out-Null
Log 'koniec kolejki 19'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null

