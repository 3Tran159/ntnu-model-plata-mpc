# start_training.ps1 - uruchamia (lub wznawia) treningi w modelu wirowym, kazdy w petli nadzorczej.
# Rdzenie: TD3 18-19, SAC 20-21 (STAR 2-17, POL32 0-1, kalibracja 22-23 nietkniete).
# Zatrzymanie: plik runs\<TAG>\STOP (zapis stanu i wyjscie). Wznowienie: uruchom ten skrypt ponownie.
param([string[]]$Jobs = @("td3:TD3_GODO:0x3:18", "sac:SAC_B:0x3:20"))
$here = "T:\NTNU_GODO_CONTROL_20261109\50_learning\vortex_env"
$py = "T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe"
foreach ($j in $Jobs) {
    $alg, $tag, $mask, $shift = $j.Split(":")
    $run = Join-Path $here "runs\$tag"; New-Item -ItemType Directory -Force $run | Out-Null
    $sup = @"
`$env:TORCH_THREADS='2'
while (-not (Test-Path '$run\DONE') -and -not (Test-Path '$run\STOP')) {
  Add-Content '$run\supervisor.log' ("{0} start" -f (Get-Date -f s))
  `$p = Start-Process -FilePath '$py' -ArgumentList '-X','utf8','$here\train_rl.py','$alg','$tag' -WorkingDirectory '$here' -NoNewWindow -PassThru -RedirectStandardOutput '$run\stdout.log' -RedirectStandardError '$run\stderr.log'
  `$p.ProcessorAffinity = [IntPtr]([int64]$mask -shl $shift)
  `$p.PriorityClass = 'BelowNormal'
  # .venv\python.exe to tylko launcher: wlasciwy interpreter jest procesem potomnym i NIE dziedziczy przypiecia - przypinamy go osobno
  Start-Sleep 3; Get-CimInstance Win32_Process | ? { `$_.ParentProcessId -eq `$p.Id } | % { try { `$c = Get-Process -Id `$_.ProcessId; `$c.ProcessorAffinity = `$p.ProcessorAffinity; `$c.PriorityClass = 'BelowNormal' } catch {} }
  `$p.WaitForExit()
  Add-Content '$run\supervisor.log' ("{0} exit {1}" -f (Get-Date -f s), `$p.ExitCode)
  Start-Sleep 20
}
"@
    $f = Join-Path $run "supervise.ps1"; Set-Content -Path $f -Value $sup -Encoding UTF8
    Start-Process powershell -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $f -WindowStyle Hidden
    Write-Output "uruchomiono $tag ($alg) na rdzeniach od $shift"
}
