"""Keep Windows awake (no sleep; display may turn off) while any process whose command line contains PATTERN runs.
usage: python keep_awake_while.py PATTERN [grace_minutes]"""
import ctypes, subprocess, sys, time
pat = sys.argv[1]; grace = float(sys.argv[2]) if len(sys.argv) > 2 else 10
ES = 0x80000000 | 0x00000001
idle_since = None
while True:
    ctypes.windll.kernel32.SetThreadExecutionState(ES)
    out = subprocess.run(["powershell", "-NoProfile", "-Command",
                          "(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*%s*' -and $_.CommandLine -notlike '*keep_awake_while*' }).Count" % pat],
                         capture_output=True, text=True, creationflags=0x08000000).stdout.strip()
    alive = out.isdigit() and int(out) > 0
    idle_since = None if alive else (idle_since or time.time())
    if idle_since and time.time() - idle_since > grace * 60:
        break
    time.sleep(60)
ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
