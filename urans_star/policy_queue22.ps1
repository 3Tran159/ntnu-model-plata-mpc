# policy_queue22.ps1 - 20.11 12:10 (koordynator, Julek 11:29-11:35: "jeden model MPC, ktorego nie zmieniamy ... URANS puszczasz na 0, potem 0.25, potem 0.5, potem 0.75 itd").
# JEDEN MPC (mpc_cel_bridge.py = samouczacy sie MPC z OVS_MPCL_T4_90 + cel z'' RMS zamiast stalej wagi), fala Godo, ta sama siatka co OVS_LEVEL_90 / OVS_MPCA_90.
# Kolejno cele z'' RMS: 0 g (W_A = 20 na stale), 0,25 g (2,4525 m/s2), dalej -1 = bez limitu komfortu (W_A = 0; model daje maks ok. 0,3 g, wiec 0,5 i 0,75 g nieosiagalne).
# t_end 12 s kazdy (okno 6-12 s jak OVS_LEVEL_90). Czeka na koniec kolejki 19. Rdzenie 2-17, ok. 8 h na przebieg. Log: queue22.log. Stop: plik STOP w overset_runs\<tag>.
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue22.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'czekam na koniec kolejki 19'
while (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*policy_queue19*' }) { Start-Sleep 120 }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$br = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort\mpc_cel_bridge.py'
foreach ($pair in @(@('OVS_CEL_000g_90','0'), @('OVS_CEL_025g_90','2.4525'), @('OVS_CEL_MAX_90','-1'))) {
    $tag = $pair[0]; $cel = $pair[1]; $case = "T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\$tag"
    if ((Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue) -match '"DONE"') { Log "$tag juz gotowy"; continue }
    if (Test-Path "$case\STOP") { Log "$tag ma STOP - pomijam"; continue }
    New-Item -ItemType Directory -Force $case | Out-Null; Remove-Item "$case\MPC_STOP" -EA SilentlyContinue
    $env:MPC_PROBE_D = '3.0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_WA_MAX = '20'
    $bp = Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',$br,$case,$cel,'0.2' -WindowStyle Hidden -PassThru -RedirectStandardError "$case\bridge.err"
    Log "start $tag, jeden MPC, cel z'' RMS $cel m/s2, pid $($bp.Id)"
    $c = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','mass_kg=28.17007','t_end_s=12.0','scenes=0','mpc_timeout_s=180','wake_gauges=-3.0','mpc_probe=GODO_eta_x-3.0')
    & $py run_mpcf_ctrl.py $tag $setup ((2..17) -join ',') mode=mpc_bridge kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=1.9367999917313226 pitch_trim_deg=2.338 @c 2>&1 | Out-File -Append "overset_runs\queue22_$tag.out" -Encoding utf8
    Log ("end $tag : " + (Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue))
    New-Item -ItemType File -Force "$case\MPC_STOP" | Out-Null
}
Log 'koniec kolejki 22'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
