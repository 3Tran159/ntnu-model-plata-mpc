"""Add native STAR power/energy reports to GodoControl.java (installed in the .sim, visible/editable in the GUI).

Sign convention (checked against the macro definitions):
  - AF_Mh: MomentReport about axis (0,0,-1) through the hinge (0.952, 0.02128) on the flap boundary.
  - delta (AF_Delta_*): positive = trailing edge down = rotation about -z  -> same sense as Mh.
  - static check: at delta = 0, Mh = -10.87 N m (water pushes the trailing edge up), physically correct for a lifting flap.
  => power delivered BY the fluid TO the flap  P_fluid = Mh * d(delta)/dt [rad/s]
     mechanical demand of the actuator (no regeneration) P_act = max(0, -Mh * d(delta)/dt)   (Godø eq. 7)
  d(delta)/dt is the commanded-interpolation rate (prev->next over one tick); in INTEGRATION_GATE the measured mesh
  angle tracks the command to 5e-8 deg with zero lag, so this equals the actual rate.
All values are for the simulated span of 0.02 m (multiply by 50 for per metre of span).
"""
p = r"T:\NTNU_GODO_CONTROL_20261109\10_macros\GodoControl.java"
t = open(p, encoding="utf-8").read()
assert "installPowerReports" not in t

method = r'''
 /** Native STAR reports/monitors/plot for flap rate, hinge power, actuator demand and drag power (per 0.02 m span). */
 void installPowerReports() throws Exception {
  if(s.getReportManager().getReport("AF_Actuator_Demand_W")!=null)return;
  UserFieldFunction rate=s.getFieldFunctionManager().createFieldFunction();
  rate.setFunctionName("AF_Cycle_Rate"); rate.setPresentationName("AF_Cycle_Rate");
  rate.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
  String tau="($Time/<1 s>-"+ref("FC_T0_s")+")";
  rate.setDefinition("(("+tau+">1e-12 && "+tau+"<="+ref("FC_Tick_s")+"+1e-9) ? ("+ref("FC_Delta_Next_deg")+"-"+ref("FC_Delta_Prev_deg")+")/"+ref("FC_Tick_s")+" : 0)");
  String[][] defs={
   {"AF_Flap_Rate_deg_s","$AF_Cycle_Rate"},
   {"AF_Hinge_Power_Fluid_W","${AF_MhReport}*$AF_Cycle_Rate*0.017453292519943295"},
   {"AF_Actuator_Demand_W","max(0,-${AF_MhReport}*$AF_Cycle_Rate*0.017453292519943295)"},
   {"AF_Drag_Power_W","18.0*${AF_FxReport}"},
   {"AF_Total_Power_W","18.0*${AF_FxReport}+max(0,-${AF_MhReport}*$AF_Cycle_Rate*0.017453292519943295)"}};
  List<Monitor> mons=new ArrayList<>();
  Map<String,Object> chk=new LinkedHashMap<>();
  for(String[] d2:defs){
   ExpressionReport r=s.getReportManager().createReport(ExpressionReport.class);
   r.setPresentationName(d2[0]); r.setDefinition(d2[1]);
   chk.put(d2[0],r.getReportMonitorValue());
   ReportMonitor m=r.createMonitor(); m.setPresentationName(d2[0]+" Monitor");
   try{m.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable e){chk.put("update_mode_warning",e.toString());}
   mons.add(m);
  }
  try{
   s.getPlotManager().createMonitorPlot(List.of(mons.get(3),mons.get(4)),"CTRL 05 - Drag power U*Fx and total power [W per 0.02 m]");
   s.getPlotManager().createMonitorPlot(List.of(mons.get(1),mons.get(2)),"CTRL 06 - Hinge power: fluid->flap and actuator demand [W per 0.02 m]");
   s.getPlotManager().createMonitorPlot(List.of(mons.get(0)),"CTRL 07 - Flap rate [deg/s]");
  }catch(Throwable e){chk.put("plot_warning",e.toString());}
  write("FC_POWER_REPORTS.json",chk);
 }
'''
anchor = " double scripted(double t){"
assert anchor in t
t = t.replace(anchor, method + anchor, 1)
old = "   if(fresh){installCommand();installMotion();}"
assert old in t
t = t.replace(old, "   if(fresh){installCommand();installMotion();}\n   installPowerReports();", 1)
# log the native power reports in history.csv too (same numbers the GUI shows)
oh = 'pFlapAbsMin_Pa,cmd_deg,meas_deg,interfaceCFL,pmin_Pa,eta_m3_m,eta_hinge_m,trim_deg\\n"'
assert oh in t
t = t.replace(oh, 'pFlapAbsMin_Pa,cmd_deg,meas_deg,interfaceCFL,pmin_Pa,eta_m3_m,eta_hinge_m,trim_deg,rate_deg_s,P_hinge_fluid_W,P_act_W,P_drag_W\\n"', 1)
orow = '+","+trim+"\\n");'
assert orow in t
t = t.replace(orow, '+","+trim+","+rd("AF_Flap_Rate_deg_s")+","+rd("AF_Hinge_Power_Fluid_W")+","+rd("AF_Actuator_Demand_W")+","+rd("AF_Drag_Power_W")+"\\n");', 1)
open(p, "w", encoding="utf-8").write(t)
print("power reports patched")
