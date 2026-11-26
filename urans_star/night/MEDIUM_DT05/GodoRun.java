package macro;
import star.motion.*;import star.meshing.*;import star.common.*;import star.vis.*;import star.post.*;import star.metrics.*;import star.base.neo.*;import star.base.report.*;import star.flow.*;import star.material.*;import star.segregatedflow.*;import star.turbulence.*;import star.kwturb.*;import star.vof.*;import star.mixturemultiphase.*;import star.vis.*;import java.nio.file.*;import java.io.*;import java.util.*;
import java.io.*;
import java.nio.file.*;
import java.util.*;

/**
 * GodoRun - long unattended FIXED-foil run on a GODO_SETUP / checkpoint .sim (restart-safe).
 * control.properties: t_end_s, checkpoint_every_steps, history_every_steps, initialize (true only for a fresh setup),
 *                     wall_budget_s, stop_file
 * Appends to history.csv (header written if new), saves CP_<step>_t<time>.sim every checkpoint_every_steps,
 * LATEST_CHECKPOINT.txt, RUN_STATE.json (heartbeat), RUN_RESULT.json at the end. Stops on NaN or interface CFL > 0.95.
 */
public class GodoRun extends StarMacro {
 Simulation s; Path out; Properties cfg=new Properties();
 double d(String k,double v){return Double.parseDouble(cfg.getProperty(k,""+v));}
 int i(String k,int v){return Integer.parseInt(cfg.getProperty(k,""+v));}
 double rv(String n){try{return s.getReportManager().getReport(n).getReportMonitorValue();}catch(Throwable e){return Double.NaN;}}
 void put(String name,String txt)throws Exception{Path p=out.resolve(name),t=out.resolve(name+".tmp");Files.writeString(t,txt);Files.move(t,p,StandardCopyOption.REPLACE_EXISTING);}
 static final String[] COLS={"AF_CL","AF_CD","AF_Fx","AF_Fz","AF_Mh","GODO_interfaceCFL","NN_pmin","AF_Flap_pAbs_Min",
   "GODO_yplus_min","GODO_yplus_mean","GODO_yplus_max","GODO_yplus_frac_30_70",
   "GODO_eta_upstream_quarter_lambda","GODO_eta_at_LE","GODO_eta_at_hinge"};

 public void execute(){
  s=getActiveSimulation();
  out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  try{
   try(Reader r=Files.newBufferedReader(out.resolve("run.properties"))){cfg.load(r);}
   s.getSimulationIterator().getAutoSave().setEnabled(false);
   if(Boolean.parseBoolean(cfg.getProperty("initialize","false")))s.getSolution().initializeSolution();
   double dt=s.getSolverManager().getSolver(ImplicitUnsteadySolver.class).getTimeStep().evaluate();
   double tEnd=d("t_end_s",11.62);int cpEvery=i("checkpoint_every_steps",969);
   Path stop=Paths.get(cfg.getProperty("stop_file",out.resolve("STOP").toString()));
   long w0=System.nanoTime();double budget=d("wall_budget_s",86400);
   Path hist=out.resolve("history.csv");boolean fresh=!Files.exists(hist);
   String result="DONE";int k=0;
   try(BufferedWriter h=Files.newBufferedWriter(hist,StandardOpenOption.CREATE,StandardOpenOption.APPEND)){
    if(fresh){StringBuilder b=new StringBuilder("time_s,solver_s");for(String c:COLS)b.append(",").append(c);h.write(b+"\n");}
    while(s.getSolution().getPhysicalTime()<tEnd-0.5*dt){
     if(Files.exists(stop)){result="HOLD_STOP_FILE";break;}
     if((System.nanoTime()-w0)/1e9>budget){result="HOLD_WALL_BUDGET";break;}
     long b0=System.nanoTime();s.getSimulationIterator().step(1);double sec=(System.nanoTime()-b0)/1e9;k++;
     double t=s.getSolution().getPhysicalTime();
     StringBuilder b=new StringBuilder().append(t).append(",").append(sec);
     for(String c:COLS)b.append(",").append(rv(c));
     h.write(b+"\n");
     double cl=rv("AF_CL"),cd=rv("AF_CD"),cfl=rv("GODO_interfaceCFL");
     if(k%20==0){h.flush();put("RUN_STATE.json","{\"time_s\":"+t+",\"t_end_s\":"+tEnd+",\"steps_this_session\":"+k+",\"s_per_step\":"+sec+",\"CL\":"+cl+",\"CD\":"+cd+",\"interfaceCFL\":"+cfl+"}");}
     if(!Double.isFinite(cl+cd)){result="HOLD_NAN";break;}
     if(cfl>0.95){result="HOLD_CFL";break;}
     long gstep=Math.round(t/dt);
     if(gstep%cpEvery==0){h.flush();String n=String.format(Locale.ROOT,"CP_%06d_t%.4f.sim",gstep,t);s.saveState(out.resolve(n).toString());put("LATEST_CHECKPOINT.txt",out.resolve(n).toString());}
    }
   }
   String n=String.format(Locale.ROOT,"END_t%.4f.sim",s.getSolution().getPhysicalTime());
   s.saveState(out.resolve(n).toString());put("LATEST_CHECKPOINT.txt",out.resolve(n).toString());
   put("RUN_RESULT.json","{\"result\":\""+result+"\",\"time_s\":"+s.getSolution().getPhysicalTime()+",\"steps_this_session\":"+k+",\"wall_s\":"+(System.nanoTime()-w0)/1e9+"}");
  }catch(Throwable e){
   try{put("RUN_ERROR.json","{\"error\":\""+e.toString().replace("\"","'").replace("\\","/").replace("\n"," ")+"\"}");}catch(Exception x){}
   throw new RuntimeException(e);
  }
 }
}
