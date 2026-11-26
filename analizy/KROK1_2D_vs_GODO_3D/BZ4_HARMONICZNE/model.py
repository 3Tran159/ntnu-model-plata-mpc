import sys, json, numpy as np
sys.path.insert(0,'../model'); sys.dont_write_bytecode=True
import faltinsen_plant as FP
from urans import harm, load, TE, OME, U, G
PID1=(2.01,0.196)
class PlantZ0(FP.FaltinsenPlant):
    """tlumienie predkosci orbitalnej z glebokoscia liczone dla zanurzenia projektowego (bez wplywu ruchu plata z)"""
    def gust(self,x,t):
        psi=self.k*x-self.ome*t+self.beta; A=self.A0*np.exp(-self.k*FP.DEPTH); return A*np.cos(psi),A*np.sin(psi)
def run(gain=0.85, t_rel=1.9368, t_end=11.621, beta=0.0, amp=0.73, cls=FP.FaltinsenPlant, th2=None, sub_fixed=False, **kw):
    P=cls(load=0.9, wave_amp=amp, wave_phase=beta, **kw); trim=float(np.degrees(P.th_ref)); P.reset(theta_deg=trim); ie=0.0
    if sub_fixed:   # (6.144) i opor falowy dla stalego zanurzenia projektowego: chwilowa bliskosc powierzchni wylaczona
        P.submergence=lambda t=None: FP.DEPTH
    n=int(round(t_end/P.dt)); rec=[]
    for i in range(n):
        free=P.t>=t_rel-1e-9
        if i%P.tick==0:
            cmd=trim
            if free: ie=float(np.clip(ie+(-P.z)*P.tick*P.dt,-1,1)); cmd=trim+PID1[0]*(-P.z)+PID1[1]*ie
            if gain: cmd-=gain*float(np.degrees(float(np.mean(P.gust(P.F.xc,P.t)[1]))/U))
            if th2 is not None: cmd+=th2[0]*np.cos(2*OME*P.t-np.radians(th2[1]))
            P.cmd=np.radians(float(np.clip(cmd,-7.5,7.5)))
        r=P.step(free_heave=free)
        rec.append((r['t'],(r['L']+FP.BUOY)/P.mass-G,r['L']*FP.SPAN,r['CL'],r['theta_deg'],r['z'],r['eta_LE'],r['P_drag_W_strip'],np.degrees(P.cmd)))
    return np.array(rec),trim,P
def H(a,win=3,t_end=None):
    t=a[:,0]; te=t[-1] if t_end is None else t_end; m=(t>te-win*TE-1e-9)&(t<=te+1e-9); tt=t[m]
    return {k:harm(tt,a[m,i]) for i,k in ((1,'acc'),(2,'Fy'),(3,'CL'),(4,'theta'),(5,'z'),(6,'eta'),(7,'P'),(8,'cmd'))}
def line(name,h):
    return f"{name:44s} z'' amp1 {h['acc']['amp'][0]:.3f} amp2 {h['acc']['amp'][1]:.3f} amp3 {h['acc']['amp'][2]:.3f} amp4 {h['acc']['amp'][3]:.3f} amp5 {h['acc']['amp'][4]:.3f} rms {h['acc']['rms']:.3f} | CL a1 {h['CL']['amp'][0]:.4f} a2 {h['CL']['amp'][1]:.4f} | th a1 {h['theta']['amp'][0]:.3f} a2 {h['theta']['amp'][1]:.3f} | z a1 {h['z']['amp'][0]:.4f} | P {h['P']['mean']:.2f} | fazy acc {h['acc']['ph'][0]:+.0f} {h['acc']['ph'][1]:+.0f} th {h['theta']['ph'][0]:+.0f} {h['theta']['ph'][1]:+.0f}"
if __name__=='__main__':
    A,_=load('../data/K0.csv'); t=A['time_s']; m=t>=t[-1]-3*TE
    he=harm(t[m],A['GODO_eta_at_LE'][m]); hc=harm(t[m],A['theta_cmd_deg'][m]); ht=harm(t[m],A['theta_deg'][m])
    print('URANS eta_LE amp1',he['amp'][0],'faza',he['ph'][0],'| theta_cmd amp1,2',hc['amp'][:2],'fazy',hc['ph'][:2],'sr',hc['mean'],'| theta amp',ht['amp'][:2],'fazy',ht['ph'][:2])
    beta=np.radians(he['ph'][0]); amp=he['amp'][0]
    out={}
    cases=[('A pelny model B',dict()),('B bez poziomej predkosci fali (u)',dict(wave_u=False)),('C bez chwilowej bliskosci powierzchni (6.144)',dict(sub_fixed=True)),
           ('D tlumienie fali dla stalego zanurzenia',dict(cls=PlantZ0)),('E bez u, bez 6.144, stale zanurzenie',dict(wave_u=False,sub_fixed=True,cls=PlantZ0)),
           ('F bez powierzchni swobodnej w ogole',dict(free_surface=False)),
           ('G pelny + 2. harmoniczna komendy jak w URANS',dict(th2=(hc['amp'][1],hc['ph'][1]))),
           ('H jak E + 2. harmoniczna komendy',dict(wave_u=False,sub_fixed=True,cls=PlantZ0,th2=(hc['amp'][1],hc['ph'][1])))]
    for name,kw in cases:
        a,trim,P=run(beta=beta,amp=amp,**kw); h=H(a); out[name]=h; print(line(name,h),flush=True)
    a,trim,P=run(beta=beta,amp=amp,t_end=1.9368*31+0.0); h=H(a); out['A30 pelny, 30 okresow']=h; print(line('A30 pelny model B, 30 okresow (ustalony)',h)); print('trim',trim,'mass',P.mass,'cl_ref',P.cl_ref)
    json.dump(dict(beta_deg=he['ph'][0],amp=amp,trim=trim,wyniki=out),open('MODEL_HARM.json','w'),indent=1)
