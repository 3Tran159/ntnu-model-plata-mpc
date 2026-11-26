$here = "T:\NTNU_GODO_CONTROL_20261109\50_learning\vortex_env"; Set-Location $here
$py = "T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe"
function Pin($p, $mask, $prio) { try { $p.ProcessorAffinity = [IntPtr]$mask; $p.PriorityClass = $prio } catch {}; Start-Sleep 2; Get-CimInstance Win32_Process | ? { $_.ParentProcessId -eq $p.Id } | % { try { $c = Get-Process -Id $_.ProcessId; $c.ProcessorAffinity = [IntPtr]$mask; $c.PriorityClass = $prio } catch {} } }
# 1. przeglad zawieszenie x sterowanie x glebokosc (rdzen 21)
$p = Start-Process -FilePath $py -ArgumentList '-X','utf8','susp_mpc.py' -WorkingDirectory $here -NoNewWindow -PassThru -RedirectStandardOutput "$here\susp_mpc.out" -RedirectStandardError "$here\susp_mpc.err"
Pin $p (1 -shl 21) 'BelowNormal'
# 2. po zakonczeniu TD3_GODO (stara nagroda) -> TD3_C z nagroda v2 (rdzenie 18-19)
while (-not (Test-Path "$here\runs\TD3_GODO\DONE")) { Start-Sleep 60 }
Add-Content "$here\night_chain.log" ((Get-Date -f s) + " TD3_GODO DONE -> start TD3_C")
powershell -NoProfile -ExecutionPolicy Bypass -File "$here\start_training.ps1" -Jobs "td3:TD3_C:0x3:18"
