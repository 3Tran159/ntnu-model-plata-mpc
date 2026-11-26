# policy_queue12.ps1 - 15.11 18:55 (koordynator, zgoda Julka: noc niedziela). Fala od plata: opor w wodzie spokojnej rosnie do 20 s (64 -> 72,7 W), wiec:
# 1) OVS_CALM_100_FALA przedluzony 20 -> 40 s (wznowienie z punktu kontrolnego) - czy opor dojdzie do ok. 74 W (CD z tarcia i ksztaltu + pelny opor falowy z teorii)
# 2) OVS_CALM_90 przedluzony 8 -> 20 s - odniesienie z tej samej chwili dla przebiegow przy 90 % (okno 5,8-11,6 s)
# Ok. 7 h + 4,5 h. Wznowienie: uruchom ponownie. Log: 70_godo_case\overnight_chain.log
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy12: ' + $m) }
function TimeOf($tag){ $s = Get-Content "overset_runs\$tag\RUN_STATE.json" -Raw -EA SilentlyContinue | ConvertFrom-Json -EA SilentlyContinue; if ($s) { return [double]$s.time_s } else { return 0 } }
$calm = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\CALM\GODO_OVERSET_SETUP_CALM.sim'
$common = @('mode=pid','kp_deg_per_m=6.63','ki_deg_per_m_s=1.18','z_ref_m=0','release_s=1.0','inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40')
Log 'start kolejki'
if ((TimeOf 'OVS_CALM_100_FALA') -lt 39.9) {
  Log 'start OVS_CALM_100_FALA do 40 s (wznowienie)'
  & $py ..\30_URANS_STAR\run_k0_ctrl.py OVS_CALM_100_FALA $calm ((2..17) -join ',') @common t_end_s=40.0 pitch_trim_deg=2.93 mass_kg=31.30078 'wake_gauges=-10,5,10,20,30,40,50,60,70,78,90,100' 2>&1 | Out-File -Append 'overset_runs\queue12_CALM_100.out' -Encoding utf8
  Log ("end OVS_CALM_100_FALA : " + (Get-Content 'overset_runs\OVS_CALM_100_FALA\RUN_RESULT.json' -Raw -EA SilentlyContinue))
}
if ((TimeOf 'OVS_CALM_90') -lt 19.9) {
  Log 'start OVS_CALM_90 do 20 s (wznowienie)'
  & $py ..\30_URANS_STAR\run_k0_ctrl.py OVS_CALM_90 $calm ((2..17) -join ',') @common t_end_s=20.0 pitch_trim_deg=2.85 mass_kg=28.17007 2>&1 | Out-File -Append 'overset_runs\queue12_CALM_90.out' -Encoding utf8
  Log ("end OVS_CALM_90 : " + (Get-Content 'overset_runs\OVS_CALM_90\RUN_RESULT.json' -Raw -EA SilentlyContinue))
}
Log 'koniec kolejki'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
