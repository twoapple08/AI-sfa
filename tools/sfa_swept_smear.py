"""v18 기본 리그의 이전/현재 팔다리 사이를 선 사슬로 구성하는 별도 시험. 영상 입력 없음."""
import copy
import json
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np
import sfa_motion_smear as M
import smear_density as D

CANVAS=(1152,648)
PROFILE=Path(__file__).resolve().parents[1]/'profiles/smear_density_v1_1_reference.json'


def history(frames,index,slot,code,canvas=CANVAS):
    """현재 몸통에 이전 부위를 정렬한다. 3D/실제 카메라 복원은 하지 않는다."""
    now=M.limb(frames[index],slot,code,canvas)
    if now is None:return None
    for past in range(index-1,max(-1,index-3),-1):
        old=M.limb(frames[past],slot,code,canvas)
        if old is None:continue
        scale=now['scale']/old['scale']
        if not .6<=scale<=1.65:continue
        if np.linalg.norm(old['root']-now['root'])>now['scale']*2.5:continue
        h=now['root']+(old['hub']-old['root'])*scale
        t=now['root']+(old['tip']-old['root'])*scale
        a=t-h;b=now['tip']-now['hub'];la=np.linalg.norm(a);lb=np.linalg.norm(b)
        if min(la,lb)<3:continue
        angle=float(np.arctan2(a[0]*b[1]-a[1]*b[0],a@b))
        displacement=float(np.linalg.norm(now['tip']-t))
        if displacement<max(2.,now['scale']*.025):continue
        # 한 번에 뒤집히는 추정은 원본으로 남긴다.
        if abs(angle)>2.35 or not .35<=la/lb<=2.8:continue
        return dict(now=now,hub=h,tip=t,angle=angle,old_length=la,length=lb,past=past,displacement=displacement)
    return None


def rotation(v,angle):
    c,s=np.cos(angle),np.sin(angle)
    return np.stack([c*v[...,0]-s*v[...,1],s*v[...,0]+c*v[...,1]],axis=-1)


def sweep_geometry(motion,detached=False,source_center=None,source_span=None):
    """기존 지그재그를 변형하지 않고 부위의 시간 궤도로 경계/보조 호를 구성한다."""
    now=motion['now'];angle=motion['angle'];length=motion['length'];v=now['tip']-now['hub']
    # 시간별 난수 없이 주요 꺾임의 크기를 다르게 둔다.
    ts=np.array([0,.10,.25,.39,.55,.72,.85,1.])
    inner=np.array([.24,.33,.20,.30,.17,.29,.22,.18])
    outer=np.array([.91,1.05,.94,1.08,.90,1.04,.95,1.0])
    accents=[]
    if detached:
        family='detached_ribbon'
        direction=now['tip']-motion['tip'];direction/=max(np.linalg.norm(direction),1e-9)
        normal=np.array([-direction[1],direction[0]])
        extent=max(8.,min(float(source_span),length*.8));width=extent*.36
        center=source_center+(ts[:,None]-.5)*extent*direction
        near=center-normal*(width*(.70+.25*np.sin(np.pi*ts)))[:,None]
        far=center+normal*(width*(.85+.15*np.cos(np.pi*ts)))[:,None]
    elif abs(angle)>=.20:
        family='radial_sweep'
        # 팔꿈치/무릎 안쪽을 기준으로 바깥쪽 궤적을 크게 한다. 회전량은 약85도로 제한한다.
        sweep=np.clip(angle,-1.48,1.48)
        directions=rotation(np.tile(v,(len(ts),1)),-sweep*(1-ts))
        # 공통 이동을 제거한 팔꿈치 자체 이동도 일부 반영한다.
        hubs=now['hub']+(1-ts[:,None])*.45*(motion['hub']-now['hub'])
        near=hubs+inner[:,None]*directions;far=hubs+outer[:,None]*directions
        if abs(sweep)>.45:
            # 큰 회전의 바깥쪽에만 짧은 분절 호를 넣는다. 직선 이동에는 넣지 않는다.
            for lo,hi,radius in [(.08,.43,1.14),(.53,.91,1.14),(.20,.67,1.25)]:
                def point(u):return now['hub']+radius*rotation(v,-sweep*(1-u))
                p0,p1=point(lo),point(hi);mid=point((lo+hi)/2);control=2*mid-(p0+p1)/2
                accents.append(np.array([p0,control,p1]))
    else:
        family='translation_blade'
        # 평행 이동은 이전/현재 부위의 두 경계 사이를 선으로 채운다.
        travel=motion['tip']-now['tip'];cap=length*.85
        if np.linalg.norm(travel)>cap:travel*=cap/np.linalg.norm(travel)
        h=now['hub']+(1-ts[:,None])*travel
        vec=np.tile(v,(len(ts),1))
        near=h+(.38+.12*np.sin(np.pi*ts))[:,None]*vec
        far=h+outer[:,None]*vec
    # 끊어진 원본 효과를 팔다리에 붙여 모으지 않는다.
    base=np.empty((2*len(ts)+1,2));base[:-1:2]=near;base[1::2]=far;base[-1]=near[-1]+(far[-1]-near[-1])*.02
    return family,base,accents


def build(source,profile=None,canvas=CANVAS):
    profile=copy.deepcopy(profile or json.loads(PROFILE.read_text()));D.validate_profile(profile)
    root=copy.deepcopy(source);root.set('Name',source.get('Name','')+'_swept_trial')
    frames=source.findall('Frame');outframes=root.findall('Frame');tracks=M.analyze(source,canvas)
    source_ids={int(a.get('ID')) for a in source.findall('.//AO')};pid=max(1950000000,max(int(p.get('ID')) for p in source.findall('.//AP'))+1)
    report=[];changed=0
    for ti,(key,groups) in enumerate(tracks.items()):
        for group in groups:
            n=group['index'];code=group['body_code'];reason=None;motion=None
            if code is None or group['features'] is None or group['match_score']>=.6:reason='uncertain_assignment'
            else:
                motion=history(frames,n,group['slot'],code,canvas)
                if motion is None:reason='insufficient_history'
            if reason:
                report.append(dict(frame=n+1,key=key,family='keep',reason=reason));continue
            family,base,accents=sweep_geometry(motion,group['detached'],group['path'].mean(0),np.linalg.norm(np.ptp(group['path'],axis=0)))
            density=D.process(base,canvas,profile);path=np.array(density['points_px']);frame=outframes[n];byid={a.get('ID'):a for a in frame.findall('AO')}
            for old in group['objects']:frame.remove(byid[old.get('ID')])
            template=group['objects'][0];line_base=1420000000+ti*20000
            if len(path)>19000:raise ValueError('사슬 객체 수 제한')
            pieces=[('1',np.array([a,b])) for a,b in zip(path,path[1:])]+[('3',a) for a in accents]
            previous=None
            for i,(typ,xy) in enumerate(pieces):
                # 곡선 보조선 ID는 선 개수와 무관하게 고정한다.
                oid=line_base+i if typ=='1' else line_base+19000+i-(len(path)-1)
                if oid in source_ids:raise ValueError('새 객체 ID 충돌')
                ao=copy.deepcopy(template);ao.set('ID',str(oid));ao.set('TypeId',typ);ao.set('DrawOrder',str(i))
                for p in list(ao):ao.remove(p)
                aps=[]
                for j,q in enumerate(xy):
                    p=E.SubElement(ao,'AP',ID=str(pid),Index=str(j),Flags='9',X=f'{q[0]/canvas[0]*100:.9f}',Y=f'{q[1]/canvas[1]*100:.9f}');pid+=1;aps.append(p)
                if typ=='1' and previous is not None:
                    E.SubElement(previous,'AC',ConnPtId=aps[0].get('ID'));E.SubElement(aps[0],'AC',ConnPtId=previous.get('ID'))
                previous=aps[-1] if typ=='1' else None;frame.append(ao)
            changed+=1
            report.append(dict(frame=n+1,key=key,slot=group['slot'],body_code=code,family=family,past_frame=motion['past']+1,angle=motion['angle'],base_vertices=len(base),added_pairs=density['added_pairs'],new_lines=len(path)-1,curved_accents=len(accents),base_vertices_preserved=density['original_vertices_preserved'],density_intervals=density['intervals']))
    if pid>=2000000000:raise ValueError('테두리 예약 점 ID 영역 침범')
    for a,b in zip(frames,outframes):
        if [E.tostring(x) for x in a if x.tag!='AO' or x.get('LayerId')!='1']!=[E.tostring(x) for x in b if x.tag!='AO' or x.get('LayerId')!='1']:raise ValueError('원본 몸/부속/면 변경')
    return root,dict(effects=report,changed_effects=changed,profile='smear_density_v1_1_reference',video_input=False,app_verified=False,body_identical=True)
