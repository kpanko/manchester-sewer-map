"""Build index.html from data/manchester-sewer-network.json.

For every pipe, find the pipe it drains into: the town's downstream ID link when that link is
geometrically plausible (within 100 ft), otherwise the pipe that starts at or passes through
this pipe's downstream end. Following those links gives each pipe's destination
(treatment plant, neighboring town, or a gap in the data).
"""
import os
HERE=os.path.dirname(os.path.abspath(__file__))
import json,collections,math
D=json.load(open(os.path.join(HERE,'..','data','manchester-sewer-network.json')))
F=D['fields'];P=[dict(zip(F,p)) for p in D['pipes']]
for i,p in enumerate(P):
    p['i']=i; p['s']=tuple(p['paths'][0][0]); p['e']=tuple(p['paths'][-1][-1])
up=collections.defaultdict(list)
for p in P:
    if p['up'] is not None: up[p['up']].append(p)
# spatial index grid of segments
G=collections.defaultdict(list); CS=40
def cells(a,b):
    x0,x1=sorted((a[0],b[0]));y0,y1=sorted((a[1],b[1]))
    for cx in range(int(x0//CS),int(x1//CS)+1):
        for cy in range(int(y0//CS),int(y1//CS)+1): yield (cx,cy)
for p in P:
    for pl in p['paths']:
        for a,b in zip(pl,pl[1:]):
            for c in cells(a,b): G[c].append((p['i'],tuple(a),tuple(b)))
def dseg(pt,a,b):
    ax,ay=a;bx,by=b;px,py=pt;dx,dy=bx-ax,by-ay;L=dx*dx+dy*dy
    t=0 if L==0 else max(0,min(1,((px-ax)*dx+(py-ay)*dy)/L))
    return math.hypot(ax+t*dx-px,ay+t*dy-py),t
def near(pt,tol):
    out={}
    cx,cy=int(pt[0]//CS),int(pt[1]//CS)
    for gx in (cx-1,cx,cx+1):
        for gy in (cy-1,cy,cy+1):
            for i,a,b in G.get((gx,gy),()):
                d,_=dseg(pt,a,b)
                if d<=tol and (i not in out or d<out[i]): out[i]=d
    return out
LIVE=lambda q: q['status'] not in ('PROPOSED',) and q['flow'] not in ('INACTIVE',)
def nxt(p):
    if p['dn'] is not None:
        c=[q for q in up.get(p['dn'],[]) if q['i']!=p['i']]
        c=[q for q in c if math.dist(q['s'],p['e'])<=20 or near(p['e'],20).get(q['i']) is not None]
        cl=[q for q in c if LIVE(q)] or c
        if cl: return max(cl,key=lambda q:(q['dia'] or 0,-(q['uinv'] or 1e9))),'id'
    TOL=3  # 15 ft
    nb=near(p['e'],TOL); nb.pop(p['i'],None)
    # continuation: pipe starting at our end
    c=[P[i] for i in nb if math.dist(P[i]['s'],p['e'])<=TOL and LIVE(P[i])]
    c=[q for q in c if not (q['dn'] is not None and q['dn']==p['up'])]
    if c: return max(c,key=lambda q:(q['dia'] or 0)),'geom-start'
    # tie-in mid pipe (not a pipe ending here, which would be an upstream neighbour)
    c=[P[i] for i in nb if math.dist(P[i]['e'],p['e'])>TOL and LIVE(P[i])]
    if p['dinv'] is not None: c=[q for q in c if q['uinv'] is None or q['dinv'] is None or min(q['uinv'],q['dinv'])<=p['dinv']+2]
    if c: return max(c,key=lambda q:(q['dia'] or 0)),'geom-tie'
    return None,'end'
NX=[];HOW=[]
for p in P:
    q,h=nxt(p); NX.append(q['i'] if q else -1); HOW.append(h)
def trace(i):
    seen=set();path=[]
    while i!=-1 and i not in seen:
        seen.add(i);path.append(i);i=NX[i]
    return path,(i!=-1)

import re
PLANT={7701315,7704024,7706398}
pid={s[0] for s in D['pumps']}
def plen(p): return sum(math.dist(a,b) for pl in p['paths'] for a,b in zip(pl,pl[1:]))*5
DEST={}
for p in P:
    path,loop=trace(p['i']); t=P[path[-1]]
    if loop: d=6
    elif t['id'] in PLANT: d=0
    elif t['flow']=='TO_VERN': d=1
    elif t['flow']=='TO_SW': d=2
    elif t['flow']=='TO_MDC': d=3
    elif t['flow']=='TO_SEPTIC': d=4
    elif t['flow']=='INACTIVE': d=5
    else: d=6
    p['dest']=d
    p['fm']=1 if (p['up'] in pid or (p['remarks'] and re.search(r'force main',p['remarks'],re.I))) else 0


pidx={s[0]:k for k,s in enumerate(D['pumps'])}
recs=[[p['id'],p['dia'] or 0,p['mat'] or '',p['uinv'],p['dinv'],p['street'],p['dest'],NX[p['i']],p['fm'],pidx.get(p['dn'],-1),p['yr'] or 0,(p['owner'] or '').strip(),{'PROPOSED':'P','CONSTRUCTED':'C'}.get(p['status'],'U'),p['remarks'] or '',round(plen(p)),[[c for xy in pl for c in xy] for pl in p['paths']]] for p in P]
out={'X0':D['X0'],'Y0':D['Y0'],'unit':5,'names':D['streetNames'],'pipes':recs,
     'pumps':[[s[1] or '',(s[2] or '').strip(),s[3] or '',s[4] or 0,s[5],s[6]] for s in D['pumps']],
     'streets':[[n,[[c for xy in pl for c in xy] for pl in v]] for n,v in D['streets'].items() if n]}
page=open(os.path.join(HERE,'template.html')).read().replace('__DATA__',json.dumps(out,separators=(',',':')))
doc=('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
     '<style>*,*::before,*::after{box-sizing:border-box}body{margin:0}</style>\n</head>\n<body>\n'+page+'\n</body>\n</html>\n')
open(os.path.join(HERE,'..','index.html'),'w').write(doc)
c=collections.Counter(p['dest'] for p in P)
print(f"index.html written: {len(P)} pipes; to plant {c[0]}, Vernon {c[1]}, South Windsor {c[2]}, MDC {c[3]}, other/gap {c[4]+c[5]+c[6]}")
