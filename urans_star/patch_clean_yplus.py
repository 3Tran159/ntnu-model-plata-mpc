"""BuildGodoCase.java: (1) remove the Mini post-processing baggage that is evaluated every iteration
(~25 duplicated NN_* report/monitor sets, plane-section gauges, tables, scenes, plots, solution histories, old parts,
old mesh operations, unused flat waves) - this starved the GPU (49 % utilisation, 9.3 s/step = same as CPU-2);
(2) y+ for wall functions: prism layers ABSOLUTE (constant across the mesh study, standard with wall functions),
first-layer centroid y+ ~ 50 (range 30-70): Re_c = 3.85e6, Cf(ITTC) = 0.00357, u_tau = 0.522 m/s, nu = 1e-6 m2/s
-> first layer 0.19 mm, 3 layers x stretching 1.18 -> total 0.679 mm;
(3) native y+ reports on the foil (min / area-mean / max / area fraction in 30-70) with monitors;
(4) AF monitors sampled once per time step (not every inner iteration).
"""
p = r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\BuildGodoCase.java"
t = open(p, encoding="utf-8").read()
assert "void cleanup(" not in t


def rep(old, new):
    global t
    assert old in t, "missing: " + old[:80]
    t = t.replace(old, new, 1)


rep('   stage="mesh";', '   stage="cleanup";\n   cleanup(domain);\n   stage="mesh";')
rep('   a.getDefaultValues().get(PrismThickness.class).setRelativeSize(100*.000169);',
    '   a.getDefaultValues().get(PrismThickness.class).setAbsoluteSize(d("prism_total_m",6.79e-4),m);   // y+ ~50, fixed for all meshes')
rep('   s.saveState(out.resolve("GODO_SETUP_B"+B+".sim").toString());',
    '   yplusReports(bnd.get("main"),bnd.get("flap"));\n   s.saveState(out.resolve("GODO_SETUP_B"+B+".sim").toString());')
# probe history: add y+
rep('h.write("step,time_s,solver_s,CL,CD,Fx_N,Fz_N,interfaceCFL,pmin_Pa\\n");',
    'h.write("step,time_s,solver_s,CL,CD,Fx_N,Fz_N,interfaceCFL,pmin_Pa,yplus_min,yplus_mean,yplus_max,yplus_frac_30_70\\n");')
rep('+","+cfl+","+pmin+"\\n"); h.flush();',
    '+","+cfl+","+pmin+","+rv("GODO_yplus_min")+","+rv("GODO_yplus_mean")+","+rv("GODO_yplus_max")+","+rv("GODO_yplus_frac_30_70")+"\\n"); h.flush();')

methods = r'''
 double rv(String n){try{return s.getReportManager().getReport(n).getReportMonitorValue();}catch(Throwable e){return Double.NaN;}}
 /** remove obj from whichever manager owns it (reflection: removeObjects / remove / deleteChildren); false if refused (still referenced) */
 boolean drop(Object mgr,Object obj){
  for(String mth:new String[]{"removeObjects","remove","deleteChildren"}){
   for(java.lang.reflect.Method mm:mgr.getClass().getMethods()){
    if(!mm.getName().equals(mth)||mm.getParameterCount()!=1)continue;
    try{
     Class<?> pt=mm.getParameterTypes()[0];
     if(pt.isArray()){Object arr=java.lang.reflect.Array.newInstance(pt.getComponentType(),1);java.lang.reflect.Array.set(arr,0,obj);mm.invoke(mgr,arr);}
     else if(Collection.class.isAssignableFrom(pt))mm.invoke(mgr,List.of(obj));
     else if(pt.isInstance(obj))mm.invoke(mgr,obj);
     else continue;
     return true;
    }catch(Throwable e){}
   }
  }
  return false;
 }
 boolean keepReport(String n){
  return n.startsWith("AF_")||n.equals("NN_interfaceCFL")||n.equals("NN_pmin")||n.equals("NN_CFL")||n.equals("NN_pflap")||n.equals("NN_pbody");
 }
 void cleanup(GeometryPart keep){
  Map<String,Integer> c=new LinkedHashMap<>();
  int k=0;
  for(Object o:new ArrayList<>(s.getSceneManager().getObjects()))if(drop(s.getSceneManager(),o))k++; c.put("scenes",k);k=0;
  for(Object o:new ArrayList<>(s.getPlotManager().getObjects()))if(drop(s.getPlotManager(),o))k++; c.put("plots",k);k=0;
  for(Object o:new ArrayList<>(s.getTableManager().getObjects()))if(drop(s.getTableManager(),o))k++; c.put("tables",k);k=0;
  for(Object o:new ArrayList<>(s.get(SolutionViewManager.class).getObjects()))if(drop(s.get(SolutionViewManager.class),o))k++; c.put("solution_views",k);k=0;
  for(Object o:new ArrayList<>(s.get(SolutionHistoryManager.class).getObjects()))if(drop(s.get(SolutionHistoryManager.class),o))k++; c.put("solution_histories",k);k=0;
  for(Object o:new ArrayList<>(s.getMonitorManager().getObjects())){
   if(o instanceof ResidualMonitor)continue;
   if(o instanceof ReportMonitor rm&&keepReport(rm.getReport().getPresentationName()))continue;
   if(drop(s.getMonitorManager(),o))k++;
  }
  c.put("monitors",k);k=0;
  for(int pass=0;pass<6;pass++){int n=0;
   for(Object o:new ArrayList<>(s.getReportManager().getObjects())){Report r=(Report)o;if(keepReport(r.getPresentationName()))continue;if(drop(s.getReportManager(),r))n++;}
   k+=n; if(n==0)break;}
  c.put("reports",k);k=0;
  for(int pass=0;pass<4;pass++){int n=0;
   for(Object o:new ArrayList<>(s.getPartManager().getObjects()))if(drop(s.getPartManager(),o))n++;
   k+=n; if(n==0)break;}
  c.put("derived_parts",k);k=0;
  for(Object o:new ArrayList<>(s.get(MeshOperationManager.class).getObjects()))if(drop(s.get(MeshOperationManager.class),o))k++; c.put("mesh_operations",k);k=0;
  for(Object o:new ArrayList<>(s.get(SimulationPartManager.class).getLeafParts()))if(o!=keep&&drop(s.get(SimulationPartManager.class),o))k++; c.put("geometry_parts",k);k=0;
  for(int pass=0;pass<3;pass++){int n=0;
   for(Object o:new ArrayList<>(s.getFieldFunctionManager().getObjects()))if(o instanceof UserFieldFunction u&&!u.getPresentationName().startsWith("AF_")&&!u.getPresentationName().startsWith("CB_")&&drop(s.getFieldFunctionManager(),u))n++;
   k+=n; if(n==0)break;}
  c.put("user_field_functions",k);k=0;
  try{VofWaveModel vm=s.getRegionManager().getRegion("MINI_water_air").getPhysicsContinuum().getModelManager().getModel(VofWaveModel.class);
   for(Object o:new ArrayList<>(vm.getVofWaveManager().getObjects()))if(drop(vm.getVofWaveManager(),o))k++;}catch(Throwable e){}
  c.put("vof_waves",k);
  for(Object o:s.getMonitorManager().getObjects())
   if(o instanceof ReportMonitor rm)try{rm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable e){}
  c.put("reports_left",s.getReportManager().getObjects().size());c.put("monitors_left",s.getMonitorManager().getObjects().size());
  log.put("cleanup",c);
 }
 void yplusReports(Boundary main,Boundary flap){
  List<Boundary> w=List.of(main,flap);
  MinReport mn=s.getReportManager().createReport(MinReport.class);mn.setPresentationName("GODO_yplus_min");mn.setFieldFunction(ff("WallYplus"));mn.getParts().setObjects(w);
  MaxReport mx=s.getReportManager().createReport(MaxReport.class);mx.setPresentationName("GODO_yplus_max");mx.setFieldFunction(ff("WallYplus"));mx.getParts().setObjects(w);
  AreaAverageReport av=s.getReportManager().createReport(AreaAverageReport.class);av.setPresentationName("GODO_yplus_mean");av.setFieldFunction(ff("WallYplus"));av.getParts().setObjects(w);
  UserFieldFunction in=s.getFieldFunctionManager().createFieldFunction();in.setPresentationName("GODO_yplus_in_30_70");in.setFunctionName("GODO_yplus_in_30_70");
  in.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);in.setDefinition("($WallYplus>=30 && $WallYplus<=70) ? 1 : 0");
  AreaAverageReport fr=s.getReportManager().createReport(AreaAverageReport.class);fr.setPresentationName("GODO_yplus_frac_30_70");fr.setFieldFunction(in);fr.getParts().setObjects(w);
  List<Monitor> ms=new ArrayList<>();
  for(Report r:List.of(mn,mx,av,fr)){ReportMonitor rm=r.createMonitor();rm.setPresentationName(r.getPresentationName()+" Monitor");
   try{rm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP);}catch(Throwable e){}ms.add(rm);}
  try{s.getPlotManager().createMonitorPlot(ms,"GODO y+ on the foil (target 30-70)");}catch(Throwable e){log.put("yplus_plot_warning",e.toString());}
 }
'''
anchor = " double metric(String name,NamedObject part,boolean minimum){"
rep(anchor, methods + anchor)
open(p, "w", encoding="utf-8").write(t)
print("patched")
