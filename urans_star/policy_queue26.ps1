# policy_queue26.ps1 - 21.11 12:55 (start MPC dopiero przy t 10 s: wczesniej MPC szacowal czestosc fali z 2 s danych i wystartowal z katem +7,5 st.; w modelu z release 10 s dziala). Kopia kolejki 25, 21.11 11:15 (Julek 10:55 opcja A: poziom wody +0,3 m, plat startuje 1,39 m pod powierzchnia; poprzedni OVS_CEL_005g_S1L_R10_90 stanal na HOLD_LIMIT przy t 2,19 s). Kopia kolejki 24, z dnia 20.11 22:30 (Julek 21:54: "choc jedna walidacja naszej nieregularnej w URANS").
# OVS_CEL_005g_S1L_R10_90: JEDEN MPC bez zmian (mpc_cel_bridge.py, kryterium na wypadkowej, cel 0,05 g = 0,4905 m/s2) na fali NIEREGULARNEJ S1
# (JONSWAP Hs 1,5 m, Tp 5 s, ta sama realizacja co w modelu seed 100, 59 skladowych, okresy 2-7,5 s): overset\WAVE_S1\GODO_OVERSET_SETUP_S1_L139.sim.
# t_end 60 s (okno porownania 15-60 s, ok. 23 okresy spotkania przy Tp). Czeka na koniec kolejki 22 (0 g na fali Godo). Rdzenie 2-17, ok. 30-35 h. Log: queue26.log.
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue26.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'czekam na koniec kolejki 25'; while (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*policy_queue25*' }) { Start-Sleep 30 }

$setup = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\WAVE_S1\GODO_OVERSET_SETUP_S1_L139.sim'
if (-not (Select-String -Path 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\WAVE_S1\LEVEL.txt' -Pattern 'zapisano GODO_OVERSET_SETUP_S1_L139' -Quiet)) { Log 'BRAK poprawionego setupu S1 (FIX.txt) - nie startuje'; exit }
$br = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort\mpc_cel_bridge.py'
$tag = 'OVS_CEL_005g_S1L_R10_90'; $case = "T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\$tag"
if ((Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue) -match '"DONE"') { Log "$tag juz gotowy"; exit }
New-Item -ItemType Directory -Force $case | Out-Null; Remove-Item "$case\MPC_STOP","$case\STOP" -EA SilentlyContinue
$env:MPC_PROBE_D = '3.0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_WA_MAX = '20'; $env:MPC_WYP = '1'
$bp = Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',$br,$case,'0.4905','0.2' -WindowStyle Hidden -PassThru -RedirectStandardError "$case\bridge.err"
Log "start $tag, jeden MPC (wypadkowa 0,05 g), fala S1, pid $($bp.Id)"
$c = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','mass_kg=28.17007','t_end_s=65.0','scenes=0','mpc_timeout_s=180','wake_gauges=-3.0','mpc_probe=GODO_eta_x-3.0','wave_period_s=5.0','encounter_period_s=1.9368')
& $py run_mpcf_ctrl.py $tag $setup ((2..17) -join ',') mode=mpc_bridge kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=10.0 pitch_trim_deg=2.338 @c 2>&1 | Out-File -Append "overset_runs\queue26_$tag.out" -Encoding utf8
Log ("end $tag : " + (Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue))
New-Item -ItemType File -Force "$case\MPC_STOP" | Out-Null
Log 'koniec kolejki 26'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null


