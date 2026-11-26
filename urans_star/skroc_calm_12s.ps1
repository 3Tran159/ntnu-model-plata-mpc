# skroc_calm_12s.ps1 - 19.11 10:52 (koordynator, zgoda Julka 10:50 "skracamy przebiegi").
# Konczy przebiegi wody spokojnej kolejki 18 przy t = 12 s (plik STOP -> HOLD_STOP_FILE, stan koncowy; kolejka 18 idzie dalej).
# Okno porownania z OVS_CALM_90: 6-12 s. Wznowienie do 20 s mozliwe pozniej z punktu zapisu. Log: skroc_calm_12s.log.
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
function Log($m){ Add-Content skroc_calm_12s.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'start straznika'
foreach ($tag in @('OVS_CALM_90_Z-0.3', 'OVS_CALM_90_Z-0.6')) {
  $d = "overset_runs\$tag"
  while ($true) {
    if (Test-Path "$d\RUN_RESULT.json") { Log "$tag ma juz RUN_RESULT - pomijam"; break }
    $t = 0.0
    try { $t = [double]((Get-Content "$d\RUN_STATE.json" -Raw -EA Stop | ConvertFrom-Json).time_s) } catch { }
    if ($t -ge 9.0) { Set-Content "$d\STOP" 'skrocone do 9 s (19.11 13:55: woda spokojna, okno 6-9 s wystarcza; miejsce dla OVS_LEVEL_90)'; Log "$tag t = $t s -> STOP"; break }
    if (-not (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*policy_queue18*' })) { Log 'kolejka 18 nie dziala - koniec straznika'; exit }
    Start-Sleep 60
  }
  while (-not (Test-Path "$d\RUN_RESULT.json")) { Start-Sleep 30 }
}
Log 'koniec straznika'

