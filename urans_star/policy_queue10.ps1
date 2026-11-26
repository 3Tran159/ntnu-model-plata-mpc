# policy_queue10.ps1 - 14.11 12:55 (koordynator, prosba Julka 12:42: URANS-y bez zjadania limitu). Rdzenie 2-17, obciazenie 90 %, trym 2.338 deg z OVS_CALM_90.
# 1) OVS_K0_85_90_H1 - K0 85 % z szacunkiem predkosci wody z 1. harmonicznej eta_LE (k0_est=h1, bez 2. harmonicznej Stokesa; test wniosku B-Z4)
# 2) OVS_K0_50_90_H1 - K0 50 %, to samo (drugi punkt linii zysk-komfort w URANS)
# 3) OVS_PID1_90     - sam PID1 przy 90 % (odniesienie i trzeci punkt kalibracji modelu, u x 0,5)
# Kazdy ok. 3,4 h. Wznowienie: uruchom ponownie (gotowe przebiegi pomija). Stop: plik STOP w overset_runs\<tag>. Log: 70_godo_case\overnight_chain.log
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null   # ES_CONTINUOUS | ES_SYSTEM_REQUIRED - laptop nie zasypia, dopoki kolejka dziala
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy10: ' + $m) }
function Done($tag){ $r = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue; return ($r -and $r -match '"(DONE|HOLD_LIMIT|HOLD_STOP_FILE|HOLD_CFL|HOLD_NAN|HOLD_MPC)"') }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$common = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','pitch_trim_deg=2.338','mass_kg=28.17007','kp_deg_per_m=2.01','ki_deg_per_m_s=0.196','release_s=1.9367999917313226','t_end_s=11.620799950387935')
$runs = @(
  @('OVS_K0_85_90_H1', @('mode=k0','k0_gain=0.85','k0_est=h1')),
  @('OVS_K0_50_90_H1', @('mode=k0','k0_gain=0.5','k0_est=h1')),
  @('OVS_PID1_90',     @('mode=pid'))
)
Log 'start kolejki (3 przebiegi, rdzenie 2-17)'
foreach ($r in $runs) {
  $tag = $r[0]
  if (Done $tag) { Log "$tag juz gotowy - pomijam"; continue }
  Log "start $tag ($($r[1] -join ' '))"
  & $py ..\30_URANS_STAR\run_k0_ctrl.py $tag $setup ((2..17) -join ',') @($r[1]) @common 2>&1 | Out-File -Append "overset_runs\queue10_$tag.out" -Encoding utf8
  Log ("end $tag : " + (Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
Log 'koniec kolejki'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
