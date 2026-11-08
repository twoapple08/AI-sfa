"""SFA 기본 뼈대의 움직임으로 기존 스미어의 유형을 선택하는 검토 도구. 영상 입력 없음."""
import copy
import xml.etree.ElementTree as E
import numpy as np

BASE=4560000
PARTS={4:(1,0),6:(1,0),8:(0,1),10:(0,1)}


def points(ao,canvas):
    return np.array([[float(p.get('X'))*canvas[0]/100,float(p.get('Y'))*canvas[1]/100] for p in ao.findall('AP')])


def group_effects(frame,canvas):
    aos=[a for a in frame.findall('AO') if a.get('LayerId')=='1' and (int(a.get('Color'))>>24)&255]
    bypoint={p.get('ID'):a.get('ID') for a in aos for p in a.findall('AP')};parent={a.get('ID'):a.get('ID') for a in aos}
    def find(x):
        while parent[x]!=x:x=parent[x]
        return x
    for a in aos:
        for c in a.findall('.//AC'):
            if c.get('ConnPtId') in bypoint:parent[find(a.get('ID'))]=find(bypoint[c.get('ConnPtId')])
    groups={}
    for a in aos:groups.setdefault(find(a.get('ID')),[]).append(a)
    out=[]
    for objects in groups.values():
        objects.sort(key=lambda a:int(a.get('ID')))
        if any(a.get('TypeId')!='1' or len(a.findall('AP'))!=2 for a in objects):continue
        edges=[points(a,canvas) for a in objects]
        if any(not np.allclose(a[1],b[0],atol=1e-3) for a,b in zip(edges,edges[1:])):continue
        rgb=int(objects[0].get('Color'))&0xffffff
        if rgb not in [0,255]:continue
        path=np.vstack([edges[0][0]]+[e[1] for e in edges]);key=str(int(objects[0].get('ID'))//10000)
        out.append(dict(key=key,slot=0 if rgb==0 else 1,objects=objects,path=path))
    return out


def limb(frame,slot,code,canvas):
    objs={int(a.get('ID')):a for a in frame.findall('AO')};ao=objs.get(BASE+slot*100+code);torso=objs.get(BASE+slot*100+2)
    if ao is None or torso is None or not ((int(ao.get('Color'))>>24)&255):return None
    p=points(ao,canvas);t=points(torso,canvas);length=np.linalg.norm(t[1]-t[0])
    if length<3:return None
    hub,tip=PARTS[code]
    return dict(hub=p[hub],tip=p[tip],root=t[0],scale=float(length),rel_tip=(p[tip]-t[0])/length,rel_vec=(p[tip]-p[hub])/length)


def motion_features(frames,n,slot,code,canvas):
    current=limb(frames[n],slot,code,canvas)
    if current is None:return None
    samples=[]
    for i in range(max(0,n-2),min(len(frames),n+3)):
        x=limb(frames[i],slot,code,canvas)
        if x is None:continue
        # 급격한 스케일/위치 변화는 컷 또는 불확실 구간이다. 실제 카메라 추정은 아니다.
        if not .6<=x['scale']/current['scale']<=1.65:continue
        if np.linalg.norm(x['root']-current['root'])>current['scale']*2.5:continue
        samples.append((i,x))
    if len(samples)<3:return None
    ids=np.array([i for i,x in samples]);tips=np.array([x['rel_tip'] for i,x in samples]);vectors=np.array([x['rel_vec'] for i,x in samples]);lengths=np.linalg.norm(vectors,axis=1)
    if (lengths<.03).any():return None
    dt=np.diff(ids);vel=np.diff(tips,axis=0)/dt[:,None];speed=float(np.max(np.linalg.norm(vel,axis=1)))
    angles=np.unwrap(np.arctan2(vectors[:,1],vectors[:,0]));da=np.diff(angles);turn=float(angles[-1]-angles[0]);coherence=float(abs(da.sum())/(abs(da).sum()+1e-9))
    chord=tips[-1]-tips[0];chord_length=np.linalg.norm(chord);path=float(np.linalg.norm(np.diff(tips,axis=0),axis=1).sum())
    if chord_length>1e-5:
        deviation=float(np.max(abs((tips-tips[0])@np.array([-chord[1],chord[0]])/chord_length)))
    else:deviation=0.
    curvature=deviation/max(path,.05);length_change=float(np.ptp(lengths)/max(np.median(lengths),.05))
    acceleration=float(np.max(np.linalg.norm(np.diff(vel,axis=0),axis=1))) if len(vel)>1 else 0.
    return dict(speed=speed,turn_radians=turn,turn_coherence=coherence,curvature=curvature,length_change=length_change,acceleration=acceleration,samples=len(samples))


def choose_family(features,detached=False):
    if features is None:return 'keep'
    f=features
    if abs(f['turn_radians'])>=.32 and f['curvature']>=.10 and f['turn_coherence']>=.65 and f['speed']>=.035:return 'arc_fan'
    if f['length_change']>=.28 and f['speed']>=.055:return 'compact_burst'
    if detached and f['speed']>=.07:return 'split_trail'
    if f['speed']>=.10 and abs(f['turn_radians'])<.22:return 'broad_band'
    return 'straight_taper'


def point_segment_distance(p,a,b):
    v=b-a;u=np.clip((p-a)@v/(v@v+1e-9),0,1)
    return np.linalg.norm(p-(a+u[:,None]*v),axis=1)


def analyze(root,canvas=(1152,648)):
    frames=root.findall('Frame');tracks={}
    for n,frame in enumerate(frames):
        for group in group_effects(frame,canvas):
            options=[]
            for code in PARTS:
                x=limb(frame,group['slot'],code,canvas)
                if x is None:continue
                distance=point_segment_distance(group['path'],x['hub'],x['tip'])/x['scale']
                score=float(np.quantile(distance,.25)+.2*np.linalg.norm(group['path'].mean(0)-x['tip'])/x['scale'])
                options.append((score,code,x))
            if not options:group.update(index=n,body_code=None,match_score=None,features=None,detached=False)
            else:
                score,code,x=min(options,key=lambda v:v[0]);features=motion_features(frames,n,group['slot'],code,canvas) if score<1.2 else None
                detached=float(point_segment_distance(group['path'],x['hub'],x['tip']).min()/x['scale'])>.16
                group.update(index=n,body_code=code,match_score=score,features=features,detached=detached)
            tracks.setdefault(group['key'],[]).append(group)
    for key,rows in tracks.items():
        # 한 효과에서 부위를 고정해, 장마다 다른 손으로 넘어가는 것을 막는다.
        codes=[g['body_code'] for g in rows if g['features'] is not None]
        if not codes:
            for g in rows:g['family']='keep'
            continue
        code=max(set(codes),key=codes.count)
        fs=[]
        for g in rows:
            g['body_code']=code;g['features']=motion_features(frames,g['index'],g['slot'],code,canvas) if g['match_score'] is not None and g['match_score']<1.2 else None
            if g['features'] is not None:fs.append(g['features'])
        if not fs:family='keep';summary=None
        else:
            summary={k:float(np.median([f[k] for f in fs])) for k in fs[0]};family=choose_family(summary,any(g['detached'] for g in rows))
        for g in rows:g['family']=family if g['features'] is not None else 'keep';g['track_features']=summary
    return tracks


def deform(path,family,features):
    """현재 사슬의 불균등 길이·안쪽 꺾임 비율을 재사용하며 형태 외곽을 바꾼다."""
    path=np.asarray(path,float)
    pairs=path[:len(path)//2*2].reshape(-1,2,2);centers=pairs.mean(1);a,b=centers[0],centers[-1];axis=b-a;length=np.linalg.norm(axis)
    if family=='keep' or length<2:return path.copy(),[None]*(len(path)-1),[]
    unit=axis/length;normal=np.array([-unit[1],unit[0]]);u=(path-a)@unit/length
    bend=0.
    if family=='arc_fan':bend=np.sign(features['turn_radians'])*length*min(.20,max(.08,abs(features['turn_radians'])*.08))
    def transform(p):
        t=(p-a)@unit/length;offset=(p-a)@normal
        # 기존 꺾임을 정규화하지 않는다. 점별 깊이 비율을 유지하는 완만한 변형.
        z=np.clip(t,0,1)
        if family=='straight_taper':offset*=.70+.30*z
        elif family=='broad_band':offset*=.85+.15*np.sin(np.pi*z)
        elif family=='compact_burst':offset*=.80+.20*np.sin(np.pi*z)
        along=t
        if family=='compact_burst':along=.5+(t-.5)*.75
        center=a+along[...,None]*length*unit+(2*bend*t*(1-t))[...,None]*normal
        tangent=length*unit+(2*bend*(1-2*t))[...,None]*normal;tangent/=np.maximum(np.linalg.norm(tangent,axis=-1,keepdims=True),1e-9);nrm=np.stack([-tangent[...,1],tangent[...,0]],axis=-1)
        return center+offset[...,None]*nrm
    mapped=transform(path)
    controls=[]
    for i,(p0,p1) in enumerate(zip(path,path[1:])):
        if family!='arc_fan':controls.append(None);continue
        mid=transform((p0+p1)/2);control=2*mid-(mapped[i]+mapped[i+1])/2;deviation=np.linalg.norm(control-(mapped[i]+mapped[i+1])/2)
        controls.append(control if deviation>max(.7,.015*np.linalg.norm(mapped[i+1]-mapped[i])) else None)
    gaps=[]
    if family=='split_trail':
        # 두 군데 짧은 공백. 원래 프레임 수·양끝 위치는 유지한다.
        positions=((u[:-1]+u[1:])/2)
        gaps=np.flatnonzero(((positions>.30)&(positions<.36))|((positions>.65)&(positions<.70))).tolist()
    return mapped,controls,gaps


def build(source,canvas=(1152,648)):
    """기존 효과 시점만 변형한다. 원본 몸/면과 불확실 효과는 그대로 보존한다."""
    tracks=analyze(source,canvas);root=copy.deepcopy(source);root.set('Name',source.get('Name','')+'_motion_types_trial')
    frames=root.findall('Frame');all_ids={int(a.get('ID')) for a in source.findall('.//AO')}
    cursor=max(1950000000,max(int(p.get('ID')) for p in source.findall('.//AP'))+1)
    changed=0;curved=0;records=[]
    for ti,(key,rows) in enumerate(tracks.items()):
        prepared=[];curve_edges=set()
        for g in rows:
            path,controls,gaps=deform(g['path'],g['family'],g.get('track_features'))
            if g['family']!='keep' and not g['detached'] and g['body_code'] is not None:
                body=limb(source.findall('Frame')[g['index']],g['slot'],g['body_code'],canvas)
                if body is not None:
                    anchor=int(np.argmin(point_segment_distance(g['path'],body['hub'],body['tip'])))
                    delta=g['path'][anchor]-path[anchor];path+=delta
                    controls=[None if c is None else c+delta for c in controls]
            prepared.append((g,path,controls,gaps))
            curve_edges.update(i for i,c in enumerate(controls) if c is not None)
        # 한 논리 객체의 종류는 프레임 사이에 바뀌지 않는다.
        for g,path,controls,gaps in prepared:
            if g['family']=='keep':continue
            frame=frames[g['index']];byid={a.get('ID'):a for a in frame.findall('AO')};new=[]
            for old in g['objects']:frame.remove(byid[old.get('ID')])
            previous=None
            for i,old in enumerate(g['objects']):
                if i in gaps:previous=None;continue
                oid=1400000000+ti*10000+i
                if oid in all_ids:raise ValueError('새 스미어 ID 충돌')
                a=copy.deepcopy(old);a.set('ID',str(oid));a.set('TypeId','3' if i in curve_edges else '1')
                for p in list(a):a.remove(p)
                xy=[path[i],path[i+1]]
                if i in curve_edges:
                    c=controls[i] if controls[i] is not None else (path[i]+path[i+1])/2
                    xy=[path[i],c,path[i+1]];curved+=1
                aps=[]
                for j,q in enumerate(xy):
                    p=E.SubElement(a,'AP',ID=str(cursor),Index=str(j),Flags='9',X=f'{q[0]/canvas[0]*100:.9f}',Y=f'{q[1]/canvas[1]*100:.9f}');cursor+=1;aps.append(p)
                if previous is not None:
                    E.SubElement(previous,'AC',ConnPtId=aps[0].get('ID'));E.SubElement(aps[0],'AC',ConnPtId=previous.get('ID'))
                previous=aps[-1];new.append(a)
            frame.extend(new);changed+=1
        records.append(dict(key=key,frames=[g['index']+1 for g in rows],family=rows[0]['family'],body_code=rows[0]['body_code'],features=rows[0].get('track_features'),kept_frames=sum(g['family']=='keep' for g in rows)))
    if cursor>=2000000000:raise ValueError('테두리용 점 ID 예약 영역 침범')
    for old,new in zip(source.findall('Frame'),frames):
        if [E.tostring(x) for x in old if x.tag!='AO' or x.get('LayerId')!='1']!=[E.tostring(x) for x in new if x.tag!='AO' or x.get('LayerId')!='1']:raise ValueError('스미어 외 원본 노드 변경')
    return root,dict(tracks=records,changed_effect_frames=changed,quadratic_objects=curved,body_and_fills_identical=True,video_input=False,app_verified=False,thresholds_learned=False)
