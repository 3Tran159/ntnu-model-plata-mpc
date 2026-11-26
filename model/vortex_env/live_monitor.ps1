# live_monitor.ps1 - podglad treningu: serwer http://127.0.0.1:8793/TRAINING_LIVE.html + odswiezanie obrazow co ~5 min (rdzen 21, priorytet Idle)
$here = "T:\NTNU_GODO_CONTROL_20261109\50_learning\vortex_env"; Set-Location $here
$py = "T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe"
$srv = Start-Process -FilePath $py -ArgumentList '-m','http.server','8793','--bind','127.0.0.1' -WorkingDirectory $here -WindowStyle Hidden -PassThru
while ($true) {
  if (-not (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.CommandLine -like '*train_rl*' })) { break }
  $p = Start-Process -FilePath $py -ArgumentList '-X','utf8','plot_training.py' -WorkingDirectory $here -NoNewWindow -PassThru -RedirectStandardOutput "$here\live_monitor.out" -RedirectStandardError "$here\live_monitor.err"
  try { $p.ProcessorAffinity = [IntPtr](1 -shl 21); $p.PriorityClass = 'Idle' } catch {}
  Start-Sleep 2; Get-CimInstance Win32_Process | ? { $_.ParentProcessId -eq $p.Id } | % { try { $c = Get-Process -Id $_.ProcessId; $c.ProcessorAffinity = [IntPtr](1 -shl 21); $c.PriorityClass = 'Idle' } catch {} }
  $p.WaitForExit()
  Start-Sleep 240
}
