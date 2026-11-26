# strut_after_policies.ps1 - wspornik h = 0,7 i 1,5 m na GPU DOPIERO po zakonczeniu kolejki polityk w URANS
# (12.11: przebieg na GPU spowalnial rownolegly URANS na CPU z ~1,4 do ~2,0 s/krok). Te same ustawienia co h = 1,09 m.
$S = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\strut_calm'
while (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*policy_queue.ps1*' }) { Start-Sleep 300 }
Add-Content "$S\strut_chain.log" ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' kolejka polityk skonczona - start h=0.7, 1.5')
$p = Start-Process -FilePath 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe' -ArgumentList '-X','utf8','strut_chain.py','0.7,1.5' -WorkingDirectory $S -WindowStyle Hidden -PassThru
Start-Sleep 2; try { $p.ProcessorAffinity = [IntPtr](1 -shl 23) } catch {}
