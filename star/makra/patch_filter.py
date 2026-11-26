p = r"T:\NTNU_GODO_CONTROL_20261109\10_macros\GodoControl.java"
t = open(p, encoding="utf-8").read()
def rep(old, new):
    global t
    assert old in t, "missing: " + old[:70]
    t = t.replace(old, new, 1)
# low-pass filtered CL for feedback (non-circulatory spikes from flap acceleration made raw-CL PI chatter)
rep(" double integ=0, trim=0, clWinSum=0;", " double integ=0, trim=0, clWinSum=0, clf=Double.NaN;")
rep("      double next=control(mode,t,cl,tick);",
    "      double clIn=(d(\"cl_filter_tau_s\",0)>0&&Double.isFinite(clf))?clf:cl;\n      double next=control(mode,t,clIn,tick);")
rep("     clWin.addLast(cl);",
    "     clf=Double.isFinite(clf)?clf+(cl-clf)*dt/(d(\"cl_filter_tau_s\",0)+dt):cl;\n     clWin.addLast(cl);")
rep('c.write("time_s,step,CL_in,cmd_prev_deg,cmd_next_deg,mode\\n");', 'c.write("time_s,step,CL_in,cmd_prev_deg,cmd_next_deg,mode\\n");/*CL_in is the controller input (filtered when cl_filter_tau_s>0)*/')
rep("c.write(t+\",\"+step+\",\"+cl+\",\"", "c.write(t+\",\"+step+\",\"+clIn+\",\"")
open(p, "w", encoding="utf-8").write(t)
print("ok")
