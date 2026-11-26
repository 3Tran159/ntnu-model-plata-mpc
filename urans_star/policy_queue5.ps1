# policy_queue5.ps1 - noc 12/13.11, 02:15. Zastepuje queue4 po wykryciu bledu: nq.compile_macro nadpisywal kopie makra
# oryginalem, wiec OVS_POL_TD3_GODO i OVS_POL_TD3_C338 policzyly PID Kp 10 (nie polityke). Ich katalogi -> *_BLAD_PIDKp10.
# Kolejnosc (zgoda Julka 22:13 "licz cala noc"): TD3_GODO (polityka, naprawdę) -> MPC (most Python) -> TD3_C338 -> woda spokojna -0,3/-0,6.
# Wznowienie: uruchom ponownie (pomija skonczone). Log: overnight_chain.log
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'; $V = 'T:\NTNU_GODO_CONTROL_20261109\40_MODEL_WIROWY_I_STEROWANIE\vortex_env'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy5: ' + $m) }
function Done($tag){ $r = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue; return ($r -and $r -match '"(DONE|HOLD_LIMIT|HOLD_STOP_FILE|HOLD_CFL|HOLD_NAN|HOLD_MPC)"') }
function Busy($tag){ return [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*run_*_ctrl.py $tag *" }) }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$common = @('pitch_trim_deg=3.5','inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40')
Log 'start (czeka na koniec blednego OVS_POL_TD3_C338)'
while (Busy 'OVS_POL_TD3_C338') { Start-Sleep 60 }
foreach ($old in 'OVS_POL_TD3_GODO','OVS_POL_TD3_C338') {
  if ((Test-Path "overset_runs\$old\history.csv") -and -not (Test-Path "overset_runs\$old\POLICY_OK")) {
    $c = Get-Content "overset_runs\$old\GodoOversetRun.java" -Raw -EA SilentlyContinue
    if ($c -notmatch 'loadPolicy') { Rename-Item "overset_runs\$old" "${old}_BLAD_PIDKp10"; Log "$old -> ${old}_BLAD_PIDKp10 (makro bez trybu policy)" }
  }
}
Start-Process -FilePath $py -ArgumentList '..\20_supervisor\keep_awake_while.py','run_','30' -WindowStyle Hidden

function RunPolicy($tag, $run) {
  if (Done $run) { Log "$run juz skonczony"; return }
  $pol = "$V\runs\$tag\policy_$tag.txt"
  if (-not (Test-Path $pol)) { Log "$tag brak pliku polityki"; return }
  Log "start $run (polityka $pol, poprawione makro)"
  & $py ..\30_URANS_STAR\run_policy_ctrl.py $run $setup ((2..17) -join ',') mode=policy "policy_file=$($pol -replace '\\','/')" @common 2>&1 | Out-Null
  if (Test-Path "overset_runs\$run\GodoOversetRun.java") { if ((Get-Content "overset_runs\$run\GodoOversetRun.java" -Raw) -match 'loadPolicy') { New-Item "overset_runs\$run\POLICY_OK" -ItemType File -Force | Out-Null } }
  Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}

RunPolicy 'TD3_GODO' 'OVS_POL_TD3_GODO'

# --- MPC w URANS ---
$run = 'OVS_MPC_WZ2'
if (-not (Done $run)) {
  $case = "overset_runs\$run"; New-Item -ItemType Directory -Force $case | Out-Null
  Remove-Item "$case\MPC_STOP","$case\MPC_REQ.txt","$case\MPC_RESP.txt" -EA SilentlyContinue
  $srv = Start-Process -FilePath $py -ArgumentList '-X','utf8',"$V\mpc_bridge_server.py",(Resolve-Path $case).Path,'2','2000' -WindowStyle Hidden -PassThru
  Start-Sleep 3; try { $srv.ProcessorAffinity = [IntPtr](1 -shl 22); $srv.PriorityClass = 'AboveNormal' } catch {}
  Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $srv.Id } | ForEach-Object { try { $c = Get-Process -Id $_.ProcessId; $c.ProcessorAffinity = [IntPtr](1 -shl 22); $c.PriorityClass = 'AboveNormal' } catch {} }
  Start-Sleep 20
  Log "start $run (MPC liniowy z modelu wirowego, W_Z 2, most mpc_bridge_server.py, rdzen 22)"
  & $py ..\30_URANS_STAR\run_mpc_ctrl.py $run $setup ((2..17) -join ',') mode=mpc_bridge mpc_timeout_s=180 @common 2>&1 | Out-Null
  Log ("end $run : " + (Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue))
  New-Item "$case\MPC_STOP" -ItemType File -Force | Out-Null; Start-Sleep 5
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*mpc_bridge_server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
}

RunPolicy 'TD3_C338' 'OVS_POL_TD3_C338'

foreach ($run in @('OVS_CALM_Z-0.3', 'OVS_CALM_Z-0.6')) {
  if (Done $run) { Log "$run juz skonczony"; continue }
  $zr = $run.Substring(10); $calm = 'T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset\CALM\GODO_OVERSET_SETUP_CALM.sim'
  Log "start $run (woda spokojna, z_ref $zr m)"
  & $py run_overset_ctrl.py $run $calm ((2..17) -join ',') mode=pid kp_deg_per_m=6.63 ki_deg_per_m_s=1.18 "z_ref_m=$zr" t_end_s=8.0 release_s=1.0 @common 2>&1 | Out-Null
  Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
Log 'koniec kolejki'
