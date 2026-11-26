# start_widmo.ps1 - 13.11.2026 (zgoda Julka 18:30): Krok 3 na widmie S1-S4 w modelu Faltinsena, 6 procesow na rdzeniach 18-23 (STAR 2-17, POL32 0-1 nietkniete).
# Wznowienie: uruchom ponownie (gotowe przebiegi sa pomijane). Zatrzymanie: utworz plik STOP w tym katalogu. Log: widmo.log
$here = 'T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI\WIDMO_S1S4'; $py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
Add-Content "$here\widmo.log" ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' start_widmo: 6 procesow')
foreach ($k in 0..5) { Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',"$here\widmo_s1s4.py",'worker',"$k",'6' -WorkingDirectory $here -WindowStyle Hidden }
Start-Process -FilePath $py -ArgumentList 'T:\NTNU_GODO_CONTROL_20261109\20_supervisor\keep_awake_while.py','widmo_s1s4.py worker','15' -WindowStyle Hidden
