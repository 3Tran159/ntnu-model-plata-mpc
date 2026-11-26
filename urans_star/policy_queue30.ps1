# policy_queue30.ps1 - 24.11 14:50 (Julek 14:39: "sprawdz to, zeby nie budzilo watpliwosci"). Odniesienie wody spokojnej dla OVS_CEL_005g_T8_90
# w TEJ SAMEJ domenie (overset\WAVE_T8\GODO_OVERSET_SETUP_T8_CALM.sim: ta sama siatka i strefy 25/60 m, fala 0,0001 m).
# Powod: OVS_CALM_90 (stara domena, tlumienie 47 m za platem) nie jest ustalony - opor 58,9 W (t 5 s) -> 71,0 W (t 29 s) przy stalym CL;
# wynik T8 zalezy od tego, ktory kawalek wziac (zysk 0 albo 9,7 W). Plat jak w wodzie spokojnej z kolejki 12: PID na nurzaniu, z_ref 0, release 1 s.
# t_end 34,1 s (okno T8: 17,93-34,03 s). Rdzenie 2-17, ok. 9 h. Potem wznawia kolejke 29 (plat nieruchomy na 3 glebokosciach).
# Przerwany OVS_FIX_L109_90 (zaczety 14:19) -> folder przemianowany na OVS_FIX_L109_90_przerwany (nic nie kasuje), kolejka 29 liczy go od nowa.
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue30.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'start: zatrzymuje kolejke 29 i OVS_FIX_L109_90'
Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like '*policy_queue29*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -EA SilentlyContinue; Log "zatrzymana kolejka 29 (pid $($_.ProcessId))" }
$fx = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\OVS_FIX_L109_90'
if (Test-Path $fx) { Set-Content "$fx\STOP" 'koordynator 24.11: przerwany, najpierw woda spokojna w domenie T8 (kolejka 30)' }
$t0 = Get-Date
while (Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -like '*run_mpcf_ctrl*OVS_FIX_L109_90*' }) { Start-Sleep 20; if (((Get-Date) - $t0).TotalMinutes -gt 20) { Log 'L109 nie konczy sie od 20 min - stop kolejki 30'; exit } }
Start-Sleep 30
if (Test-Path $fx) { Rename-Item $fx 'OVS_FIX_L109_90_przerwany' -EA SilentlyContinue; Log ("L109 przemianowany: " + (Test-Path ($fx + '_przerwany'))) }
$setup = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\WAVE_T8\GODO_OVERSET_SETUP_T8_CALM.sim'
$t1 = Get-Date; while (-not (Test-Path $setup)) { Start-Sleep 20; if (((Get-Date) - $t1).TotalMinutes -gt 30) { Log 'BRAK setupu T8_CALM - stop'; exit } }
Start-Sleep 20
$tag = 'OVS_CALM_T8DOM_90'; $case = "T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\$tag"
New-Item -ItemType Directory -Force $case | Out-Null; Remove-Item "$case\STOP" -EA SilentlyContinue
$c = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','mass_kg=28.17007','t_end_s=34.1','scenes=0','wake_gauges=-3.0','wave_period_s=8.0','encounter_period_s=4.0228')
Log "start $tag (woda spokojna w domenie T8, PID nurzania, z_ref 0)"
& $py run_mpcf_ctrl.py $tag $setup ((2..17) -join ',') mode=pid kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=1.0 pitch_trim_deg=2.338 @c 2>&1 | Out-File -Append "overset_runs\queue30_$tag.out" -Encoding utf8
Log ("end $tag : " + (Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue))
Log 'wznawiam kolejke 29'
Start-Process powershell -ArgumentList '-NoProfile','-ExecutionPolicy','Bypass','-File','T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\policy_queue29.ps1' -WindowStyle Hidden
Log 'koniec kolejki 30'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
