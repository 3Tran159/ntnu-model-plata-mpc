package macro;
import star.motion.*;import star.meshing.*;import star.common.*;import star.vis.*;import star.post.*;import star.metrics.*;import star.base.neo.*;import star.base.report.*;import star.flow.*;import star.material.*;import star.segregatedflow.*;import star.turbulence.*;import star.kwturb.*;import star.vof.*;import star.mixturemultiphase.*;import star.vis.*;import java.nio.file.*;import java.io.*;import java.util.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * GodoControl - native, GUI-editable flap controller for the Mini-VOF sealed-flap case.
 *
 * Everything the controller touches lives in the .sim and is editable in STAR-CCM+:
 *   Global Parameters  FC_Delta_Prev_deg, FC_Delta_Next_deg, FC_T0_s, FC_Tick_s
 *   Field function     AF_Cycle_Command  (linear interpolation Prev -> Next over one tick; [deg])
 *   Motion             "Godo flap controller motion" (User Defined Vertex Motion, total displacement)
 *   Reports/monitors   AF_Delta_Command_deg (commanded), AF_Delta_Measured_deg (mesh angle)
 * This macro only (1) installs those objects if missing, (2) every tick reads reports, computes the
 * command, applies rate/range limits and writes the two parameters, (3) steps the solver and logs.
 * Settings come from MINI_CASE_DIR/control.properties.
 */
public class GodoControl extends StarMacro {
 Simulation s; Path out; Properties cfg=new Properties();
 Region reg; List<Boundary> flapB=new ArrayList<>();
 final double HX=.952, HY=.02128173276777;
 ScalarGlobalParameter pPrev,pNext,pT0,pTick;
 String refStyle="Parameter";
 double d(String k,double v){return Double.parseDouble(cfg.getProperty(k,""+v));}
 int i(String k,int v){return Integer.parseInt(cfg.getProperty(k,""+v));}
 String str(String k,String v){return cfg.getProperty(k,v);}
 static String q(String x){return "\""+x.replace("\\","/").replace("\"","'")+"\"";}
 String json(Object a){
  if(a==null)return "null";
  if(a instanceof Number){double x=((Number)a).doubleValue();return Double.isFinite(x)?a.toString():"null";}
  if(a instanceof Boolean)return a.toString();
  if(a instanceof Map<?,?> m){StringBuilder b=new StringBuilder("{");boolean f=true;for(Map.Entry<?,?> e:m.entrySet()){if(!f)b.append(",");f=false;b.append(q(String.valueOf(e.getKey()))).append(":").append(json(e.getValue()));}return b.append("}").toString();}
  if(a instanceof Collection<?> c){StringBuilder b=new StringBuilder("[");boolean f=true;for(Object o:c){if(!f)b.append(",");f=false;b.append(json(o));}return b.append("]").toString();}
  return q(String.valueOf(a));
 }
 void write(String name,Object v)throws Exception{Path p=out.resolve(name),t=out.resolve(name+".tmp");Files.writeString(t,json(v));Files.move(t,p,StandardCopyOption.REPLACE_EXISTING);}
 FieldFunction ff(String n){FieldFunction f=s.getFieldFunctionManager().getFunction(n);if(f==null)throw new IllegalStateException("Missing field function "+n);return f;}
 Report rp(String n){Report r=s.getReportManager().getReport(n);if(r==null)throw new IllegalStateException("Missing report "+n);return r;}
 double rd(String n){return rp(n).getReportMonitorValue();}
 double clamp(double x,double lo,double hi){return Math.max(lo,Math.min(hi,x));}
 String smooth(String e){String c="max(0,min(1,"+e+"))";return "(pow("+c+",3)*(10-15*"+c+"+6*pow("+c+",2)))";}

 ScalarGlobalParameter param(String name){
  GlobalParameterManager gm=s.get(GlobalParameterManager.class);
  for(Object o:gm.getObjects())if(o instanceof ScalarGlobalParameter p&&p.getPresentationName().equals(name))return p;
  ScalarGlobalParameter p=(ScalarGlobalParameter)gm.createGlobalParameter(ScalarGlobalParameter.class,"Scalar");
  p.setPresentationName(name);return p;
 }
 void set(ScalarGlobalParameter p,double v){p.getQuantity().setValue(v);}
 String ref(String name){return "${"+name+refStyle+"}";}

 /** Create (or re-use) the command field function; verify by evaluating it. */
 void installCommand() throws Exception {
  pPrev=param("FC_Delta_Prev_deg");pNext=param("FC_Delta_Next_deg");pT0=param("FC_T0_s");pTick=param("FC_Tick_s");
  UserFieldFunction cmd=null;
  for(FieldFunction f:s.getFieldFunctionManager().getObjects())if(f instanceof UserFieldFunction u&&u.getPresentationName().equals("AF_Cycle_Command"))cmd=u;
  if(cmd==null){cmd=s.getFieldFunctionManager().createFieldFunction();cmd.setFunctionName("AF_Cycle_Command");cmd.setPresentationName("AF_Cycle_Command");cmd.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);}
  String last="";
  for(String style:new String[]{"Parameter",""}){
   refStyle=style;
   try{
    cmd.setDefinition(ref("FC_Delta_Prev_deg")+"+("+ref("FC_Delta_Next_deg")+"-"+ref("FC_Delta_Prev_deg")+")*max(0,min(1,($Time/<1 s>-"+ref("FC_T0_s")+")/"+ref("FC_Tick_s")+"))");
    set(pPrev,0.123);set(pNext,0.123);set(pT0,0);set(pTick,1);
    ExpressionReport chk=s.getReportManager().createReport(ExpressionReport.class);chk.setPresentationName("FC_check_command");chk.setDefinition("$AF_Cycle_Command");
    double v=chk.getReportMonitorValue();s.getReportManager().remove(chk);
    if(Math.abs(v-0.123)<1e-9){last="ok:"+style;break;}
    last="value "+v+" with style '"+style+"'";
   }catch(Throwable e){last=e.toString()+" with style '"+style+"'";refStyle="?";}
  }
  if(!last.startsWith("ok"))throw new IllegalStateException("Command field function failed readback: "+last);
  set(pPrev,0);set(pNext,0);set(pT0,d("start_time_s",0));set(pTick,d("tick_steps",10)*d("dt_s",5e-4));
  write("FC_INSTALL_COMMAND.json",Map.of("ok",true,"reference_style",refStyle.isEmpty()?"${Name}":"${NameParameter}","definition",cmd.getDefinition()));
 }

 void installMotion() throws Exception {
  if(!(s.get(MotionManager.class).getObjects().size()==1))throw new IllegalStateException("Unexpected motion set (expected only Stationary)");
  UserDefinedVertexMotion motion=s.get(MotionManager.class).createMotion(UserDefinedVertexMotion.class,"Godo flap controller motion");
  reg.getValues().get(MotionSpecification.class).setMotion(motion);
  UserDefinedVertexMotionSolver solver=s.getSolverManager().getSolver(UserDefinedVertexMotionSolver.class);
  solver.setIgnoreGridFlux(false);solver.setZeroGridFlux(false);solver.setUpdateInnerIterations(false);
  ff("SavedCoord");
  String x="($$SavedCoord[0]-<"+HX+" m>)", y="($$SavedCoord[1]-<"+HY+" m>)";
  String radius="sqrt(pow("+x+",2)+pow("+y+",2))";
  String blend=smooth(x+"/<.035 m>");
  String a="($AF_Cycle_Command*0.017453292519943295*"+blend+"*"+smooth("(<1.40 m>-"+radius+")/<1.10 m>")+")";
  UserFieldFunction f=s.getFieldFunctionManager().createFieldFunction();
  f.setFunctionName("CB_FlapTotalDisplacement");f.setPresentationName("CB_FlapTotalDisplacement");
  f.getTypeOption().setSelected(FieldFunctionTypeOption.Type.VECTOR);
  Dimensions length=new Dimensions();length.setLength(1);f.setDimensions(length);
  f.setDefinition("["+x+"*(cos("+a+")-1)+"+y+"*sin("+a+"),-"+x+"*sin("+a+")+"+y+"*(cos("+a+")-1),<0 m>]");
  reg.getConditions().get(MovingVertexOption.class).setSelected(MovingVertexOption.Type.TOTAL_DISPLACEMENT);
  VertexDisplacementProfile profile=reg.getValues().get(VertexDisplacementProfile.class);
  profile.setTotalDisplacement(true);
  profile.setMethod(FunctionVectorProfileMethod.class);
  profile.getMethod(FunctionVectorProfileMethod.class).setFieldFunction(f);
  // reports: commanded vs actual (mesh) angle
  ((ExpressionReport)rp("AF_Delta_Command_deg")).setDefinition("$AF_Cycle_Command");
  UserFieldFunction angle=s.getFieldFunctionManager().createFieldFunction();
  angle.setFunctionName("AF_Aft_Mesh_Angle");angle.setPresentationName("AF_Aft_Mesh_Angle");angle.getTypeOption().setSelected(FieldFunctionTypeOption.Type.SCALAR);
  String xs="($$SavedCoord[0]-<"+HX+" m>)", ys="($$SavedCoord[1]-<"+HY+" m>)";
  String px="($$Position[0]-<"+HX+" m>)", py="($$Position[1]-<"+HY+" m>)";
  angle.setDefinition("("+xs+">.20) ? -57.29577951308232*atan(("+xs+"*"+py+"-"+ys+"*"+px+")/("+xs+"*"+px+"+"+ys+"*"+py+")) : -999");
  MaxReport measured=s.getReportManager().createReport(MaxReport.class);
  measured.setPresentationName("AF_Mesh_Angle");measured.setSmooth(false);
  measured.setFieldFunction(angle);measured.getParts().setObjects(flapB);
  ((ExpressionReport)rp("AF_Delta_Measured_deg")).setDefinition("${AF_Mesh_AngleReport}");
 }

 double scripted(double t){ // integration test: hold, ramp +, hold, ramp -, hold  (deg)
  double e=t-d("start_time_s",0),A=d("test_amp_deg",1.0);
  if(e<0.02)return 0; if(e<0.06)return A; if(e<0.12)return A; if(e<0.16)return -A; return -A;
 }

 double integ=0, trim=0, clWinSum=0, clf=Double.NaN;
 ArrayDeque<Double> clWin=new ArrayDeque<>();
 SolutionHistory hist=null; boolean playbackOn=false;
 double smoothValue(double x){double q=clamp(x,0,1);return q*q*q*(10-15*q+6*q*q);}
 double eta(String area,String gauge){
  try{return (rd(gauge)-rd(area))/0.02+4-2.02128173276777;}catch(Throwable e){return Double.NaN;}
 }
 /** Best-effort native playback: recorded solution history + scene + monitor plots (CFD continues if it fails). */
 void setupPlayback(){
  try{
   PlaneSection plane=s.getPartManager().createPlaneSection();
   plane.setPresentationName("CTRL - midspan section");plane.getInputParts().setObjects(reg);
   plane.setOrigin(new DoubleVector(new double[]{0,0,.01}));plane.setOrientation(new DoubleVector(new double[]{0,0,1}));
   hist=s.get(SolutionHistoryManager.class).createForFile(out.resolve("CTRL_playback.simh").toAbsolutePath().toString(),false);
   hist.setPresentationName("CTRL - flap motion history");hist.setAutoRecord(false);hist.setAutoRescan(true);
   hist.getRegions().setObjects(reg);
   List<NamedObject> in=new ArrayList<>();in.add(plane);
   for(Boundary b:reg.getBoundaryManager().getBoundaries())if(b.getPresentationName().equals("main")||b.getPresentationName().equals("flap"))in.add(b);
   hist.getInputs().setObjects(in);
   hist.setFunctions(List.of(ff("AbsolutePressure"),ff("Velocity"),ff("Velocity").getMagnitudeFunction(),ff("VolumeFractionwater")));
   hist.createSnapshot("start");
   RecordedSolutionView view=hist.createRecordedSolutionView();
   view.setPresentationName("CTRL - playback view");view.setStateIndex(hist.getMinStateIndex());
   Scene sc=s.getSceneManager().createScene("CTRL 01 - Recorded flap motion (history)");
   sc.initializeAndWait();
   PartDisplayer pd=sc.getDisplayerManager().createPartDisplayer("Foil and flap",-1,4);
   List<NamedObject> walls=new ArrayList<>();
   for(Boundary b:reg.getBoundaryManager().getBoundaries())if(b.getPresentationName().equals("main")||b.getPresentationName().equals("flap"))walls.add(b);
   pd.getInputParts().setObjects(walls);pd.setRepresentation(view.getRepresentation());pd.setOutline(true);pd.setSurface(true);
   try{
    MonitorPlot p1=s.getPlotManager().createMonitorPlot(List.of(s.getMonitorManager().getMonitor("AF_Delta_Command_deg Monitor"),s.getMonitorManager().getMonitor("AF_Delta_Measured_deg Monitor")),"CTRL 02 - Flap command vs measured [deg]");
    MonitorPlot p2=s.getPlotManager().createMonitorPlot(List.of(s.getMonitorManager().getMonitor("AF_CL Monitor")),"CTRL 03 - CL");
    MonitorPlot p3=s.getPlotManager().createMonitorPlot(List.of(s.getMonitorManager().getMonitor("AF_CD Monitor")),"CTRL 04 - CD");
   }catch(Throwable e){write("CTRL_PLOT_WARNING.json",Map.of("error",e.toString()));}
   playbackOn=true;
   write("CTRL_PLAYBACK_SETUP.json",Map.of("ok",true,"history",hist.getPath().toString()));
  }catch(Throwable e){
   playbackOn=false;
   try{write("CTRL_PLAYBACK_WARNING.json",Map.of("error",e.toString(),"CFD_continues",true));}catch(Exception x){}
  }
 }
 double control(String mode,double t,double cl,double tick){
  switch(mode){
   case "fixed": return 0;
   case "scripted": return scripted(t);
   case "map": case "pimap":{
    double tt=t+tick,T=Math.max(0,tt-d("start_time_s",0));
    double ramp=smoothValue(T/d("map_ramp_s",0.45555302324319264));
    double ffw=ramp*d("map_amp_deg",0)*Math.cos(d("map_omega_rad_s",13.79)*tt+d("map_theta0_rad",0)+Math.toRadians(d("map_phase_off_deg",0)));
    if(mode.equals("pimap")&&clWin.size()>=i("trim_window_steps",911)){
     double mean=clWinSum/clWin.size();
     trim+=(d("cl_target",0.3315)-mean)/d("plant_gain_per_deg",0.0356)*tick/d("trim_tau_s",1.0);
     trim=clamp(trim,-d("trim_max_deg",0.5),d("trim_max_deg",0.5));
    }
    return ffw+(mode.equals("pimap")?trim:0);
   }
   case "pi":{
    double e=d("cl_target",0.3315)-cl,g=d("plant_gain_per_deg",0.0356),kp=d("kp",0.8),ti=d("ti_s",0.15);
    double u=(kp*e+kp/ti*integ)/g, dmax=d("delta_max_deg",2.0);
    if(Math.abs(u)<dmax||Math.signum(u)!=Math.signum(e))integ+=e*tick;
    return clamp((kp*e+kp/ti*integ)/g,-dmax,dmax);
   }
   default: throw new IllegalStateException("Unknown mode "+mode);
  }
 }

 public void execute(){
  s=getActiveSimulation();
  out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  String stage="init";
  try{
   try(Reader r=Files.newBufferedReader(out.resolve("control.properties"))){cfg.load(r);}
   double dt=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class).getTimeStep().evaluate();
   double start=s.getSolution().getPhysicalTime();
   cfg.setProperty("start_time_s",""+start);cfg.setProperty("dt_s",""+dt);
   if(Math.abs(start-d("expected_time_s",start))>1e-6||Math.abs(dt-5e-4)>1e-12)throw new IllegalStateException("Start time or dt mismatch: t="+start+" dt="+dt);
   reg=s.getRegionManager().getRegion("MINI_water_air");
   for(Boundary b:reg.getBoundaryManager().getBoundaries())if(b.getPresentationName().equals("flap"))flapB.add(b);
   if(flapB.size()!=1)throw new IllegalStateException("flap boundary not found");
   String mode=str("mode","pi");int tickSteps=i("tick_steps",10),steps=i("steps",200);double tick=tickSteps*dt;
   stage="install";
   boolean fresh=s.get(GlobalParameterManager.class).getObjects().stream().noneMatch(o->((NamedObject)o).getPresentationName().equals("FC_Delta_Prev_deg"));
   if(fresh){installCommand();installMotion();} else {pPrev=param("FC_Delta_Prev_deg");pNext=param("FC_Delta_Next_deg");pT0=param("FC_T0_s");pTick=param("FC_Tick_s");refStyle=str("ref_style","Parameter");}
   set(pTick,tick);
   if(i("playback",0)==1)setupPlayback();
   double prevCmd=fresh?0:pNext.getQuantity().getRawValue();
   write("FC_STATE.json",Map.of("stage","installed","mode",mode,"time_s",start,"dt_s",dt,"tick_s",tick,"fresh",fresh,"cl_at_start",rd("AF_CL"),"cd_at_start",rd("AF_CD")));
   double dmax=d("delta_max_deg",2.0),rate=d("rate_max_deg_s",30.0),clTarget=d("cl_target",0.3315);
   Path stop=Paths.get(str("stop_file",out.resolve("STOP").toString()));
   long wall0=System.nanoTime();double wallBudget=d("wall_budget_s",3600);
   String result="DONE";
   stage="loop";
   try(BufferedWriter h=Files.newBufferedWriter(out.resolve("history.csv"));BufferedWriter c=Files.newBufferedWriter(out.resolve("ticks.csv"))){
    h.write("time_s,step,solver_s,CL,CD,Fx_N,Fz_N,Mh_Nm,pFlapAbsMin_Pa,cmd_deg,meas_deg,interfaceCFL,pmin_Pa,eta_m3_m,eta_hinge_m,trim_deg\n");
    c.write("time_s,step,CL_in,cmd_prev_deg,cmd_next_deg,mode\n");/*CL_in is the controller input (filtered when cl_filter_tau_s>0)*/
    for(int step=1;step<=steps;step++){
     if(Files.exists(stop)){result="HOLD_STOP_FILE";break;}
     if((System.nanoTime()-wall0)/1e9>wallBudget){result="HOLD_WALL_BUDGET";break;}
     if((step-1)%tickSteps==0){
      double t=s.getSolution().getPhysicalTime(),cl=rd("AF_CL");
      if(!Double.isFinite(cl))throw new IllegalStateException("CL not finite at t="+t);
      double clIn=(d("cl_filter_tau_s",0)>0&&Double.isFinite(clf))?clf:cl;
      double next=control(mode,t,clIn,tick);
      next=clamp(next,prevCmd-rate*tick,prevCmd+rate*tick);next=clamp(next,-dmax,dmax);
      set(pPrev,prevCmd);set(pNext,next);set(pT0,t);
      c.write(t+","+step+","+clIn+","+prevCmd+","+next+","+mode+"\n");c.flush();
      prevCmd=next;
     }
     long t0=System.nanoTime();s.getSimulationIterator().step(1);double sec=(System.nanoTime()-t0)/1e9;
     double t=s.getSolution().getPhysicalTime();
     if(Math.abs(t-(start+step*dt))>1e-8)throw new IllegalStateException("Physical time discontinuity at step "+step+": t="+t);
     double cl=rd("AF_CL"),cd=rd("AF_CD"),cfl=rd("NN_interfaceCFL"),pmin=rd("NN_pmin");
     h.write(t+","+step+","+sec+","+cl+","+cd+","+rd("AF_Fx")+","+rd("AF_Fz")+","+rd("AF_Mh")+","+rd("AF_Flap_pAbs_Min")+","+rd("AF_Delta_Command_deg")+","+rd("AF_Delta_Measured_deg")+","+cfl+","+pmin+","+eta("Surface Integral 4","Surface Integral 5")+","+eta("Surface Integral 7","Surface Integral 8")+","+trim+"\n");
     clf=Double.isFinite(clf)?clf+(cl-clf)*dt/(d("cl_filter_tau_s",0)+dt):cl;
     clWin.addLast(cl);clWinSum+=cl;if(clWin.size()>i("trim_window_steps",911))clWinSum-=clWin.removeFirst();
     if(playbackOn&&step%i("snap_steps",25)==0){try{hist.createSnapshot("step_"+step+"_t"+t);}catch(Throwable e){playbackOn=false;write("CTRL_PLAYBACK_WARNING.json",Map.of("step",step,"error",e.toString(),"CFD_continues",true));}}
     if(step%20==0){h.flush();write("FC_STATE.json",Map.of("stage","running","mode",mode,"time_s",t,"step",step,"of",steps,"CL",cl,"CD",cd,"cmd_deg",prevCmd));}
     if(!Double.isFinite(cl+cd)||cfl>0.95||Math.abs(cl-clTarget)>0.5){result="HOLD_GUARD";break;}
    }
   }
   stage="save";
   Path fin=out.resolve("FINAL.sim");
   if(Files.exists(fin))throw new IllegalStateException("Refuse overwrite FINAL.sim");
   s.saveState(fin.toString());
   write("FC_RESULT.json",Map.of("result",result,"mode",mode,"end_time_s",s.getSolution().getPhysicalTime(),"final_cmd_deg",prevCmd,"integrator",integ,"wall_s",(System.nanoTime()-wall0)/1e9));
  }catch(Throwable e){
   try{write("ERROR.json",Map.of("stage",stage,"error",e.toString()));}catch(Exception x){}
   throw new RuntimeException(e);
  }
 }
}
