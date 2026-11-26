package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;
import java.nio.file.*;import java.io.*;import java.util.*;

/**
 * RunStrut - liczenie przypadku wspornika (STRUT_SETUP_h*.sim albo CP_*.sim do wznowienia).
 *  - historia co krok: strut_history.csv (dopisywana, wznowienie kontynuuje)
 *  - recyrkulacja: co cp_every krokow zapis CP_*.sim i usuniecie poprzedniego CP (zostaje 1)
 *  - plik STOP w folderze -> zapis CP i wyjscie
 *  - koniec (t_end_s): END_t*.sim, usuniecie ostatniego CP, RUN_RESULT.json (srednie z ostatnich avg_s sekund)
 */
public class RunStrut extends StarMacro {
 Simulation s;Path out;Properties cfg=new Properties();
 double d(String k,double v){return Double.parseDouble(cfg.getProperty(k,""+v));}
 double rv(String n){try{return s.getReportManager().getReport(n).getReportMonitorValue();}catch(Throwable e){return Double.NaN;}}
 static final String[] R={"STRUT_Fx_pressure_half","STRUT_Fx_shear_half","STRUT_Fx_half","STRUT_D_full_N","STRUT_D_per_m_submergence_N_m",
  "STRUT_wetted_area_half_m2","STRUT_ventilated_area_half_m2","STRUT_max_water_above_level_m","STRUT_interfaceCFL","STRUT_yplus_mean"};
 public void execute(){
  s=getActiveSimulation();
  out=Paths.get(System.getenv().getOrDefault("MINI_CASE_DIR",System.getProperty("user.dir")));
  Map<String,Object> res=new LinkedHashMap<>();
  try{
   try(Reader r=Files.newBufferedReader(out.resolve("control.properties"))){cfg.load(r);}
   s.getSimulationIterator().getAutoSave().setEnabled(false);
   double tEnd=d("t_end_s",2.0),avg=d("avg_s",0.5);int cpEvery=(int)d("cp_every",500);
   if(s.getSolution().getPhysicalTime()<=0)s.getSolution().initializeSolution();
   Path hist=out.resolve("strut_history.csv");boolean head=!Files.exists(hist);
   try(BufferedWriter h=Files.newBufferedWriter(hist,StandardOpenOption.CREATE,StandardOpenOption.APPEND)){
    if(head){h.write("step,time_s,wall_s");for(String n:R)h.write(","+n);h.write("\n");}
    Path lastCp=null;
    try(DirectoryStream<Path> ds=Files.newDirectoryStream(out,"CP_*.sim")){for(Path p:ds)lastCp=p;}
    int k=0;
    while(s.getSolution().getPhysicalTime()<tEnd-1e-9){
     long t0=System.nanoTime();s.getSimulationIterator().step(1);double w=(System.nanoTime()-t0)/1e9;k++;
     double t=s.getSolution().getPhysicalTime();int it=s.getSimulationIterator().getCurrentIteration();
     StringBuilder b=new StringBuilder();b.append(it).append(",").append(t).append(",").append(w);
     double dfull=Double.NaN;
     for(String n:R){double v=rv(n);b.append(",").append(v);if(n.equals("STRUT_D_full_N"))dfull=v;}
     h.write(b.append("\n").toString());h.flush();
     if(!Double.isFinite(dfull))throw new IllegalStateException("non-finite drag at t="+t);
     boolean stop=Files.exists(out.resolve("STOP"));
     if(k%cpEvery==0||stop){
      Path cp=out.resolve(String.format(Locale.ROOT,"CP_%06d_t%.4f.sim",it,t));
      s.saveState(cp.toString());
      if(lastCp!=null&&!lastCp.equals(cp))try{Files.deleteIfExists(lastCp);}catch(Exception e){}
      lastCp=cp;
      if(stop){res.put("status","STOPPED");res.put("time_s",t);write(res);return;}
     }
    }
    Path end=out.resolve(String.format(Locale.ROOT,"END_t%.4f.sim",s.getSolution().getPhysicalTime()));
    s.saveState(end.toString());
    if(lastCp!=null)try{Files.deleteIfExists(lastCp);}catch(Exception e){}
   }
   // srednie z ostatnich avg_s
   List<String> lines=Files.readAllLines(hist);String[] hd=lines.get(0).split(",");
   double tl=Double.parseDouble(lines.get(lines.size()-1).split(",")[1]);
   for(int c=3;c<hd.length;c++){double sm=0,sq=0;int n=0;
    for(int L=1;L<lines.size();L++){String[] f=lines.get(L).split(",");double t=Double.parseDouble(f[1]);if(t<tl-avg)continue;double v=Double.parseDouble(f[c]);if(!Double.isFinite(v))continue;sm+=v;sq+=v*v;n++;}
    double mu=n>0?sm/n:Double.NaN;res.put(hd[c]+"_mean",mu);res.put(hd[c]+"_std",n>1?Math.sqrt(Math.max(0,sq/n-mu*mu)):Double.NaN);}
   double ws=0;int nw=0;for(int L=Math.max(1,lines.size()-200);L<lines.size();L++){ws+=Double.parseDouble(lines.get(L).split(",")[2]);nw++;}
   res.put("wall_s_per_step_last200",nw>0?ws/nw:Double.NaN);
   res.put("t_end_s",tl);res.put("avg_window_s",avg);res.put("h_m",d("h_m",Double.NaN));res.put("status","DONE");
   write(res);
  }catch(Throwable e){res.put("status","ERROR");res.put("error",e.toString());write(res);throw new RuntimeException(e);}
 }
 void write(Map<String,Object> m){
  StringBuilder b=new StringBuilder("{");boolean f=true;
  for(Map.Entry<String,Object> e:m.entrySet()){if(!f)b.append(",\n");f=false;Object v=e.getValue();
   String js=(v instanceof Number n)?(Double.isFinite(n.doubleValue())?n.toString():"null"):"\""+String.valueOf(v).replace("\\","/").replace("\"","'")+"\"";
   b.append("\"").append(e.getKey()).append("\": ").append(js);}
  try{Path t=out.resolve("RUN_RESULT.json.tmp");Files.writeString(t,b.append("}\n").toString());Files.move(t,out.resolve("RUN_RESULT.json"),StandardCopyOption.REPLACE_EXISTING);}catch(Exception e){}
 }
}
