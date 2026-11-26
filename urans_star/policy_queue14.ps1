# policy_queue14.ps1 - 17.11 13:00 (koordynator, prosba Julka 12:09: "waliduj MPC w URANS lokalnie").
# OVS_MPCF_90: MPC z kara za komfort (W_A 1,5, model zidentyfikowany na Faltinsenie B) na fali regularnej Godo, obciazenie 90 %, do 30 s, ze scenami.
# W modelu (ten sam most, Faltinsen B w miejsce STAR): -13,7 % przy z'' RMS 0,46 m/s2 (K0 85 %: -8,4 % przy 0,40).
# MPC liczy Python (95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort\mpc_falt_bridge.py), makro STAR wymienia pliki co takt (jak OVS_MPC_WZ2).
# Wznowienie: uruchom ponownie (przebieg i most podejmuja od ostatniego checkpointu). Log: 70_godo_case\overnight_chain.log
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy14: ' + $m) }
$tag = 'OVS_MPCF_90'; $case = "T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\$tag"
New-Item -ItemType Directory -Force $case | Out-Null
Remove-Item "$case\MPC_STOP" -EA SilentlyContinue
Remove-Item "$case\STOP" -EA SilentlyContinue
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$br = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort\mpc_falt_bridge.py'
$env:MPC_PROBE_D = '3.0'
$bp = Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',$br,$case,'1.5','0.2' -WindowStyle Hidden -PassThru -RedirectStandardError "$case\bridge.err"
Log "start $tag, most MPC pid $($bp.Id)"
$c = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','mass_kg=28.17007','t_end_s=30.0','scenes=1','scene_every_steps=100','mpc_timeout_s=180','wake_gauges=-3.0','mpc_probe=GODO_eta_x-3.0')
& $py ..\30_URANS_STAR\run_mpcf_ctrl.py $tag $setup ((2..17) -join ',') mode=mpc_bridge kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=1.9367999917313226 pitch_trim_deg=2.338 @c 2>&1 | Out-File -Append "..\30_URANS_STAR\overset_runs\queue14_MPCF.out" -Encoding utf8
Log ("end $tag : " + (Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue))
New-Item -ItemType File -Force "$case\MPC_STOP" | Out-Null
Log 'koniec kolejki'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
