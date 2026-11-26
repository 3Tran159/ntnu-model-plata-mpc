import numpy as np, json, csv
class DF(dict):
    def __getattr__(s,k): return s[k]
class PD:
    @staticmethod
    def read_csv(f):
        r=list(csv.reader(open(f))); h=r[0]; rows=[x for x in r[1:] if len(x)==len(h)]
        D={}
        for i,k in enumerate(h):
            try: D[k]=np.array([float(x[i]) for x in rows])
            except: D[k]=np.array([x[i] for x in rows])
        t=D['time_s']; o=np.argsort(t,kind='stable'); u={};
        for j in o: u[t[j]]=j
        idx=np.array(sorted(u.values(),key=lambda j:t[j]))
        return DF({k:v[idx] for k,v in D.items()})
pd=PD()
f=r'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\OVS_K0_85_90\history.csv'
d=pd.read_csv(f)
t=d.time_s; Te=1.9368; tend=t[-1]; ref=58.9089
acc=np.gradient(d.v_m_s,t)
out={'tend':tend,'n':len(d)}
for n in (3,4):
    m=t>tend-n*Te
    out[f'P{n}']=d.P_drag_W[m].mean(); out[f'dP{n}']=100*(out[f'P{n}']/ref-1)
    out[f'acc{n}']=np.sqrt(np.mean((acc[m]-acc[m].mean())**2))
    out[f'Pact{n}']=d.P_act_W[m].mean()
per=[]
for k in range(6):
    m=(t>tend-(k+1)*Te)&(t<=tend-k*Te)
    per.append(round(100*(d.P_drag_W[m].mean()/ref-1),1))
out['per_period_dP_newest_first']=per
m=t>tend-3*Te
out['th_mean']=d.theta_deg[m].mean(); out['th_amp']=(d.theta_deg[m].max()-d.theta_deg[m].min())/2
out['cmd_amp']=(d.theta_cmd_deg[m].max()-d.theta_cmd_deg[m].min())/2
out['z_mean']=d.z_m[m].mean(); out['z_amp']=(d.z_m[m].max()-d.z_m[m].min())/2
e=d.GODO_eta_at_LE[m]; c=d.theta_cmd_deg[m]
out['corr_cmd_eta']=float(np.corrcoef(e,c)[0,1])
out['sat_pct']=100*np.mean(np.abs(d.theta_deg[m])>7.4)
out['CL']=d.AF_CL[m].mean(); out['CD']=d.AF_CD[m].mean()
print(json.dumps({k:(round(v,4) if isinstance(v,float) else v) for k,v in out.items()}))
# timeseries for dashboard (last 2 periods, 20 Hz)
m=np.where(t>tend-2*Te)[0][::50]; s=DF({k:v[m] for k,v in d.items()})
json.dump({'t':list(np.round(s.time_s-s.time_s[0],3)),'eta':list(np.round(s.GODO_eta_at_LE,4)),'zf':list(np.round(s.z_m,4)),'th':list(np.round(s.theta_deg,3))},open(r'T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI\k0_90_ts.json','w'))




m=t>tend-3*Te; e=d.GODO_eta_at_LE[m]; de=np.gradient(e,t[m]); c=d.theta_cmd_deg[m]; th=d.theta_deg[m]
print('corr cmd vs deta/dt',np.corrcoef(c,de)[0,1],'corr cmd vs eta',np.corrcoef(c,e)[0,1])
print('cmd std',c.std(),'th std',th.std(),'cmd-th corr',np.corrcoef(c,th)[0,1])
from numpy.fft import rfft,rfftfreq
F=rfftfreq(len(c),t[1]-t[0]); A=np.abs(rfft(c-c.mean()))*2/len(c); i=np.argsort(A)[-5:]; print('cmd peaks Hz/amp',[(round(F[j],2),round(A[j],2)) for j in i])
A2=np.abs(rfft(th-th.mean()))*2/len(c); print('th at peaks',[(round(F[j],2),round(A2[j],2)) for j in i])
print('eta amp',(e.max()-e.min())/2)

m=t>tend-3*Te; a=acc[m]-acc[m].mean(); F=rfftfreq(len(a),0.001); A=rfft(a)*2/len(a)
fe=1/Te; print('acc rms all',a.std())
for h in range(1,6):
    j=np.argmin(abs(F-h*fe)); print(h, round(F[j],3), round(abs(A[j]),3))
lp=np.sqrt(sum(abs(A[(F>0)&(F<5)])**2)/2); print('acc rms <5Hz',lp); print('acc rms >5Hz',np.sqrt(sum(abs(A[F>=5])**2)/2))
