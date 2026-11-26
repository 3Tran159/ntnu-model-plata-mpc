# policy_queue4.ps1 - noc 12/13.11, decyzja Julka 22:13 ("zgoda, licz cala noc"): zastepuje reszte policy_queue3.
# Kolejnosc: czeka na koniec OVS_POL_TD3_C338 (liczy sie juz, uruchomiony przez queue3) -> MPC w URANS (most STAR<->Python, W_Z 2)
# -> woda spokojna z = -0,3 / -0,6 m -> wspornik h 0,7 / 1,5 m na GPU.  TD3_C wypada z nocy.
# Wznowienie: uruchom ponownie (pomija skonczone). Log: overnight_chain.log
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'; $V = 'T:\NTNU_GODO_CONTROL_20261109\40_MODEL_WIROWY_I_STEROWANIE\vortex_env'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy4: ' + $m) }
function Done($tag){ $r = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue; return ($r -and $r -match '"(DONE|HOLD_LIMIT|HOLD_STOP_FILE|HOLD_CFL|HOLD_NAN|HOLD_MPC)"') }
function Busy($tag){ return [bool](Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*run_*_ctrl.py $tag *" }) }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
Log 'start (czeka na TD3_C338)'
while ((-not (Done 'OVS_POL_TD3_C338')) -or (Busy 'OVS_POL_TD3_C338')) { Start-Sleep 120 }
Log ('TD3_C338 koniec: ' + (Get-Content 'overset_runs\OVS_POL_TD3_C338\RUN_RESULT.json' -Raw -EA SilentlyContinue))
Start-Process -FilePath $py -ArgumentList '..\20_supervisor\keep_awake_while.py','run_','30' -WindowStyle Hidden

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
  & $py run_mpc_ctrl.py $run $setup ((2..17) -join ',') mode=mpc_bridge pitch_trim_deg=3.5 inner=8 iface_alpha_lo=0.1 cfl_max=1.5 actuator=lag2 servo_wn_rad_s=40 mpc_timeout_s=180 2>&1 | Out-Null
  Log ("end $run : " + (Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue))
  New-Item "$case\MPC_STOP" -ItemType File -Force | Out-Null; Start-Sleep 5
  Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*mpc_bridge_server.py*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue }
}

# --- woda spokojna: opor vs wysokosc lotu ---
foreach ($run in @('OVS_CALM_Z-0.3', 'OVS_CALM_Z-0.6')) {
  if (Done $run) { Log "$run juz skonczony"; continue }
  $zr = $run.Substring(10); $calm = 'T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset\CALM\GODO_OVERSET_SETUP_CALM.sim'
  Log "start $run (woda spokojna, z_ref $zr m)"
  & $py run_overset_ctrl.py $run $calm ((2..17) -join ',') mode=pid kp_deg_per_m=6.63 ki_deg_per_m_s=1.18 "z_ref_m=$zr" t_end_s=8.0 release_s=1.0 pitch_trim_deg=3.5 inner=8 iface_alpha_lo=0.1 cfl_max=1.5 actuator=lag2 servo_wn_rad_s=40 2>&1 | Out-Null
  Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}

$S = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\strut_calm'
Add-Content "$S\strut_chain.log" ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' queue4 skonczona - start h=0.7, 1.5')
$p = Start-Process -FilePath 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe' -ArgumentList '-X','utf8','strut_chain.py','0.7,1.5' -WorkingDirectory $S -WindowStyle Hidden -PassThru
Start-Sleep 2; try { $p.ProcessorAffinity = [IntPtr](1 -shl 23) } catch {}
Log 'koniec kolejki (wspornik h0.7/1.5 wystartowany)'
