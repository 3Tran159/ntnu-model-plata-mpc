import numpy as np, csv, json, sys
TE=1.9368; OME=2*np.pi/TE; U=12.3466667; G=9.81
def load(f):
    R=list(csv.DictReader(open(f))); cols=[k for k in R[0] if k!='mode']
    A={k:np.array([float(r[k]) for r in R]) for k in cols}; A['mode']=[r['mode'] for r in R]
    t=A['time_s']; # usun duplikaty czasu (zostaw ostatni)
    _,idx=np.unique(np.round(t,6)[::-1],return_index=True); keep=np.sort(len(t)-1-idx)
    n0=len(t); A={k:(v[keep] if k!='mode' else [v[i] for i in keep]) for k,v in A.items()}
    return A,n0-len(keep)
def harm(t,y,nh=5,trend=True):
    cols=[np.ones_like(t)]+([t-t.mean()] if trend else [])
    for n in range(1,nh+1): cols+= [np.cos(n*OME*t),np.sin(n*OME*t)]
    M=np.stack(cols,1); c,res,_,_=np.linalg.lstsq(M,y,rcond=None); o=2 if trend else 1
    amp=[float(np.hypot(c[o+2*i],c[o+2*i+1])) for i in range(nh)]; ph=[float(np.degrees(np.arctan2(c[o+2*i+1],c[o+2*i]))) for i in range(nh)]
    return dict(mean=float(c[0]),trend=float(c[1]) if trend else 0.0,amp=amp,ph=ph,resid_rms=float(np.sqrt(np.mean((y-M@c)**2))),rms=float(np.std(y)))
if __name__=='__main__':
    A,nd=load('../data/K0.csv'); t=A['time_s']; print('wiersze',len(t),'duplikaty usuniete',nd,'t_end',t[-1],'dt',np.median(np.diff(t)))
    modes=A['mode']; ch=[(t[i],modes[i]) for i in range(1,len(t)) if modes[i]!=modes[i-1]]; print('mode start',modes[0],'zmiany',ch[:5])
    i0=np.argmax(np.abs(A['v_m_s'])>1e-9); print('pierwszy ruch t=',t[i0])
    for win in (3,4):
        m=t>=t[-1]-win*TE; tt=t[m]; acc=np.gradient(A['v_m_s'][m],tt)
        print(f'--- okno {win} okresow: {tt[0]:.3f}-{tt[-1]:.3f} s')
        for name,y in (('acc z gradientu v [m/s2]',acc),('acc z L/W [m/s2]',G*(A['GODO_lift_over_weight'][m]-1)),('Fy_fluid [N/pasek]',A['GODO_Fy_fluid'][m]),('AF_CL',A['AF_CL'][m]),
                       ('theta [deg]',A['theta_deg'][m]),('z [m]',A['z_m'][m]),('eta_LE [m]',A['GODO_eta_at_LE'][m]),('eta_upstream [m]',A['GODO_eta_upstream_quarter_lambda'][m]),('P_drag [W]',A['P_drag_W'][m])):
            h=harm(tt,y); print(f"{name:26s} sr {h['mean']:+.4f} rms {h['rms']:.4f} | amp1-5 "+' '.join(f'{a:.4f}' for a in h['amp'])+' | faza1,2 '+f"{h['ph'][0]:+.0f} {h['ph'][1]:+.0f} | reszta {h['resid_rms']:.4f}")
