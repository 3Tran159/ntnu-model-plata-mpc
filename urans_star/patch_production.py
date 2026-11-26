"""BuildGodoCase.java: native production reports (interface CFL, wave gauges) before the setup is saved."""
p = r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\BuildGodoCase.java"
t = open(p, encoding="utf-8").read()
assert "productionReports" not in t
old = '   yplusReports(bnd.get("main"),bnd.get("flap"));'
assert old in t
t = t.replace(old, old + '\n   productionReports(region,yfs,y0);', 1)
m = r'''
 /** Native: max interface Courant number (cells with 0.01<alpha<0.99) and wave gauges eta(x) from a vertical plane:
  *  eta = (integral of water volume fraction over the plane)/span + y_bottom - y_calm.  Gauges: lambda/4 upstream, LE, hinge. */
 void productionReports(Region region,double yfs,double y0){
  UserFieldFunction ic=s.getFieldFunctionManager().createFieldFunction();ic.setPresentationName("GODO_interface_Courant");ic.setFunctionName("GODO_interface_Courant");
  ic.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);ic.setDefinition("($VolumeFractionwater>0.01 && $VolumeFractionwater<0.99) ? $CourantNumber : 0");
  MaxReport cf=s.getReportManager().createReport(MaxReport.class);cf.setPresentationName("GODO_interfaceCFL");cf.setFieldFunction(ic);cf.getParts().setObjects(region);
  List<Monitor> ms=new ArrayList<>();
  double lam=d("lambda_m",39.03274979328733);
  double[][] gx={{-lam/4},{0},{0.8*d("chord_m",.312)}};
  String[] gn={"GODO_eta_upstream_quarter_lambda","GODO_eta_at_LE","GODO_eta_at_hinge"};
  for(int k=0;k<3;k++){
   PlaneSection pl=s.getPartManager().createPlaneSection();pl.setPresentationName(gn[k]+" plane");pl.getInputParts().setObjects(region);
   pl.setOrigin(new DoubleVector(new double[]{gx[k][0],0,.01}));pl.setOrientation(new DoubleVector(new double[]{1,0,0}));
   SurfaceIntegralReport si=s.getReportManager().createReport(SurfaceIntegralReport.class);si.setPresentationName(gn[k]+"_SI");si.setFieldFunction(ff("VolumeFractionwater"));si.getParts().setObjects(pl);si.setSmooth(false);
   ExpressionReport e=s.getReportManager().createReport(ExpressionReport.class);e.setPresentationName(gn[k]);
   e.setDefinition("${"+gn[k]+"_SIReport}/<0.02 m>+<"+y0+" m>-<"+yfs+" m>");
   ReportMonitor rm=e.createMonitor();rm.setPresentationName(gn[k]+" Monitor");
   try{rm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable x){}
   ms.add(rm);
  }
  ReportMonitor cm=cf.createMonitor();cm.setPresentationName("GODO_interfaceCFL Monitor");
  try{cm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable x){}
  try{s.getPlotManager().createMonitorPlot(ms,"GODO wave gauges eta [m]");s.getPlotManager().createMonitorPlot(List.of(cm),"GODO interface Courant");}catch(Throwable x){}
  for(String n:new String[]{"AF_CL","AF_CD","AF_Mh"})
   try{for(Object o:s.getMonitorManager().getObjects())if(o instanceof ReportMonitor r&&r.getReport().getPresentationName().equals(n))r.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable x){}
 }
'''
anchor = " double metric(String name,NamedObject part,boolean minimum){"
assert anchor in t
t = t.replace(anchor, m + anchor, 1)
open(p, "w", encoding="utf-8").write(t)
print("ok")
