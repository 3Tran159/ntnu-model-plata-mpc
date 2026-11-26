package macro;
import star.common.*;import star.base.neo.*;import star.base.report.*;import star.vis.*;
import java.util.*;

/** DodajNaZywo - 26.11 (Julek 10:41: podlaczony GUI do serwera liczacego przebieg OVS_CEL_000g_T8_90).
 *  Uruchomic W GUI podlaczonym do serwera: Tools > Macro > Play Macro... -> ten plik. NIC nie zapisuje, nie zmienia fizyki ani solvera.
 *  Dodaje: 10 scen (jak w OVS_CEL_005g_T8_90_GUI.sim) i 5 wykresow monitorow, ktore rosna na zywo co krok czasu.
 *  Po obejrzeniu: rozlaczyc GUI przez File > Disconnect (NIE "Close Simulation" / "Kill Server" - to zatrzymaloby przebieg). */
public class DodajIZapisz extends StarMacro {
 Simulation s;
 DoubleVector dv(double... d){return new DoubleVector(d);}
 void view(Scene sc,double x,double y,double wd,int W,int H){ sc.getCurrentView().setInput(dv(x,y,0),dv(x,y,5),dv(0,1,0),wd*H/W/2,1,s.getCoordinateSystemManager().getLabCoordinateSystem(),false); }
 Scene nowa(String n){ for(Scene x:s.getSceneManager().getScenes()) if(x.getPresentationName().equals(n)) return x; Scene sc=s.getSceneManager().createScene(n); sc.setPresentationName(n); sc.initializeAndWait(); return sc; }
 public void execute(){
  s=getActiveSimulation(); Collection<Region> regs=s.getRegionManager().getRegions(); FieldFunctionManager fm=s.getFieldFunctionManager();
  PlaneSection scp=null; for(Object o:s.getPartManager().getObjects()) if(o instanceof PlaneSection pp&&pp.getPresentationName().equals("GODO_scene_plane")) scp=pp;
  if(scp==null){ scp=s.getPartManager().createPlaneSection(); scp.setPresentationName("GODO_scene_plane"); scp.getInputParts().setObjects(regs); scp.setOrigin(dv(0,0,0.01)); scp.setOrientation(dv(0,0,1)); }
  String[][] spec={{"ZYWO_01_powierzchnia_cala_domena","vof","23.4","1.09","112","1920","420","0","1"},
   {"ZYWO_02_powierzchnia_wokol_plata","vof","8","1.0","40","1600","500","0","1"},
   {"ZYWO_03_woda_nad_platem","vof","1.0","0.6","5","1600","800","0","1"},
   {"ZYWO_04_predkosc_przy_placie","vel","0.35","0.05","3","1600","900","8","16"},
   {"ZYWO_05_wirowosc_slad","vort","3.5","0.0","9","1600","500","-60","60"},
   {"ZYWO_06_cisnienie_przy_placie","p","0.35","0.05","2","1600","900","",""},
   {"ZYWO_07_predkosc_cala_domena","vel","23.4","0","112","1920","500","8","16"}};
  for(String[] q:spec){try{
   Scene sc=nowa(q[0]); ScalarDisplayer sd=null;
   for(Object d:sc.getDisplayerManager().getObjects()) if(d instanceof ScalarDisplayer x) sd=x;
   if(sd==null) sd=sc.getDisplayerManager().createScalarDisplayer("Skalar");
   sd.getInputParts().setObjects(scp);
   FieldFunction ff=q[1].equals("vof")?fm.getFunction("VolumeFractionwater"):q[1].equals("vel")?((PrimitiveFieldFunction)fm.getFunction("Velocity")).getMagnitudeFunction()
     :q[1].equals("vort")?((PrimitiveFieldFunction)fm.getFunction("VorticityVector")).getComponentFunction(2):fm.getFunction("Pressure");
   sd.getScalarDisplayQuantity().setFieldFunction(ff);
   if(!q[7].isEmpty()){ sd.getScalarDisplayQuantity().setAutoRange(AutoRangeMode.NONE); sd.getScalarDisplayQuantity().setRange(dv(Double.parseDouble(q[7]),Double.parseDouble(q[8]))); }
   view(sc,Double.parseDouble(q[2]),Double.parseDouble(q[3]),Double.parseDouble(q[4]),Integer.parseInt(q[5]),Integer.parseInt(q[6]));
  }catch(Throwable e){ s.println("SCENA BLAD "+q[0]+": "+e); }}
  PrimitiveFieldFunction vel=(PrimitiveFieldFunction)fm.getFunction("Velocity");
  try{ Scene s9=nowa("ZYWO_08_wektory_LIC"); VectorDisplayer vd=null; for(Object d:s9.getDisplayerManager().getObjects()) if(d instanceof VectorDisplayer x) vd=x;
   if(vd==null) vd=s9.getDisplayerManager().createVectorDisplayer("Wektory");
   vd.getInputParts().setObjects(scp); vd.getVectorDisplayQuantity().setFieldFunction(vel); vd.setDisplayMode(VectorDisplayMode.VECTOR_DISPLAY_MODE_LIC); view(s9,0.3,0,1.6,1600,900);
  }catch(Throwable e){ s.println("SCENA BLAD LIC: "+e); }
  try{ Scene s10=nowa("ZYWO_09_siatka_overset"); PartDisplayer pd=null; for(Object d:s10.getDisplayerManager().getObjects()) if(d instanceof PartDisplayer x) pd=x;
   if(pd==null) pd=s10.getDisplayerManager().createPartDisplayer("Siatka");
   pd.getInputParts().setObjects(scp); pd.setMesh(true); pd.setOutline(false); view(s10,0.3,0,2.5,1600,900);
  }catch(Throwable e){ s.println("SCENA BLAD siatka: "+e); }
  // ---- wykresy monitorow na zywo (raporty z przebiegu; monitor tworzony, jesli go brak; aktualizacja co krok czasu)
  String[][] wyk={{"ZYWO_W1 wysokosc plata i fala [m]","GODO_foil_y_centroid_m","GODO_eta_at_LE","GODO_eta_x-3.0"},{"ZYWO_W2 CL","AF_CL"},
   {"ZYWO_W3 sila oporu Fx [N]","AF_Fx"},{"ZYWO_W4 sila nosna / ciezar","GODO_lift_over_weight"},{"ZYWO_W5 Courant na powierzchni","GODO_interfaceCFL"}};
  for(String[] w:wyk){ try{
   List<Monitor> ms=new ArrayList<>();
   for(int k=1;k<w.length;k++){ Report r=null; try{ r=s.getReportManager().getReport(w[k]); }catch(Throwable e){} if(r==null){ s.println("brak raportu "+w[k]); continue; }
    ReportMonitor rm=null; for(Object o:s.getMonitorManager().getObjects()) if(o instanceof ReportMonitor x&&x.getReport()==r) rm=x;
    if(rm==null){ rm=r.createMonitor(); rm.setPresentationName(w[k]+" ZYWO"); }
    try{ rm.getStarUpdate().getUpdateModeOption().setSelected(StarUpdateModeOption.Type.TIMESTEP); }catch(Throwable e){}
    ms.add(rm); }
   if(!ms.isEmpty()) s.getPlotManager().createMonitorPlot(ms,w[0]);
  }catch(Throwable e){ s.println("WYKRES BLAD "+w[0]+": "+e); }}
  s.saveState(s.getSessionPath()); s.println("DodajIZapisz: zapisano "+s.getSessionPath());
 }
}
