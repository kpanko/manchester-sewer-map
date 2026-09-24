"""Build storm.html from data/manchester-storm-network.json.

Each storm pipe is linked to the pipe it drains into (the town's downstream ID when it's within
100 ft, otherwise pipe geometry), then followed to where the water ends up: an outfall into a
stream or pond, a dry well or infiltrator, a detention basin, or a gap in the data. Outfalls are
matched to the nearest pond or stream on the town's water-body map. Street names come from the
nearest street centerline (data/manchester-sewer-network.json).
"""
import json,collections,math,os
HERE=os.path.dirname(os.path.abspath(__file__))
D=json.load(open(os.path.join(HERE,'..','data','manchester-storm-network.json')))
F=D['pipeFields'];P=[dict(zip(F,p)) for p in D['pipes']]
OF=D['outletFields'];O=[dict(zip(OF,o)) for o in D['outlets']]
Oid={o['id']:k for k,o in enumerate(O)}
for i,p in enumerate(P):
    p['i']=i; p['pts']=[(pl[k],pl[k+1]) for pl in p['paths'] for k in range(0,len(pl),2)]
    p['s']=p['pts'][0]; p['e']=p['pts'][-1]
LIVE=lambda q: q['status'] not in ('PROPOSED','ABANDONED')
up=collections.defaultdict(list)
for p in P:
    if p['up'] is not None: up[p['up']].append(p)
CS=40
def cellsOf(a,b):
    x0,x1=sorted((a[0],b[0]));y0,y1=sorted((a[1],b[1]))
    for cx in range(int(x0//CS),int(x1//CS)+1):
        for cy in range(int(y0//CS),int(y1//CS)+1): yield (cx,cy)
G=collections.defaultdict(list)
for p in P:
    for pl in p['paths']:
        pts=[(pl[k],pl[k+1]) for k in range(0,len(pl),2)]
        for a,b in zip(pts,pts[1:]):
            for c in cellsOf(a,b): G[c].append((p['i'],a,b))
def dseg(pt,a,b):
    ax,ay=a;bx,by=b;px,py=pt;dx,dy=bx-ax,by-ay;L=dx*dx+dy*dy
    t=0 if L==0 else max(0,min(1,((px-ax)*dx+(py-ay)*dy)/L))
    return math.hypot(ax+t*dx-px,ay+t*dy-py)
def near(pt,tol):
    out={};cx,cy=int(pt[0]//CS),int(pt[1]//CS)
    for gx in (cx-1,cx,cx+1):
        for gy in (cy-1,cy,cy+1):
            for i,a,b in G.get((gx,gy),()):
                d=dseg(pt,a,b)
                if d<=tol and (i not in out or d<out[i]): out[i]=d
    return out
# point sets: outlets, dry wells
def pgrid(pts):
    g=collections.defaultdict(list)
    for k,(x,y) in enumerate(pts):
        if x<-1e8: continue
        g[(int(x//CS),int(y//CS))].append(k)
    return g
OP=[(o['x'],o['y']) if o['x'] is not None else (-1e9,-1e9) for o in O]; OG=pgrid(OP)
DW=[(D['dryWells'][k],D['dryWells'][k+1]) for k in range(0,len(D['dryWells']),2)]; DG=pgrid(DW)
def nearest(g,pts,pt,tol):
    best=None;bd=tol;cx,cy=int(pt[0]//CS),int(pt[1]//CS)
    for gx in (cx-1,cx,cx+1):
        for gy in (cy-1,cy,cy+1):
            for k in g.get((gx,gy),()):
                d=math.dist(pts[k],pt)
                if d<=bd: best,bd=k,d
    return best
def size(q): return max(q['dia'] or 0,q['h'] or 0,q['w'] or 0)
def nxt(p):
    # explicit outlet
    if p['dn'] in Oid: return ('O',Oid[p['dn']]),'id'
    if p['dn'] is not None:
        c=[q for q in up.get(p['dn'],[]) if q['i']!=p['i']]
        c=[q for q in c if math.dist(q['s'],p['e'])<=20 or near(p['e'],20).get(q['i']) is not None]
        cl=[q for q in c if LIVE(q)] or c
        if cl: return ('P',max(cl,key=lambda q:(size(q),-(q['uinv'] or 1e9)))['i']),'id'
    TOL=3
    nb=near(p['e'],TOL); nb.pop(p['i'],None)
    c=[P[i] for i in nb if math.dist(P[i]['s'],p['e'])<=TOL and LIVE(P[i])]
    c=[q for q in c if not (q['dn'] is not None and q['dn']==p['up']) and math.dist(q['e'],p['s'])>TOL]
    if c: return ('P',max(c,key=size)['i']),'geom-start'
    k=nearest(OG,OP,p['e'],6)
    if k is not None: return ('O',k),'geom-outlet'
    k=nearest(DG,DW,p['e'],6)
    if k is not None: return ('W',k),'geom-drywell'
    c=[P[i] for i in nb if math.dist(P[i]['e'],p['e'])>TOL and LIVE(P[i]) and size(P[i])>=size(p)]
    if c: return ('P',max(c,key=size)['i']),'geom-tie'
    return None,'end'
NX=[];HOW=[]
for p in P:
    t,h=nxt(p); NX.append(t); HOW.append(h)
def trace(i):
    seen=set();path=[]
    while i is not None and i not in seen:
        seen.add(i);path.append(i)
        t=NX[i]
        if t is None: return path,None
        if t[0]!='P': return path,t
        i=t[1]
    return path,('LOOP',i)

# ---- terminals & receiving water ----
def pip(pt,ring):
    x,y=pt;ins=False
    for k in range(0,len(ring)-2,2):
        x1,y1,x2,y2=ring[k],ring[k+1],ring[k+2],ring[k+3]
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1+1e-12)+x1: ins=not ins
    return ins
def ringdist(pt,ring):
    return min(dseg(pt,(ring[k],ring[k+1]),(ring[k+2],ring[k+3])) for k in range(0,len(ring)-2,2))
def mkpolys(lst):
    out=[]
    for t,n,rings in lst:
        xs=[r[k] for r in rings for k in range(0,len(r),2)];ys=[r[k] for r in rings for k in range(1,len(r),2)]
        out.append((t,n,rings,(min(xs),min(ys),max(xs),max(ys))))
    return out
WAT=mkpolys(D['water']); DET=mkpolys([(d[0],d[1],d[2]) for d in D['detention']])
def poly_at(polys,pt,tol,named=False):
    best=None;bd=tol+1e-9
    for j,(t,n,rings,bb) in enumerate(polys):
        if named and not n: continue
        x0,y0,x1,y1=bb
        if pt[0]<x0-tol or pt[0]>x1+tol or pt[1]<y0-tol or pt[1]>y1+tol: continue
        for r in rings:
            d=0 if pip(pt,r) else ringdist(pt,r)
            if d<bd: best,bd=j,d
    return best,bd
TT=['Outfall','Soaks into ground','Detention basin','Pond or stream','Trace ends (data gap)']
TERM={}   # key -> dict
def term_key(path,t):
    last=P[path[-1]]
    if t is not None and t[0]=='O':
        o=O[t[1]]; return ('O',t[1]), (o['x'],o['y']) if o['x'] is not None else last['e']
    if t is not None and t[0]=='W': return ('W',t[1]), DW[t[1]]
    pre=str(last['dn'])[:2] if last['dn'] else ''
    if pre in ('85','86'): return ('O*',last['i']), last['e']
    if pre in ('90','93'): return ('G',last['i']), last['e']
    j,d=poly_at(DET,last['e'],4)
    if j is not None or pre=='94': return ('D',last['i']), last['e']
    j,d=poly_at(WAT,last['e'],4)
    if j is not None: return ('R',last['i']), last['e']
    return ('X',last['i']), last['e']
KIND={'O':0,'O*':0,'W':1,'G':1,'D':2,'R':3,'X':4,'LOOP':4}
PTERM=[None]*len(P)
for p in P:
    if PTERM[p['i']] is not None: continue
    path,t=trace(p['i'])
    if t is not None and t[0]=='LOOP': key,pt=('X',path[-1]),P[path[-1]]['e']
    else: key,pt=term_key(path,t)
    if key not in TERM:
        kind=KIND[key[0]]
        info={'kind':kind,'x':pt[0],'y':pt[1]}
        if kind in (0,3):
            j,d=poly_at(WAT,pt,60)          # within 300 ft
            jn,dn=poly_at(WAT,pt,300,True)  # named within 1500 ft
            info['water']=(WAT[j][1] or ('unnamed '+(WAT[j][0] or 'water').lower()), round(d*5)) if j is not None else None
            info['named']=(WAT[jn][1], round(dn*5)) if jn is not None else None
        if key[0]=='O':
            o=O[key[1]]; info.update(outlet=o['id'],otype=o['type'],omat=o['mat'],ms4=o['ms4name'],oremarks=o['remarks'],oinv=o['inv'])
        TERM[key]=info
    for i in path:
        if PTERM[i] is None: PTERM[i]=key


SW=json.load(open(os.path.join(HERE,'..','data','manchester-sewer-network.json')))
assert SW['X0']==D['X0'] and SW['Y0']==D['Y0'] and SW['unit']==D['unit']
streets=[[n,[[c for xy in pl for c in xy] for pl in v]] for n,v in SW['streets'].items() if n]
# street grid for nearest-street lookup
SG=collections.defaultdict(list)
for si,(n,paths) in enumerate(streets):
    for f in paths:
        pts=[(f[k],f[k+1]) for k in range(0,len(f),2)]
        for a,b in zip(pts,pts[1:]):
            for c in cellsOf(a,b): SG[c].append((si,a,b))
def street_of(pt,tol=20):  # 100 ft
    best=-1;bd=tol;cx,cy=int(pt[0]//CS),int(pt[1]//CS)
    for gx in (cx-1,cx,cx+1):
        for gy in (cy-1,cy,cy+1):
            for si,a,b in SG.get((gx,gy),()):
                d=dseg(pt,a,b)
                if d<bd: best,bd=si,d
    return best
names=[n for n,_ in streets]
def mid(p):
    pts=p['pts'];return pts[len(pts)//2]
# terminals
tkeys=list(TERM.keys()); tidx={k:i for i,k in enumerate(tkeys)}
# basin mosaic coloring for outfall basins
cells=collections.defaultdict(set)
for p in P:
    t=tidx[PTERM[p['i']]]
    for pt in p['pts'][::2]: cells[(int(pt[0]//40),int(pt[1]//40))].add(t)
adj=collections.defaultdict(set)
for (cx,cy),ts in cells.items():
    around=set()
    for gx in (cx-1,cx,cx+1):
        for gy in (cy-1,cy,cy+1): around|=cells.get((gx,gy),set())
    for t in ts: adj[t]|=around-{t}
size_of=collections.Counter(tidx[k] for k in PTERM)
color=[-1]*len(tkeys); NC=6
for t in sorted(range(len(tkeys)),key=lambda t:-size_of[t]):
    used={color[u] for u in adj[t] if color[u]>=0}
    # prefer least-used-nearby color deterministic
    color[t]=next((c for c in range(NC) if c not in used), min(range(NC),key=lambda c:sum(1 for u in adj[t] if color[u]==c)))
def nxt_idx(i):
    t=NX[i]; return t[1] if t is not None and t[0]=='P' else -1
recs=[]
for p in P:
    recs.append([p['id'],p['dia'],p['h'],p['w'],p['shape'] or '',p['mat'] or '',p['culvert'] or '',p['uinv'],p['dinv'],p['owner'] or '',p['yr'] or 0,
                 {'PROPOSED':'P','CONSTRUCTED':'C','ABANDONED':'A'}.get(p['status'],'U'),p['remarks'] or '',p['len'],street_of(mid(p)),tidx[PTERM[p['i']]],nxt_idx(p['i']),p['paths']])
terms=[]
for k in tkeys:
    v=TERM[k]
    terms.append([v['kind'],round(v['x']),round(v['y']),color[tidx[k]],v.get('water'),v.get('named'),v.get('outlet'),v.get('otype'),v.get('omat'),v.get('ms4'),v.get('oremarks'),v.get('oinv')])
out={'X0':D['X0'],'Y0':D['Y0'],'unit':5,'names':names,'pipes':recs,'terms':terms,
     'cb':[v for k in range(0,len(D['catchBasins']),2) if D['catchBasins'][k] is not None and D['catchBasins'][k+1] is not None for v in D['catchBasins'][k:k+2]],'dw':D['dryWells'],
     'water':[[w[0] or '',w[1] or '',w[2]] for w in D['water']],'det':[d[2] for d in D['detention']],
     'streets':streets}
page=open(os.path.join(HERE,'storm_template.html')).read().replace('__DATA__',json.dumps(out,separators=(',',':')))
doc=('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
     '<style>*,*::before,*::after{box-sizing:border-box}body{margin:0}</style>\n</head>\n<body>\n'+page+'\n</body>\n</html>\n')
open(os.path.join(HERE,'..','storm.html'),'w').write(doc)
k=collections.Counter(TT[TERM[t]['kind']] for t in PTERM)
print(f"storm.html written: {len(P)} pipes; " + ", ".join(f"{n}: {c}" for n,c in k.most_common()))
