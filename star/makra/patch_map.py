import re, sys
p = r"T:\NTNU_GODO_CONTROL_20261109\10_macros\GodoControl.java"
t = open(p, encoding="utf-8").read()

def rep(old, new, count=1):
    global t
    assert t.count(old) >= 1, "missing: " + old[:60]
    t = t.replace(old, new, count)

# fields + helpers
rep(" double integ=0;\n", r'''
 double integ=0, trim=0, clWinSum=0;
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
''')

# control modes
rep('   case "pi":{', r'''   case "map": case "pimap":{
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
   case "pi":{''')

# history header + row
rep('pFlapAbsMin_Pa,cmd_deg,meas_deg,interfaceCFL,pmin_Pa\\n"', 'pFlapAbsMin_Pa,cmd_deg,meas_deg,interfaceCFL,pmin_Pa,eta_m3_m,eta_hinge_m,trim_deg\\n"')
rep('+","+cfl+","+pmin+"\\n");', '+","+cfl+","+pmin+","+eta("Surface Integral 4","Surface Integral 5")+","+eta("Surface Integral 7","Surface Integral 8")+","+trim+"\\n");\n     clWin.addLast(cl);clWinSum+=cl;if(clWin.size()>i("trim_window_steps",911))clWinSum-=clWin.removeFirst();\n     if(playbackOn&&step%i("snap_steps",25)==0){try{hist.createSnapshot("step_"+step+"_t"+t);}catch(Throwable e){playbackOn=false;write("CTRL_PLAYBACK_WARNING.json",Map.of("step",step,"error",e.toString(),"CFD_continues",true));}}')
# enable playback after install
rep('   set(pTick,tick);\n', '   set(pTick,tick);\n   if(i("playback",0)==1)setupPlayback();\n')
open(p, "w", encoding="utf-8").write(t)
print("patched", len(t))
