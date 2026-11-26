import sys, csv, json, numpy as np
sys.path.insert(0,'/mnt/user-data/outputs/vortex_validation/model')
from uvm2d import Foil, G
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':9,'axes.spines.top':False,'axes.spines.right':False,'font.family':'DejaVu Sans'})
K='#111111'; R='#c0392b'; B='#1f6f8b'; O='#d98c1f'; Gy='#8a8f94'
# ---------- Rys. 1: schemat
fig,ax=plt.subplots(figsize=(7.4,2.55))
c=1.0; N=20; xe=np.linspace(0,c,N+1); xv=xe[:-1]+0.25/N; xc=xe[:-1]+0.75/N
ax.axhline(1.0,color=B,lw=1.2); ax.text(2.62,1.26,'średni poziom wody (linia ciągła) i fala',color=B,ha='right',va='bottom',fontsize=8)
xx=np.linspace(-0.6,2.65,300); ax.plot(xx,1.0+0.16*np.cos(2*np.pi*(xx-0.2)/2.6),color=B,lw=0.8,ls='--')
ax.plot([0,c],[0,0],color=K,lw=2.2); ax.plot(xv,0*xv,'o',color=R,ms=4,label='wir związany (20 szt.)'); ax.plot(xc,0*xc,'|',color=K,ms=7,label='punkt kontrolny: woda nie przechodzi przez płat')
xw=c+0.03+0.075*np.arange(20); ax.plot(xw,0*xw,'o',mfc='none',mec=R,ms=4,label='wiry śladu (pamięć opływu)')
ax.plot(np.r_[xv,xw],2.0+0*np.r_[xv,xw],'o',mfc='none',mec=Gy,ms=3,label='lustrzane odbicie (powierzchnia swobodna)')
ax.annotate('',xy=(-0.12,0.0),xytext=(-0.55,0.0),arrowprops=dict(arrowstyle='->',color=K)); ax.text(-0.62,0.07,'U = 12,35 m/s',fontsize=8)
ax.annotate('',xy=(-0.14,-0.03),xytext=(-0.5,-0.3),arrowprops=dict(arrowstyle='->',color=B)); ax.text(-0.62,-0.5,'napływ z falą (±3,7°)',fontsize=8,color=B)
ax.annotate('',xy=(0.17,0.52),xytext=(0.25,0.0),arrowprops=dict(arrowstyle='->',color=O,lw=1.6)); ax.text(0.30,0.40,'siła nośna pochylona\ndo przodu = ciąg',fontsize=8,color=O)
ax.annotate('',xy=(1.62,-0.02),xytext=(1.12,-0.22),arrowprops=dict(arrowstyle='->',color=R,lw=0.8)); ax.text(1.0,-0.42,'w każdym kroku nowy wir schodzi z krawędzi spływu',fontsize=8,color=R)
ax.text(0.5,-0.14,'cięciwa 0,312 m',ha='center',fontsize=8); ax.annotate('',xy=(2.45,1.0),xytext=(2.45,0.0),arrowprops=dict(arrowstyle='<->',color=Gy)); ax.text(2.48,0.5,'1,09 m',fontsize=8,color=Gy,va='center')
ax.set_xlim(-0.65,2.7); ax.set_ylim(-0.62,2.15); ax.axis('off'); ax.legend(loc='upper left',bbox_to_anchor=(0.30,0.93),fontsize=7.5,frameon=False,ncol=1)
fig.tight_layout(pad=0.2); fig.savefig('fig1.png',dpi=200); plt.close()
# ---------- Rys. 2: odtworzenie BASE2
hist='/mnt/user-data/uploads/NTNU_GODO_CONTROL_20261109/70_godo_case/overset_runs/OVS_PID_BASE2/history.csv'
rows=list(csv.DictReader(open(hist))); col=lambda k: np.array([float(r[k]) for r in rows])
t=col('time_s'); th=np.radians(col('theta_deg')); thd=np.radians(col('theta_rate_deg_s')); z=col('z_m'); v=col('v_m_s'); eta=col('GODO_eta_at_LE')
cl_u=col('AF_CL'); fx_u=col('AF_Fx')/0.02
rho,c,U,depth=1000.,0.312,12.3466667,1.09; dt=1e-3; om=2*np.pi/5; k=om*om/G; ome=om+k*U; Te=2*np.pi/ome; spp=int(round(Te/dt))
m=t>0.3; n=(m.sum()//spp)*spp; zc=2*np.mean((eta[m][:n]-eta[m][:n].mean())*np.exp(-1j*ome*t[m][:n])); a,beta=abs(zc),-np.angle(zc)
F=Foil(c=c,U=U,N=20,h=depth,dt=dt,wake_len=3*U*Te,rho=rho); idx=lambda tt: min(len(t)-1,max(0,int(round(tt/dt))-1)); qc=0.5*rho*U*U*c
def gust(x,tt):
    psi=k*x-ome*tt+beta; A=a*om*np.exp(-k*(depth-z[idx(tt)])); return A*np.cos(psi),A*np.sin(psi)
thm=th.mean()
fw=F.simulate(len(t),gust=gust); fp=F.simulate(len(t),theta=lambda tt:(th[idx(tt)]-thm,thd[idx(tt)])); fh=F.simulate(len(t),heave_rate=lambda tt:-v[idx(tt)])
ff=F.simulate(len(t),theta=lambda tt:(th[idx(tt)]-thm,thd[idx(tt)]),heave_rate=lambda tt:-v[idx(tt)],gust=gust)
Lw,Lp,Lh=[F.forces(f)['L'] for f in (fw,fp,fh)]
w=t>=1.9368
g1=np.linalg.solve(F.Abb,-U*np.ones(20)); dcl=rho*U*g1.sum()/qc
r0=F.forces(ff); thr=(cl_u[w].mean()-r0['CL'][w].mean())/dcl
mean=dict(theta0=thr+thm,G0=g1*thr,w0=F.Wvb@(g1*thr),u0=F.Uvb@(g1*thr)); ff['th']=ff['th']-thm; r=F.forces(ff,mean)
cal=dict(kw=0.6649389,kp=0.6277573,kh=0.6618295,dw=0.08,dp=0.0,dh=0.08)
sh=lambda y,d: np.r_[np.full(int(round(d/dt)),y[0]),y][:len(y)]
cl_c=(cal['kw']*sh(Lw,cal['dw'])+cal['kp']*sh(Lp,cal['dp'])+cal['kh']*sh(Lh,cal['dh']))/qc; cl_c=cl_c-cl_c[w].mean()+cl_u[w].mean()
def met(u,mm):
    u1,m1=u[w]-u[w].mean(),mm[w]-mm[w].mean(); return m1.std()/u1.std(), np.corrcoef(u1,m1)[0,1]
off=fx_u[w].mean()-r['Fx'][w].mean()
M=dict(raw=met(cl_u,r['CL']),cal=met(cl_u,cl_c),fx=met(fx_u,r['Fx']),cd=off/qc,a=a)
print(M)
wa=np.degrees(a*om*np.exp(-k*(depth-z))*np.sin(k*0.078-ome*t+beta)/U); ha=np.degrees(-v/U)*-1  # nurzanie w gore -> mniejszy kat
ha=np.degrees(-v/U); pa=np.degrees(th-thm)
sel=(t>=5.81)&(t<=11.62)
fig,ax=plt.subplots(3,1,figsize=(7.4,6.0),sharex=True,gridspec_kw=dict(height_ratios=[1,1,1]))
ax[0].plot(t[sel],wa[sel],color=B,label='od fali'); ax[0].plot(t[sel],ha[sel],color=O,label='od nurzania płata'); ax[0].plot(t[sel],pa[sel],color=Gy,label='od obrotu płata'); ax[0].plot(t[sel],(wa+ha+pa)[sel],color=K,lw=1.8,label='suma: kąt, pod jakim woda trafia w płat')
ax[0].set_ylabel('zmiana kąta napływu [°]'); ax[0].legend(ncol=2,fontsize=7.5,frameon=False,loc='upper center',bbox_to_anchor=(0.5,1.33)); ax[0].axhline(0,color='0.8',lw=0.6)
ax[1].plot(t[sel],cl_u[sel],color=K,lw=1.8,label='URANS'); ax[1].plot(t[sel],r['CL'][sel],color=R,ls=':',lw=1.3,label=('model surowy (amplituda ×%.2f)'%M['raw'][0]).replace('.',',')); ax[1].plot(t[sel],cl_c[sel],color=R,ls='--',lw=1.3,label=('model po kalibracji (×%.2f, korelacja %.3f)'%M['cal']).replace('.',','))
ax[1].set_ylabel('siła nośna CL'); ax[1].legend(ncol=3,fontsize=7.5,frameon=False,loc='upper center',bbox_to_anchor=(0.5,1.17))
ax[2].plot(t[sel],fx_u[sel],color=K,lw=1.8,label='URANS'); ax[2].plot(t[sel],(r['Fx']+off)[sel],color=R,ls='--',lw=1.3,label=('model + stały opór lepki (CD = %.4f); korelacja %.3f'%(M['cd'],M['fx'][1])).replace('.',','))
ax[2].set_ylabel('siła wzdłużna Fx [N/m]\n(dodatnia = opór)'); ax[2].set_xlabel('czas [s]'); ax[2].legend(ncol=2,fontsize=7.5,frameon=False,loc='upper center',bbox_to_anchor=(0.5,1.17))
for a_ in ax: a_.grid(alpha=0.25)
fig.tight_layout(pad=0.4); fig.savefig('fig2.png',dpi=200); plt.close()
json.dump({k:(list(map(float,v)) if isinstance(v,tuple) else float(v)) for k,v in M.items()},open('fig2_metrics.json','w'))
