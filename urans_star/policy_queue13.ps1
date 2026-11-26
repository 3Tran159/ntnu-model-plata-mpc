# policy_queue13.ps1 - 16.11 13:20 (koordynator, zgoda Julka 13:15: URANS na popoludnie i noc). Stan ustalony fali od plata (ok. 28 s) dla przebiegow przy 90 %:
# czeka na koniec obliczen modelu (trzy_platy_interakcja.py zajmuje rdzenie 2-23), potem przedluza do 30 s:
# 1) OVS_CALM_90 (20 -> 30 s) - odniesienie w stanie ustalonym, ok. 3,5 h
# 2) OVS_K0_85_90_H1 (11,6 -> 30 s), ok. 6,5 h
# 3) OVS_PID1_90 (11,6 -> 30 s), ok. 6,5 h - wyjasnienie odstajacego wyniku model / URANS
# Wznowienie: uruchom ponownie. Log: 70_godo_case\overnight_chain.log
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy13: ' + $m) }
function TimeOf($tag){ $s = Get-Content "overset_runs\$tag\RUN_STATE.json" -Raw -EA SilentlyContinue | ConvertFrom-Json -EA SilentlyContinue; if ($s) { return [double]$s.time_s } else { return 0 } }
function ModelBusy(){ return [bool](Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*trzy_platy_*.py*worker*' }) }
$calm = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\CALM\GODO_OVERSET_SETUP_CALM.sim'
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$c = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','mass_kg=28.17007','t_end_s=30.0','scenes=1','scene_every_steps=100')
Log 'start (czeka na koniec obliczen modelu na rdzeniach 2-23)'
while (ModelBusy) { Start-Sleep 60 }
if ((TimeOf 'OVS_CALM_90') -lt 29.9) { Log 'OVS_CALM_90 do 30 s'
  & $py ..\30_URANS_STAR\run_k0_ctrl.py OVS_CALM_90 $calm ((2..17) -join ',') mode=pid kp_deg_per_m=6.63 ki_deg_per_m_s=1.18 z_ref_m=0 release_s=1.0 pitch_trim_deg=2.85 @c 2>&1 | Out-File -Append 'overset_runs\queue13_CALM_90.out' -Encoding utf8
  Log ("end OVS_CALM_90 : " + (Get-Content 'overset_runs\OVS_CALM_90\RUN_RESULT.json' -Raw -EA SilentlyContinue)) }
if ((TimeOf 'OVS_K0_85_90_H1') -lt 29.9) { Log 'OVS_K0_85_90_H1 do 30 s'
  & $py ..\30_URANS_STAR\run_k0_ctrl.py OVS_K0_85_90_H1 $setup ((2..17) -join ',') mode=k0 k0_gain=0.85 k0_est=h1 kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=1.9367999917313226 pitch_trim_deg=2.338 @c 2>&1 | Out-File -Append 'overset_runs\queue13_K0_85.out' -Encoding utf8
  Log ("end OVS_K0_85_90_H1 : " + (Get-Content 'overset_runs\OVS_K0_85_90_H1\RUN_RESULT.json' -Raw -EA SilentlyContinue)) }
if ((TimeOf 'OVS_PID1_90') -lt 29.9) { Log 'OVS_PID1_90 do 30 s'
  & $py ..\30_URANS_STAR\run_k0_ctrl.py OVS_PID1_90 $setup ((2..17) -join ',') mode=pid kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=1.9367999917313226 pitch_trim_deg=2.338 @c 2>&1 | Out-File -Append 'overset_runs\queue13_PID1_90.out' -Encoding utf8
  Log ("end OVS_PID1_90 : " + (Get-Content 'overset_runs\OVS_PID1_90\RUN_RESULT.json' -Raw -EA SilentlyContinue)) }
Log 'koniec kolejki'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null

