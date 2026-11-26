"""Tworzy KOPIE makra GodoOversetRun.java z trybem mode=policy (oryginal w 70_godo_case nietkniety).
Wynik: 50_learning/vortex_env/stars/GodoOversetRun.java  (ta sama nazwa klasy - do uzycia w katalogu przypadku zamiast oryginalu).
Tryb policy: co tick (10 ms) obserwacje jak w GodoVortexEnv: z, dz/dt, eta nad LE (raport GODO_eta_at_LE),
  w_surface = (omega/omega_e) d(eta)/dt (pionowa predkosc wody na sredniej powierzchni), poprzednia komenda a = theta_cmd/7,5;
  siec z pliku policy_file (format z export_policy.py); theta_cmd = 7,5 deg * a (kat bezwzgledny). Przed release_s jak 'hold'.
"""
from pathlib import Path
SRC = Path(r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\GodoOversetRun.java")
DST = Path(__file__).parent / "stars" / "GodoOversetRun.java"; DST.parent.mkdir(exist_ok=True)
s = SRC.read_text(encoding="utf-8")

helpers = r'''
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
'''
s = s.replace(" static double clamp(double x,double a){return Math.max(-a,Math.min(a,x));}",
              " static double clamp(double x,double a){return Math.max(-a,Math.min(a,x));}\n" + helpers, 1)
s = s.replace('   String mode=cfg.getProperty("mode","pid");',
              '   String mode=cfg.getProperty("mode","pid");\n   if(mode.equals("policy"))loadPolicy(cfg.getProperty("policy_file"));\n'
              '   double omW=2*Math.PI/d("wave_period_s",5.0),omE=2*Math.PI/d("encounter_period_s",1.9368);', 1)
old = '''      if(!mode.equals("hold")&&free){
       ie+=e*tick_dur; ie=clamp(ie,d("ie_max",1.0));'''
new = '''      double etaNow=rv("GODO_eta_at_LE");if(!Double.isFinite(etaNow))etaNow=0;
      double wSurf=(omW/omE)*(etaNow-sd("etaPrev",etaNow))/tick_dur;st.setProperty("etaPrev",""+etaNow);
      if(mode.equals("policy")&&free){
       double aPrev=Double.parseDouble(st.getProperty("cmd",""+d("pitch_trim_deg",0)))/thMax;
       double a=policy(new double[]{z,v,etaNow,wSurf,aPrev});
       cmd=thMax*a;st.setProperty("obs_last",z+" "+v+" "+etaNow+" "+wSurf+" "+aPrev+" -> "+a);
      }else
      if(!mode.equals("hold")&&free){
       ie+=e*tick_dur; ie=clamp(ie,d("ie_max",1.0));'''
assert old in s, "nie znaleziono bloku regulatora"
s = s.replace(old, new, 1)
s = s.replace(" * Controllers (mode):", " * Controllers (mode):\n *   policy : siec aktora z pliku policy_file (TD3/SAC wytrenowane w modelu wirowym; KOPIA makra z 50_learning/vortex_env/stars)", 1)
DST.write_text(s, encoding="utf-8")
print("zapisano", DST)
