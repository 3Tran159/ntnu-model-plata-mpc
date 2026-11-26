p = r"T:\NTNU_GODO_CONTROL_20261109\10_macros\GodoControl.java"
t = open(p, encoding="utf-8").read()
old = '   case "map": case "pimap":{'
assert old in t and 'case "prbs"' not in t
new = r'''   case "prbs":{ // band-limited random excitation for system identification (deterministic in t -> restart-safe)
    double e=Math.max(0,t+tick-d("start_time_s",0)), K=d("prbs_knot_s",0.04), Ko=d("prbs_offset_knot_s",0.25);
    long seed=(long)d("prbs_seed",1);
    long k=(long)Math.floor(e/K), ko=(long)Math.floor(e/Ko);
    double a0=knot(seed,k), a1=knot(seed,k+1), f=smoothValue(e/K-k);
    double o0=knot(seed+7919,ko), o1=knot(seed+7919,ko+1), fo=smoothValue(e/Ko-ko);
    double ramp=smoothValue(e/d("prbs_ramp_s",0.1));
    return ramp*(d("prbs_amp_deg",1.0)*(a0+(a1-a0)*f)+d("prbs_offset_amp_deg",0.0)*(o0+(o1-o0)*fo));
   }
   case "map": case "pimap":{'''
t = t.replace(old, new, 1)
helper_anchor = " double smoothValue(double x){"
assert helper_anchor in t
t = t.replace(helper_anchor, " static double knot(long seed,long k){return new java.util.Random(seed*1000003L+k*7777777L).nextDouble()*2-1;}\n" + helper_anchor, 1)
open(p, "w", encoding="utf-8").write(t)
print("prbs mode added")
