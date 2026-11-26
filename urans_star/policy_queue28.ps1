# policy_queue28.ps1 - 23.11 22:35 (Julek 23.11: "niech cos liczy, w srode wracam"). Kopia kolejki 26.
# OVS_CEL_005g_T8_90: JEDEN MPC bez zmian (mpc_cel_bridge.py, kryterium na wypadkowej, cel 0,05 g = 0,4905 m/s2, KI 0,2) na DLUGIEJ fali czolowej:
# T 8 s, H 1,5 m (lambda 99,93 m, okres spotkania 4,023 s przy U 12,35 m/s), overset\WAVE_T8\GODO_OVERSET_SETUP_T8.sim (ta sama siatka co OVS_*_90, zanurzenie 1,09 m).
# Cel: test wzoru ujednoliconego (sufit x (1 + g/(U*omega_e)) = x 1,51) - drugi czlon (od poziomej predkosci fali) jest tu polowa glownego.
# release 10 s, t_end 36 s (okno analizy: calkowita liczba okresow spotkania po ok. 14 s). Czeka na koniec kolejek 26/27 (S1). Rdzenie 2-17, ok. 10-11 h (przy wolnej maszynie), do ok. 16 h gdy KORAB/POL42 licza rownolegle. Strefy fal: forsowanie 25 m, tlumienie 60 m (SetZonesT8.java, ZONES.txt).
# Log: queue28.log. Stop: plik STOP w overset_runs\OVS_CEL_005g_T8_90. Wznowienie: uruchom ponownie (run_mpcf_ctrl wznawia z punktu kontrolnego).
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue28.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'czekam na koniec kolejek 26/27 (S1)'
while (Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -like '*policy_queue26*' -or $_.CommandLine -like '*policy_queue27*' -or $_.CommandLine -like '*run_mpcf_ctrl*OVS_CEL_005g_S1L_R10_90*') }) { Start-Sleep 30 }
Start-Sleep 60

$setup = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\WAVE_T8\GODO_OVERSET_SETUP_T8.sim'
if (-not (Test-Path $setup)) { Log 'BRAK setupu T8 - nie startuje'; exit }
$br = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort\mpc_cel_bridge.py'
$tag = 'OVS_CEL_005g_T8_90'; $case = "T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\$tag"
if ((Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue) -match '"DONE"') { Log "$tag juz gotowy"; exit }
$free = (Get-PSDrive T).Free/1GB; if ($free -lt 8) { Log ("za malo miejsca na T: {0:N1} GB - nie startuje" -f $free); exit }
New-Item -ItemType Directory -Force $case | Out-Null; Remove-Item "$case\MPC_STOP","$case\STOP" -EA SilentlyContinue
$env:MPC_PROBE_D = '3.0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_WA_MAX = '20'; $env:MPC_WYP = '1'
$bp = Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',$br,$case,'0.4905','0.2' -WindowStyle Hidden -PassThru -RedirectStandardError "$case\bridge.err"
Log "start $tag, jeden MPC (wypadkowa 0,05 g), fala T 8 s H 1,5 m, pid $($bp.Id)"
$c = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','mass_kg=28.17007','t_end_s=36.0','scenes=0','mpc_timeout_s=180','wake_gauges=-3.0','mpc_probe=GODO_eta_x-3.0','wave_period_s=8.0','encounter_period_s=4.0228')
& $py run_mpcf_ctrl.py $tag $setup ((2..17) -join ',') mode=mpc_bridge kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=10.0 pitch_trim_deg=2.338 @c 2>&1 | Out-File -Append "overset_runs\queue28_$tag.out" -Encoding utf8
Log ("end $tag : " + (Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue))
New-Item -ItemType File -Force "$case\MPC_STOP" | Out-Null
Log 'koniec kolejki 28'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
