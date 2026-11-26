# policy_queue9.ps1 - 14.11 02:20 (koordynator): zastepuje policy_queue8 dla drugiego przebiegu. Poprawka: trym K0 przy 90 % brany z ustalonego
# kata w OVS_CALM_90 (srednia theta z ostatnich 2 s; w URANS ok. 2,31 deg), a nie 2,85 deg z rachunku recznego (PID1 ma male Ki - przy 2,85 plat jechalby ok. 0,27 m za wysoko).
# Czeka na koniec OVS_CALM_90 (liczony przez policy_queue8 / run_overset_ctrl.py), potem OVS_K0_85_90. Wznowienie: uruchom ponownie. Log: 70_godo_case\overnight_chain.log
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy9: ' + $m) }
function Done($tag){ $r = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue; return ($r -and $r -match '"(DONE|HOLD_LIMIT|HOLD_STOP_FILE|HOLD_CFL|HOLD_NAN|HOLD_MPC)"') }
function Busy(){ return [bool](Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*run_overset_ctrl.py OVS_CALM_90*' }) }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
Log 'start (czeka na koniec OVS_CALM_90)'
while (Busy) { Start-Sleep 60 }
Log ("OVS_CALM_90 koniec: " + (Get-Content "overset_runs\OVS_CALM_90\RUN_RESULT.json" -Raw -EA SilentlyContinue))
$trim = (& $py -c "import csv,numpy as np; rd=csv.reader(open(r'overset_runs\OVS_CALM_90\history.csv')); h=next(rd); R=[r for r in rd if len(r)==len(h)]; t=np.array([float(r[0]) for r in R]); th=np.array([float(r[h.index('theta_deg')]) for r in R]); print(round(float(th[t>t.max()-2].mean()),3))").Trim()
if (-not ($trim -as [double]) -or [double]$trim -lt 1.5 -or [double]$trim -gt 3.5) { Log "trym z CALM_90 poza zakresem ($trim) - uzywam 2.31"; $trim = '2.31' }
Log "trym K0 przy 90 % = $trim deg (z OVS_CALM_90)"
$common = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40',"pitch_trim_deg=$trim",'mass_kg=28.17007')
$run = 'OVS_K0_85_90'
if (-not (Done $run)) {
  Log "start $run (fala Godø, obciazenie 90 %, PID1 + K0 85 %, makro_k0, trym $trim)"
  & $py ..\30_URANS_STAR\run_k0_ctrl.py $run $setup ((2..17) -join ',') mode=k0 k0_gain=0.85 kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=1.9367999917313226 t_end_s=11.620799950387935 @common 2>&1 | Out-Null
  Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
Log 'koniec kolejki'
