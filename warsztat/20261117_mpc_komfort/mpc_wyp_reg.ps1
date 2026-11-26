# 19.11: seria MPC z kara za wypadkowa na fali Godo (model), po kolei na jednym rdzeniu. Log: mpc_wyp.log, wynik: WYPADKOWA_MPC.json
$w = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort'
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
Set-Location $w
foreach ($a in @(@('2.2','21','0'), @('2.2','21'), @('1.5','21'), @('3','21'), @('2','21'), @('1.8','21'))) {
    & $py mpc_wyp.py reg @a *>> "$w\mpc_wyp.log"
}
