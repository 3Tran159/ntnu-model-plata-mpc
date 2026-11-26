import pickle, susp_mpc as SM, mpc_irr as M, mpc_irr2 as M2
_, pred = pickle.loads(open("MPC_IRR2_MODEL.pkl","rb").read())
mdl = SM.phys_fix(M.identify(M2.collect_spread(seeds=range(100,102))))
for args in [("sztywne","MPC",0.0),("pasywne_1.5Hz","MPC",0.0),("polaktywne_v2","MPC",0.0)]:
    print(args, SM.run(5,*args,mdl,pred,T=6.0), flush=True)
