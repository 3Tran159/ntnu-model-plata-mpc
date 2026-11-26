package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * GodoOversetRun - GodÃ¸-style flight control of the rotating + heaving foil (overset case), restart-safe, unattended.
 *
 * Plant (all imposed natively through the GUI-visible motion "GODO foil heave + pitch (from controller)"):
 *   heave: m dv/dt = F_y,fluid - m g   (explicit per step; F_y includes hydrostatics), z += v dt  -> GODO_Heave_v_ms / _z_m
 *   pitch: nose-up angle theta [deg] (absolute, foil geometry = 0), |theta| <= 7.5 deg, |dtheta/dt| <= 90 deg/s (GodÃ¸ Table 1)
 *          commanded every tick_steps; inside a tick theta follows a C1 (smoothstep) blend, so the rotation rate is
 *          continuous (no impulsive added-mass spikes at tick boundaries); GODO_Rot_rate_radps = -dtheta/dt (STAR sign).
 * Controllers (mode):
 *   k0     : PID (kp, ki) + kasowanie fali: cmd -= k0_gain * deg(w_wody_na_placie / U)  [KOPIA makra 30_URANS_STAR/makro_k0, 13.11]
 *   policy : siec aktora z pliku policy_file (TD3/SAC wytrenowane w modelu wirowym; KOPIA makra z 50_learning/vortex_env/stars)
 *   hold   : theta = theta_trim, heave held (z = 0) until t >= release_s (flow development), then free heave
 *   pid    : GodÃ¸'s baseline - PID on the design draft  theta = trim + Kp e + Ki int(e) - Kd zdot ,  e = z_ref - z
 *   pid_prbs / pid_sine : PID + excitation (training data, GodÃ¸ phase 2 style)
 *   policy : later (frozen actor weights in JSON)
 * Termination (GodÃ¸): |z| > 0.75 m  or  submergence < c/2  -> HOLD_LIMIT.
 * Files: run.properties in, history.csv (append), CP_*.sim every checkpoint_every_steps (2 kept), CTRL_STATE.properties
 * (controller state for restarts), RUN_STATE.json heartbeat, RUN_RESULT.json / RUN_ERROR.json / RUN_WARN.json.
 */
public class GodoOversetRun extends StarMacro {
 Simulation s; Path out; Properties cfg=new Properties(), st=new Properties();
 double d(String k,double v){return Double.parseDouble(cfg.getProperty(k,""+v));}
 int i(String k,int v){return Integer.parseInt(cfg.getProperty(k,""+v));}
 double sd(String k,double v){return Double.parseDouble(st.getProperty(k,""+v));}
 double rv(String n){try{return s.getReportManager().getReport(n).getReportMonitorValue();}catch(Throwable e){return Double.NaN;}}
 void put(String name,String txt)throws Exception{Path p=out.resolve(name),t=out.resolve(name+".tmp");Files.writeString(t,txt);Files.move(t,p,StandardCopyOption.REPLACE_EXISTING);}
 void par(String n,double v){((ScalarGlobalParameter)s.get(GlobalParameterManager.class).getObject(n)).getQuantity().setValue(v);}
 void cmdFF(double deg){
  FieldFunctionManager fm=s.getFieldFunctionManager();UserFieldFunction f=(UserFieldFunction)fm.getFunction("AF_Cycle_Command");
  f.setDefinition(String.format(Locale.ROOT,"%.10f",deg-d("pitch_trim_deg",0)));   // GODO_pitch_deg = GODO_Pitch_trim_deg + AF_Cycle_Command
 }
 static double knot(long seed,long k){long x=seed*6364136223846793005L+k*1442695040888963407L;x^=(x>>>33);x*=0xff51afd7ed558ccdL;x^=(x>>>33);x*=0xc4ceb9fe1a85ec53L;x^=(x>>>33);return ((x>>>11)*(1.0/9007199254740992.0))*2-1;}
 static double clamp(double x,double a){return Math.max(-a,Math.min(a,x));}
 // ---- 16.11 koordynator: natywne sceny STAR (edytowalne w GUI) + zapis klatek PNG co scene_every_steps (opcja scenes=1) ----
 java.util.List<Object[]> SC=new java.util.ArrayList<>();
 void buildScenes(){
  String[][] spec={{"GODO_S1_powierzchnia_cala","vof","31","1.09","156","1920","400","0","1"},
   {"GODO_S2_powierzchnia_za_platem","vof","25","1.0","60","1600","500","0","1"},
   {"GODO_S3_predkosc_przy_placie","vel","0.35","0.05","3","1600","900","8","16"},
   {"GODO_S4_wirowosc_slad","vort","3.5","0.0","9","1600","500","-60","60"},
   {"GODO_S5_cisnienie_przy_placie","p","0.35","0.05","2","1600","900","",""},
   {"GODO_S6_woda_nad_platem","vof","1.5","0.6","6","1600","700","0","1"}};
  java.util.Collection<Region> regs=s.getRegionManager().getRegions(); FieldFunctionManager fm=s.getFieldFunctionManager();
  for(String[] q:spec){try{
   star.vis.Scene sc=null; for(star.vis.Scene x:s.getSceneManager().getScenes()) if(x.getPresentationName().equals(q[0])) sc=x;
   if(sc==null){ sc=s.getSceneManager().createScene(q[0]); sc.setPresentationName(q[0]); sc.initializeAndWait();
    star.vis.ScalarDisplayer sd=sc.getDisplayerManager().createScalarDisplayer("Skalar"); sd.getInputParts().setObjects(regs);
    FieldFunction ff=q[1].equals("vof")?fm.getFunction("VolumeFractionwater"):q[1].equals("vel")?((PrimitiveFieldFunction)fm.getFunction("Velocity")).getMagnitudeFunction()
      :q[1].equals("vort")?((PrimitiveFieldFunction)fm.getFunction("VorticityVector")).getComponentFunction(2):fm.getFunction("Pressure");
    sd.getScalarDisplayQuantity().setFieldFunction(ff);
    if(!q[7].isEmpty()){ sd.getScalarDisplayQuantity().setAutoRange(star.vis.AutoRangeMode.NONE); sd.getScalarDisplayQuantity().setRange(new DoubleVector(new double[]{Double.parseDouble(q[7]),Double.parseDouble(q[8])})); } }
   double x=Double.parseDouble(q[2]),y=Double.parseDouble(q[3]),wd=Double.parseDouble(q[4]); int W=Integer.parseInt(q[5]),H=Integer.parseInt(q[6]);
   sc.getCurrentView().setInput(new DoubleVector(new double[]{x,y,0}),new DoubleVector(new double[]{x,y,5}),new DoubleVector(new double[]{0,1,0}),wd*H/W/2,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false);
   SC.add(new Object[]{sc,q[0],W,H});
  }catch(Throwable e){ try{put("SCENE_WARN_"+q[0]+".txt",e.toString());}catch(Exception z){} }}
 }
 void snapScenes(double t){ for(Object[] o:SC){ try{ Path dd=out.resolve("sceny").resolve((String)o[1]); Files.createDirectories(dd);
   ((star.vis.Scene)o[0]).printAndWait(dd.resolve(String.format(Locale.ROOT,"%s_t%07.3f.png",(String)o[1],t)).toString(),1,(Integer)o[2],(Integer)o[3]); }catch(Throwable e){} } }
 /** Sonda fali jak GODO_eta_at_LE (BuildGodoCase.productionReports): przekroj pionowy w x, calka udzialu wody / szerokosc + y_dna - y_spokojnej. Tworzona raz, zostaje w .sim (edytowalna w GUI). */
 void ensureGauge(String nm,double x){
  try{if(s.getReportManager().getReport(nm)!=null)return;}catch(Throwable e){}
  star.vis.PlaneSection ref=null;
  for(Object o:s.getPartManager().getObjects())if(o instanceof star.vis.PlaneSection p&&p.getPresentationName().startsWith("GODO_eta_at_LE"))ref=p;
  star.vis.PlaneSection pl=s.getPartManager().createPlaneSection();pl.setPresentationName(nm+" plane");
  pl.getInputParts().setObjects(ref.getInputParts().getObjects());
  pl.setOrigin(new DoubleVector(new double[]{x,0,.01}));pl.setOrientation(new DoubleVector(new double[]{1,0,0}));
  SurfaceIntegralReport si=s.getReportManager().createReport(SurfaceIntegralReport.class);si.setPresentationName(nm+"_SI");
  si.setFieldFunction(s.getFieldFunctionManager().getFunction("VolumeFractionwater"));si.getParts().setObjects(pl);si.setSmooth(false);
  ExpressionReport e=s.getReportManager().createReport(ExpressionReport.class);e.setPresentationName(nm);
  e.setDefinition(((ExpressionReport)s.getReportManager().getReport("GODO_eta_at_LE")).getDefinition().replace("GODO_eta_at_LE_SIReport",nm+"_SIReport"));
 }

 // ---- polityka (siec aktora) - tryb mode=policy ----
 double[][][] PW; double[][] PB; double[] OBS_SC;
 void loadPolicy(String file)throws Exception{
  java.util.Scanner sc=new java.util.Scanner(Files.newBufferedReader(Paths.get(file)));sc.useLocale(Locale.ROOT);
  sc.next();sc.next();sc.next();OBS_SC=new double[5];for(int j=0;j<5;j++)OBS_SC[j]=sc.nextDouble();
  PW=new double[3][][];PB=new double[3][];
  for(int L=0;L<3;L++){sc.next();int r=sc.nextInt(),c=sc.nextInt();PW[L]=new double[r][c];for(int a=0;a<r;a++)for(int b=0;b<c;b++)PW[L][a][b]=sc.nextDouble();
   sc.next();int n=sc.nextInt();PB[L]=new double[n];for(int a=0;a<n;a++)PB[L][a]=sc.nextDouble();}
 }
 double policy(double[] o){
  double[] x=new double[5];for(int j=0;j<5;j++)x[j]=Math.max(-5,Math.min(5,o[j]/OBS_SC[j]));
  for(int L=0;L<3;L++){double[] y=new double[PW[L].length];for(int a=0;a<y.length;a++){double sm=PB[L][a];for(int b=0;b<x.length;b++)sm+=PW[L][a][b]*x[b];y[a]=(L<2)?Math.max(0,sm):Math.tanh(sm);}x=y;}
  return x[0];
 }


 public void execute(){
  s=getActiveSimulation();
  out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  try{
   try(Reader r=Files.newBufferedReader(out.resolve("run.properties"))){cfg.load(r);}
   Path sp=out.resolve("CTRL_STATE.properties");if(Files.exists(sp))try(Reader r=Files.newBufferedReader(sp)){st.load(r);}
   s.getSimulationIterator().getAutoSave().setEnabled(false);
   if(Boolean.parseBoolean(cfg.getProperty("initialize","false"))){s.getSolution().initializeSolution();st.clear();}
   if(cfg.getProperty("dt_s")!=null)s.getSolverManager().getSolver(ImplicitUnsteadySolver.class).getTimeStep().setValue(d("dt_s",1e-3));
   double dt=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class).getTimeStep().evaluate();
   if(cfg.getProperty("inner")!=null)((InnerIterationStoppingCriterion)s.getSolverStoppingCriterionManager().getSolverStoppingCriterion("Maximum Inner Iterations")).setMaximumNumberInnerIterations(i("inner",12));
   par("GODO_Pitch_trim_deg",d("pitch_trim_deg",0));
   if(cfg.getProperty("iface_alpha_lo")!=null){   // interface Courant only where the water fraction is genuinely mixed
    double lo=d("iface_alpha_lo",0.01);
    ((UserFieldFunction)s.getFieldFunctionManager().getFunction("GODO_interface_Courant")).setDefinition("($VolumeFractionwater>"+lo+" && $VolumeFractionwater<"+(1-lo)+") ? $CourantNumber : 0");
   }
   double mass=d("mass_kg",31.29),g=9.81,tEnd=d("t_end_s",11.62),release=d("release_s",1.9368);
   double thMax=d("theta_max_deg",7.5),rateMax=d("rate_max_deg_s",90),zLim=d("z_limit_m",0.75),subMin=d("submergence_min_m",0.156);
   double kp=d("kp_deg_per_m",10),ki=d("ki_deg_per_m_s",2),kd=d("kd_deg_s_per_m",0),zref=d("z_ref_m",0);
   int tick=i("tick_steps",10),cpEvery=i("checkpoint_every_steps",250);
   String mode=cfg.getProperty("mode","pid");
   if(mode.equals("policy"))loadPolicy(cfg.getProperty("policy_file"));
   double omW=2*Math.PI/d("wave_period_s",5.0),omE=2*Math.PI/d("encounter_period_s",1.9368);
   double z=sd("z",0),v=sd("v",0),ie=sd("ie",0),th0=sd("th0",0),th1=sd("th1",0),tTick=sd("tTick",s.getSolution().getPhysicalTime());
   double th=sd("th",0);   // geometry angle at a fresh start is 0 deg; the first ticks ramp it to the trim (rate-limited)
   long kTick=Long.parseLong(st.getProperty("kTick","0"));
   Path stop=Paths.get(cfg.getProperty("stop_file",out.resolve("STOP").toString()));
   Path hist=out.resolve("history.csv");boolean fresh=!Files.exists(hist);
   String result="DONE";int k=0;long w0=System.nanoTime();double budget=d("wall_budget_s",86400);
   String[] cols={"AF_CL","AF_CD","AF_Fx","GODO_Fy_fluid","GODO_M_pivot","GODO_lift_over_weight","GODO_foil_y_centroid_m","GODO_interfaceCFL","GODO_eta_upstream_quarter_lambda","GODO_eta_at_LE","GODO_yplus_mean","GODO_yplus_frac_30_70"};
   String wg=cfg.getProperty("wake_gauges","");   // 14.11 koordynator: natywne sondy wzniesienia za platem (fala od plata, T3), x [m] po przecinku
   if(!wg.isEmpty()){java.util.List<String> cl=new java.util.ArrayList<>(Arrays.asList(cols));
    for(String xs:wg.split(",")){String nm="GODO_eta_x"+xs.trim();ensureGauge(nm,Double.parseDouble(xs.trim()));cl.add(nm);}
    cols=cl.toArray(new String[0]);}
   int sceneEvery=i("scene_every_steps",0); if(cfg.getProperty("scenes","0").equals("1")) buildScenes();
   try(BufferedWriter h=Files.newBufferedWriter(hist,StandardOpenOption.CREATE,StandardOpenOption.APPEND)){
    if(fresh){StringBuilder b=new StringBuilder("time_s,solver_s,mode,theta_deg,theta_rate_deg_s,theta_cmd_deg,z_m,v_m_s,P_act_W,P_drag_W");for(String c:cols)b.append(",").append(c);h.write(b+"\n");}
    double tick_dur=tick*dt;
    while(s.getSolution().getPhysicalTime()<tEnd-0.5*dt){
     if(Files.exists(stop)){result="HOLD_STOP_FILE";break;}
     if((System.nanoTime()-w0)/1e9>budget){result="HOLD_WALL_BUDGET";break;}
     double t=s.getSolution().getPhysicalTime();
     boolean free=t>=release-0.5*dt;
     // ---- controller (new command at tick boundaries) ----
     if(Math.abs(t-(tTick+tick_dur))<0.5*dt||k==0&&!st.containsKey("tTick")){
      if(k>0||st.containsKey("tTick")){tTick=t;kTick++;}
      double e=zref-z,cmd=d("pitch_trim_deg",0);
      double etaNow=rv("GODO_eta_at_LE");if(!Double.isFinite(etaNow))etaNow=0;
      double wSurf=(omW/omE)*(etaNow-sd("etaPrev",etaNow))/tick_dur;st.setProperty("etaPrev",""+etaNow);
      if(cfg.getProperty("k0_est","raw").equals("h1")){   // 14.11 koordynator: tylko 1. harmoniczna eta_LE z ostatniego okresu spotkania (przesuwne DFT) - bez 2. harmonicznej fali Stokesa (B-Z4)
       double h1Te=2*Math.PI/omE;String[] h1It=(st.getProperty("etaHist","")+t+":"+etaNow+";").split(";");
       java.util.ArrayList<double[]> h1L=new java.util.ArrayList<>();StringBuilder h1Nb=new StringBuilder();double h1M=0;
       for(String h1P:h1It){if(h1P.isEmpty())continue;String[] h1Q=h1P.split(":");double h1Tj=Double.parseDouble(h1Q[0]);if(h1Tj<=t-h1Te+1e-9)continue;double h1Ej=Double.parseDouble(h1Q[1]);h1L.add(new double[]{h1Tj,h1Ej});h1M+=h1Ej;h1Nb.append(h1P).append(";");}
       st.setProperty("etaHist",h1Nb.toString());
       if(h1L.size()>=(int)(0.95*h1Te/tick_dur)){h1M/=h1L.size();double h1A=0,h1B=0;for(double[] h1R:h1L){h1A+=(h1R[1]-h1M)*Math.cos(omE*h1R[0]);h1B+=(h1R[1]-h1M)*Math.sin(omE*h1R[0]);}
        h1A*=2.0/h1L.size();h1B*=2.0/h1L.size();wSurf=(omW/omE)*omE*(-h1A*Math.sin(omE*t)+h1B*Math.cos(omE*t));st.setProperty("h1_last",h1A+" "+h1B+" "+h1L.size());}
      }
      if(mode.equals("policy")&&free){
       double aPrev=Double.parseDouble(st.getProperty("cmd",""+d("pitch_trim_deg",0)))/thMax;
       double a=policy(new double[]{z,v,etaNow,wSurf,aPrev});
       cmd=thMax*a;st.setProperty("obs_last",z+" "+v+" "+etaNow+" "+wSurf+" "+aPrev+" -> "+a);
      }else
      if(!mode.equals("hold")&&free){
       ie+=e*tick_dur; ie=clamp(ie,d("ie_max",1.0));
       cmd+=kp*e+ki*ie-kd*v;
       double tt=t-release;
       if(mode.equals("pid_prbs"))cmd+=d("exc_amp_deg",2.0)*knot(i("seed",1),(long)Math.floor(tt/d("knot_s",0.2)));
       if(mode.equals("pid_sine"))cmd+=d("exc_amp_deg",2.0)*Math.sin(2*Math.PI*tt/d("exc_period_s",1.9368)+Math.toRadians(d("exc_phase_deg",0)));
       if(mode.equals("k0")){double kw=omW*omW/9.81;double wF=wSurf*Math.exp(-kw*Math.max(0,d("free_surface_y_m",1.09)-z));cmd-=d("k0_gain",0.85)*Math.toDegrees(wF/d("U_ms",12.3467));st.setProperty("k0_last",wSurf+" "+wF);}   // K0 (13.11, koordynator): gladki sterownik - kasuje pionowa predkosc wody na plecie (z eta_LE, zanik exp(-k*glebokosc)), jak zaw90.py
      }
      cmd=clamp(cmd,thMax);
      th0=th;th1=Math.max(th-rateMax*tick_dur/1.5,Math.min(th+rateMax*tick_dur/1.5,cmd));  // smoothstep peak rate = 1.5 x mean rate <= rate_max
      st.setProperty("cmd",""+cmd);
     }
     // ---- C1 smoothstep inside the tick ----
     double thNext,rate;
     if(cfg.getProperty("actuator","smoothstep").equals("lag2")){
      // servo model: critically damped 2nd-order lag on the (tick-held) command, rate- and angle-limited.
      // Continuous rate across ticks -> no tick-periodic (100 Hz) angular acceleration / added-mass force ripple.
      double wn=d("servo_wn_rad_s",40),ze=d("servo_zeta",1.0),cmdH=Double.parseDouble(st.getProperty("cmd",""+th));
      double wA=sd("wA",0);
      wA+=dt*(wn*wn*(cmdH-th)-2*ze*wn*wA);wA=clamp(wA,rateMax);
      thNext=th+wA*dt;if(Math.abs(thNext)>thMax){thNext=clamp(thNext,thMax);wA=(thNext-th)/dt;}
      rate=wA;st.setProperty("wA",""+wA);
     }else{
      double u1=(t+dt-tTick)/tick_dur;
      double s1=Math.min(1,u1)*Math.min(1,u1)*(3-2*Math.min(1,u1));
      thNext=th0+(th1-th0)*s1;rate=(thNext-th)/dt;
     }
     par("GODO_Rot_rate_radps",-rate*Math.PI/180);
     // ---- heave (explicit) ----
     double fy=rv("GODO_Fy_fluid");
     boolean dfbi=cfg.getProperty("heave","explicit").equals("dfbi");   // native DFBI body does the heave (implicit coupling)
     if(!dfbi){if(free){v+=dt*(fy-mass*g)/mass;}else{v=0;}par("GODO_Heave_v_ms",v);}
     cmdFF(thNext);   // AF_Cycle_Command / GODO_pitch_deg report the angle reached at the end of the step
     long b0=System.nanoTime();
     int fails=0;while(true){try{s.getSimulationIterator().step(1);break;}catch(Throwable ex){
      double tn=Double.NaN;try{tn=s.getSolution().getPhysicalTime();}catch(Throwable x){}
      put("RUN_WARN.json","{\"step_exception\":\""+ex.toString().replace("\"","'").replace("\\","/").replace("\n"," ")+"\",\"t\":"+tn+"}");
      if(Double.isFinite(tn)&&tn>t+0.5*dt)break;if(++fails>=5)throw ex;Thread.sleep(3000);}}
     double sec=(System.nanoTime()-b0)/1e9;k++;
     th=thNext;
     if(dfbi){z=rv("GODO_heave_dfbi_m");v=rv("GODO_heave_v_dfbi_ms");if(!Double.isFinite(z)){z=0;v=0;}}
     else{z+=v*dt;par("GODO_Heave_z_m",z);}
     double tn=s.getSolution().getPhysicalTime();
     if(sceneEvery>0&&!SC.isEmpty()&&Math.round(tn/dt)%sceneEvery==0) snapScenes(tn);
     double M=rv("GODO_M_pivot"),Pact=Math.max(0,-M*rate*Math.PI/180),Pdrag=d("U_ms",12.3467)*rv("AF_Fx");   // actuator supplies -M*omega when the fluid resists
     StringBuilder b=new StringBuilder().append(tn).append(",").append(sec).append(",").append(mode).append(",").append(th).append(",").append(rate).append(",").append(st.getProperty("cmd","")).append(",").append(z).append(",").append(v).append(",").append(Pact).append(",").append(Pdrag);
     for(String c:cols)b.append(",").append(rv(c));
     h.write(b+"\n");
     double cl=rv("AF_CL"),cfl=rv("GODO_interfaceCFL"),eta=rv("GODO_eta_at_LE");
     // persist controller state every step (cheap) so a restart from any checkpoint can resume exactly
     st.setProperty("z",""+z);st.setProperty("v",""+v);st.setProperty("ie",""+ie);st.setProperty("th",""+th);st.setProperty("th0",""+th0);st.setProperty("th1",""+th1);
     st.setProperty("tTick",""+tTick);st.setProperty("kTick",""+kTick);st.setProperty("t",""+tn);
     if(k%20==0){h.flush();put("RUN_STATE.json","{\"time_s\":"+tn+",\"t_end_s\":"+tEnd+",\"steps_this_session\":"+k+",\"s_per_step\":"+sec+",\"mode\":\""+mode+"\",\"theta_deg\":"+th+",\"z_m\":"+z+",\"v_m_s\":"+v+",\"CL\":"+cl+",\"lift_over_weight\":"+rv("GODO_lift_over_weight")+",\"interfaceCFL\":"+cfl+"}");}
     if(!Double.isFinite(cl)){result="HOLD_NAN";break;}
     if(cfl>d("cfl_max",0.95)){result="HOLD_CFL";break;}
     double sub=d("free_surface_y_m",1.09)+(Double.isFinite(eta)?eta:0)-z;
     if(Math.abs(z)>zLim||sub<subMin){result="HOLD_LIMIT";break;}
     long gstep=Math.round(tn/dt);
     if(gstep%cpEvery==0){h.flush();String n=String.format(Locale.ROOT,"CP_%06d_t%.4f.sim",gstep,tn);
      try(Writer w=Files.newBufferedWriter(out.resolve(n+".ctrl"))){st.store(w,"controller state at "+tn);}
      s.saveState(out.resolve(n).toString());put("LATEST_CHECKPOINT.txt",out.resolve(n).toString());
      try(DirectoryStream<Path> ds=Files.newDirectoryStream(out,"CP_*.sim")){List<Path> cps=new ArrayList<>();for(Path p:ds)cps.add(p);Collections.sort(cps);
       for(int q=0;q<cps.size()-2;q++){Files.deleteIfExists(cps.get(q));Files.deleteIfExists(Paths.get(cps.get(q)+".ctrl"));}}catch(Exception x){}}
    }
   }
   String n=String.format(Locale.ROOT,"END_t%.4f.sim",s.getSolution().getPhysicalTime());
   try(Writer w=Files.newBufferedWriter(out.resolve(n+".ctrl"))){st.store(w,"controller state");}
   s.saveState(out.resolve(n).toString());put("LATEST_CHECKPOINT.txt",out.resolve(n).toString());
   put("RUN_RESULT.json","{\"result\":\""+result+"\",\"time_s\":"+s.getSolution().getPhysicalTime()+",\"steps_this_session\":"+k+",\"wall_s\":"+(System.nanoTime()-w0)/1e9+"}");
  }catch(Throwable e){
   try{put("RUN_ERROR.json","{\"error\":\""+e.toString().replace("\"","'").replace("\\","/").replace("\n"," ")+"\"}");}catch(Exception x){}
   throw new RuntimeException(e);
  }
 }
}
