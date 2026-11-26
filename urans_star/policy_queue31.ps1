# policy_queue31.ps1 - 25.11 00:45 (Julek 00:37: "mielismy tez porownywac do idealnie rownej jazdy po falach", 00:40 "ok").
# Odniesienie "rowna jazda" dla OVS_CEL_005g_T8_90: TEN SAM jeden MPC, ta sama domena i fala T 8 s H 1,5 m, cel 0 g (W_A 20 = maks. komfort) -> OVS_CEL_000g_T8_90.
# Wtedy zysk = P(rowna jazda) - P(0,05 g), obie w fali i tej samej domenie: dryf wody spokojnej (OVS_CALM_T8DOM_90 rosnie 60 -> 65 W) przestaje miec znaczenie.
# Zastepuje koniec kolejki 30 (ktora uruchamialaby kolejke 29): czeka na koniec OVS_CALM_T8DOM_90, liczy OVS_CEL_000g_T8_90 (t_end 36 s, ok. 10-14 h), potem kolejka 29 (plat nieruchomy 3 glebokosci).
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue31.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'start: zatrzymuje skrypt kolejki 30 (sam przebieg wody spokojnej liczy dalej)'
Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like '*policy_queue30*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue; Log "zatrzymany skrypt kolejki 30 (pid $($_.ProcessId))" }
Log 'czekam na koniec OVS_CALM_T8DOM_90'
while (Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like '*run_mpcf_ctrl*OVS_CALM_T8DOM_90*' }) { Start-Sleep 30 }
Log ("koniec OVS_CALM_T8DOM_90: " + (Get-Content 'overset_runs\OVS_CALM_T8DOM_90\RUN_RESULT.json' -Raw -EA SilentlyContinue))
Start-Sleep 60
$setup = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\WAVE_T8\GODO_OVERSET_SETUP_T8.sim'
$br = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort\mpc_cel_bridge.py'
$tag = 'OVS_CEL_000g_T8_90'; $case = "T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\$tag"
if (-not ((Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue) -match '"DONE"')) {
    $free = (Get-PSDrive T).Free/1GB
    if ($free -lt 8) { Log ("za malo miejsca na T: {0:N1} GB - pomijam $tag" -f $free) }
    else {
        New-Item -ItemType Directory -Force $case | Out-Null; Remove-Item "$case\MPC_STOP","$case\STOP" -EA SilentlyContinue
        $env:MPC_PROBE_D = '3.0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_WA_MAX = '20'; $env:MPC_WYP = '1'
        $bp = Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',$br,$case,'0','0.2' -WindowStyle Hidden -PassThru -RedirectStandardError "$case\bridge.err"
        Log "start $tag, jeden MPC (cel 0 g = rowna jazda), fala T 8 s H 1,5 m, most pid $($bp.Id)"
        $c = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','mass_kg=28.17007','t_end_s=36.0','scenes=0','mpc_timeout_s=180','wake_gauges=-3.0','mpc_probe=GODO_eta_x-3.0','wave_period_s=8.0','encounter_period_s=4.0228')
        & $py run_mpcf_ctrl.py $tag $setup ((2..17) -join ',') mode=mpc_bridge kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=10.0 pitch_trim_deg=2.338 @c 2>&1 | Out-File -Append "overset_runs\queue31_$tag.out" -Encoding utf8
        Log ("end $tag : " + (Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue))
        New-Item -ItemType File -Force "$case\MPC_STOP" | Out-Null
    }
}
Log 'uruchamiam kolejke 29 (plat nieruchomy)'
Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\policy_queue29.ps1' -WindowStyle Hidden
Log 'koniec kolejki 31'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
