# start_k3w_po_k3.ps1 - agent D, 13.11 23:55, zlecenie D-Z4: uruchamia k3_wiener.py (4 przypadki x S1-S4 x 5 realizacji) na rdzeniach 18-23,
# DOPIERO gdy nocny K3 jest skonczony: w K3_WIDMO\wyniki jest 160 plikow i nie dziala zaden proces 'k3_widmo.py worker'.
# Kolejnosc: (1) projekt filtrow Wienera d = 3 i 6 m (jeden proces, rdzen 18) - zeby 6 workerow nie liczylo ich naraz; (2) 6 workerow (rdzenie 18-23, priorytet ponizej normalnego).
# Wznowienie: uruchom ponownie (worker pomija gotowe pliki, filtr czytany z pliku). Stop: plik K3_WIENER\STOP. Log: K3_WIENER\k3_wiener.log. Nic nie kasuje.
$here = 'T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI\ZAWIESZENIE'; $py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
New-Item -ItemType Directory -Force "$here\K3_WIENER" | Out-Null
$log = "$here\K3_WIENER\k3_wiener.log"
function L($s) { Add-Content $log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' start_k3w: ' + $s) }
function K3Done() {
  $n = @(Get-ChildItem "$here\K3_WIDMO\wyniki" -Filter *.json -ErrorAction SilentlyContinue).Count
  $busy = [bool](Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*k3_widmo.py*worker*' })
  return (($n -ge 160) -and (-not $busy))
}
L 'czekam na koniec K3 (160 plikow w K3_WIDMO\wyniki i brak workerow k3_widmo)'
while (-not (K3Done)) { if (Test-Path "$here\K3_WIENER\STOP") { L 'STOP przed startem'; exit }; Start-Sleep 60 }
L 'K3 skonczony; projekt filtrow Wienera d = 3 i 6 m (rdzen 18)'
$p = Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',"$here\k3_wiener.py",'fir','3','6' -WorkingDirectory $here -WindowStyle Hidden -PassThru `
       -RedirectStandardOutput "$here\K3_WIENER\fir.out" -RedirectStandardError "$here\K3_WIENER\fir.err"
try { $p.PriorityClass = 'BelowNormal'; $p.ProcessorAffinity = [IntPtr](1 -shl 18) } catch {}
$p.WaitForExit()
if (-not (Test-Path "$here\K3_WIENER\FIR_ogolny_d3_s10.json") -or -not (Test-Path "$here\K3_WIENER\FIR_ogolny_d6_s10.json")) { L 'BLAD: brak plikow filtru - workerow nie startuje (patrz fir.err)'; exit }
L 'filtry gotowe; start 6 procesow k3_wiener (rdzenie 18-23)'
Start-Process -FilePath $py -ArgumentList 'T:\NTNU_GODO_CONTROL_20261109\20_supervisor\keep_awake_while.py','k3_wiener.py worker','15' -WindowStyle Hidden
foreach ($k in 0..5) { Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',"$here\k3_wiener.py",'worker',"$k",'6','18' -WorkingDirectory $here -WindowStyle Hidden }
