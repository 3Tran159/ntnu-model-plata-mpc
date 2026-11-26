# Overnight chain (10/11 Nov), cores 2-17, all runs with the servo model (actuator=lag2, wn 40 rad/s, rate <= 90 deg/s):
#   1) OVS_PID_BASE2  - Godø PID baseline at design draft (reference)
#   2) OVS_PID_PRBS1  - PID + PRBS +-2 deg every 0.2 s   (surrogate training data)
#   3) OVS_PID_SINE_A2- PID + sine +-2 deg at the encounter period (surrogate data)
$ErrorActionPreference = 'Continue'
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$py = '..\.venv\Scripts\python.exe'
$cores = (2..17) -join ','
$common = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40')
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'chain start (v2, servo lag2); waiting for the old OVS_PID_BASE session to stop'
while (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*run_overset_ctrl.py OVS_PID_BASE *' }) { Start-Sleep 20 }
$runs = @(
  @('OVS_PID_BASE2', @('mode=pid')),
  @('OVS_PID_PRBS1', @('mode=pid_prbs','exc_amp_deg=2.0','knot_s=0.2','seed=1')),
  @('OVS_PID_SINE_A2', @('mode=pid_sine','exc_amp_deg=2.0','exc_period_s=1.9368','exc_phase_deg=0'))
)
foreach ($r in $runs) {
  Log "start $($r[0])"
  & $py run_overset_ctrl.py $r[0] $setup $cores @($r[1] + $common) 2>&1 | Out-Null
  Log ("end $($r[0]): " + (Get-Content "overset_runs\$($r[0])\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
Log 'chain end'
