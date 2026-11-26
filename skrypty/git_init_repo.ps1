# Jednorazowe: inicjalizacja repo git i pierwszy commit (autor: noreply GitHuba).
$g = 'C:\Program Files\Git\cmd\git.exe'
Set-Location (Split-Path $PSScriptRoot -Parent)
& $g init -q -b main
& $g config user.name 'Julek'
& $g config user.email '361491866+3Tran159@users.noreply.github.com'
& $g config core.autocrlf false
& $g add -A
& $g commit -q -m "NTNU model plata + MPC: makra STAR overset, przebiegi URANS, model wirowy 2D i Faltinsen, MPC, zawieszenie, widmo S1-S4 (stan 26.11.2026)"
& $g log --format="%h %an <%ae> %s" -1
