"""확인된 스미어 라벨 → 완성 스틱맨 SFA의 팔다리에 붙인 스미어 사슬(스미어 단계 2, v18 규칙).

입력:
- 스틱맨 SFA(스미어 층 없음; 몸 ID BASE+slot*100+1..11, 부위 3/4·5/6 팔, 7/8·9/10 다리)
- 비공개 라벨 `smear-eval-labels/1`(장·원본 인물색·부위·확인 상자·사용자 메모)
- 원본 프레임 폴더(<장>.png, 스틱맨 좌표와 같은 1152×648 캔버스)
- 사슬 모양 틀(비공개 templates.private.json의 첫 항목)
- 장면 설정 `scenes/*_smear.json`: 원본 인물색 → slot/스미어 색, 추가 라벨(extra)

규칙(사용자 11-07~11-08 확정, v18):
- 방향은 스틱맨 아래팔/정강이, 길이·양쪽 폭은 원본 톱니 화소로 측정. 폭은 일그러진 정도이므로 원본 팔다리 반두께를 뺀다.
- 팔다리 끝은 스미어 끝 밖으로 나오지 않는다. 팔다리를 줄이지 않고 스미어를 민다. '전체'(다리 전체) 모드도 같다.
- 굵기는 부위 ThicknessScale p10(0.945)→기본 .14의 250%, p90(4.99)→1000%, 밀도 간격 연동. 폭<28px·길이<40px만 소형 12선.
- 끝 정리: 끝 20% 점을 앞 8점 외곽(폭 1.15배·진행 +4%) 안으로, 앞 6선 중앙값의 1.1배 넘는 끝 선 제거(최대 12회).
결과는 휘두르기 사슬 초안이며 형태 단계(sfa_axial_smear: GPT 표시 테이퍼·직진 갈래)가 다시 그린다.
"""
import argparse,copy,json,zipfile
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np

CANVAS=(1152,648)
BASE=4560000
LIMBS={'armA':(3,4,'arm'),'armB':(5,6,'arm'),'legA':(7,8,'leg'),'legB':(9,10,'leg')}
TH_LO,TH_HI=.945,4.99


def P(a,canvas=CANVAS):
    return [np.array([float(p.get('X'))*canvas[0]/100,float(p.get('Y'))*canvas[1]/100]) for p in a.findall('AP')]


def chain(objs,off,o1,o2):
    """위 마디·아래 마디를 이어 (뿌리, 가운데 관절, 끝)."""
    a,b=P(objs[off+o1]),P(objs[off+o2])
    for i in (0,1):
        for j in (0,1):
            if np.linalg.norm(a[i]-b[j])<.6:return a[1-i],a[i],b[1-j]


def segdist(q,a,b):
    u=b-a;t=np.clip(((q-a)@u)/max(u@u,1e-9),0,1);return np.linalg.norm(q-(a+t[:,None]*u),axis=1)


def teeth_pixels(rgb,mask,tor):
    import cv2
    m=mask.astype(bool);k=max(3,int(round(.03*tor))|1)
    op=cv2.morphologyEx(m.astype(np.uint8),cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(k,k))).astype(bool)
    gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY);near=cv2.dilate(m.astype(np.uint8),np.ones((5,5),np.uint8)).astype(bool)
    dark=(gray<80)&near;dk=dark&~cv2.morphologyEx(dark.astype(np.uint8),cv2.MORPH_OPEN,np.ones((5,5),np.uint8)).astype(bool)
    return m,op,dk


def measure_pixels(rgb,mask,root,mid,end,tor,thick_px):
    """라벨 상자 없는 추가 항목에서 어느 팔다리인지 고르는 데 쓰는 톱니 화소 수."""
    H,W=mask.shape;R=int(max(40,.9*tor));yy,xx=np.mgrid[0:H,0:W];win=((xx-end[0])**2+(yy-end[1])**2<=R*R)
    m,op,dk=teeth_pixels(rgb,mask&win,tor);ys,xs=np.nonzero((m&~op)|dk);Q=np.stack([xs,ys],1).astype(float)
    if len(Q)<15:return 0
    d=np.minimum(segdist(Q,mid,end),segdist(Q,root,mid));return int((d>thick_px*1.2).sum())


def measure_axis(rgb,mask,root,mid,end,tor,head,others=()):
    """스틱맨 아래팔/정강이 방향 고정. 원본 톱니 화소로 길이와 축 양쪽 폭(원본 반두께 제외)을 잰다."""
    import cv2
    H,W=mask.shape;u=end-mid;lb=max(10.,np.linalg.norm(u));u=u/lb;nv=np.array([-u[1],u[0]])
    m,op,dk=teeth_pixels(rgb,mask,tor)
    ys,xs=np.nonzero((m&~op)|dk);Q=np.stack([xs,ys],1).astype(float)
    t=(Q-end)@u;o=(Q-end)@nv
    sel=(t>-.3*lb)&(t<1.6*lb)&(np.abs(o)<.5*tor)
    for a_,b_ in others:sel&=segdist(Q,a_,b_)>.12*tor
    if head is not None:sel&=np.linalg.norm(Q-head[0],axis=1)>head[1]*1.15
    t,o=t[sel],o[sel]
    if len(t)<25:return None
    tf=float(np.percentile(t,97));ln=float(np.clip(tf+.35*lb,.6*lb,2.2*lb))
    dt=cv2.distanceTransform(m.astype(np.uint8),cv2.DIST_L2,5);hs=[]
    for s_ in np.linspace(.3,.9,7):
        x,y=(mid+(end-mid)*s_).astype(int)
        if 0<=x<W and 0<=y<H:hs.append(dt[y,x])
    half=float(np.median(hs)) if hs else 0.
    pos=o[o>0];neg=-o[o<0]
    wl=float(np.percentile(pos,85)) if len(pos)>=6 else 0.;wr=float(np.percentile(neg,85)) if len(neg)>=6 else 0.
    return dict(ln=ln,wl=max(0.,wl-half),wr=max(0.,wr-half),half=half,n=int(len(t)),u=u,nv=nv,lb=lb)


def clamp_tail(pts,axis,frac=.2,k=8,grow=1.15):
    """끝 정리(v6 사용자 지적 '끝부분 혼자 벌어짐')."""
    p=np.array(pts,float);a0=np.array(axis[0],float);u=np.subtract(axis[1],axis[0]);u=u/np.linalg.norm(u);nv=np.array([-u[1],u[0]])
    t=(p-a0)@u;o=(p-a0)@nv;n=len(p);start=max(k,int(n*(1-frac)));changed=0
    for i in range(start,n):
        tmax=t[:i].max()+.04*(t.max()-t.min());side=o[i-k:i][np.sign(o[i-k:i])==np.sign(o[i])] if o[i]!=0 else np.array([0.])
        omax=grow*np.abs(side).max() if len(side) else abs(o[i])
        nt=min(t[i],tmax);no=np.sign(o[i])*min(abs(o[i]),omax)
        if nt!=t[i] or no!=o[i]:t[i],o[i]=nt,no;changed+=1
    q=a0+t[:,None]*u+o[:,None]*nv
    for _ in range(12):
        L=np.linalg.norm(np.diff(q,axis=0),axis=1)
        if len(L)>10 and L[-1]>1.1*np.median(L[-8:-2]):q=q[:-1];changed+=1
        else:break
    return q,changed


def items_from_labels(labels,extra=()):
    out=[dict(frame=l['frame'],actor=l['actor'],part=l['part'],box=l['box'],src=str(l.get('review_no','')),whole='전체' in str(l.get('user',''))) for l in labels if l.get('conf','S') in ('S','L')]
    return out+[dict(frame=int(f),actor=a,part=p,box=None,src='extra',whole=False) for f,a,p in extra]


def apply_pose_fixes(stick,fixes,frame_base,canvas=CANVAS,tol=1.5):
    """사용자 요청 수동 자세 교정(장면 설정 pose_fixes). 지정 객체의 from 좌표 점(과 같은 좌표로 이어진 점)을 to로 옮긴다.
    자동 교정이 아니다. 맞는 점이 없으면 멈춘다."""
    out=copy.deepcopy(stick);log=[]
    for fx in fixes or []:
        f=out.findall('Frame')[fx['frame']-frame_base];hit=0
        for a in f.findall('AO'):
            if a.get('ID')!=str(fx['object']):continue
            for p in a.findall('AP'):
                xy=np.array([float(p.get('X'))*canvas[0]/100,float(p.get('Y'))*canvas[1]/100])
                if np.linalg.norm(xy-np.array(fx['from'],float))<tol:
                    p.set('X',repr(fx['to'][0]/canvas[0]*100));p.set('Y',repr(fx['to'][1]/canvas[1]*100));hit+=1
        if hit!=1:raise ValueError(f"자세 교정 대상 점을 하나로 못 찾음: {fx}")
        log.append(dict(frame=fx['frame'],object=fx['object'],to=fx['to']))
    return out,log


def build(stick,items,frames_dir,template,scene,density_profile,frame_base,canvas=CANVAS):
    """stick: 스미어 없는 스틱맨 SFA 루트(그대로 두고 복사본에 스미어 층 추가). 장면 pose_fixes를 먼저 적용한다."""
    stick,_=apply_pose_fixes(stick,scene.get('pose_fixes'),frame_base,canvas)
    import cv2
    import smear_limb_scan as V
    from smear_rail_fit import deform_chain
    from smear_density import process,export_sfa
    actors=scene['actors']  # {원본색: {slot, smear_color}}
    result=copy.deepcopy(stick);sfr=stick.findall('Frame');out=result.findall('Frame');last=frame_base+len(sfr)-1
    dense=dict(density_profile,thickness=.28);sparse=dict(dense,max_gap=60.,relative_gap=1.,min_gap=50.)
    rep=[];cache={}
    def limbs(n,actor,part):
        off=actors[actor]['slot']*100;objs={int(a.get('ID'))-BASE:a for a in sfr[n-frame_base].findall('AO') if BASE<int(a.get('ID'))<BASE+200}
        res=[]
        for name,(o1,o2,pt) in LIMBS.items():
            if pt!=part or off+o1 not in objs or off+o2 not in objs:continue
            c=chain(objs,off,o1,o2)
            if c:res.append((name,c,objs[off+o2],objs[off+2]))
        return res
    for ei,it in enumerate(items):
        n=it['frame'];L=limbs(n,it['actor'],it['part'])
        if n not in cache:cache[n]=cv2.cvtColor(cv2.imread(str(Path(frames_dir)/f'{n}.png')),cv2.COLOR_BGR2RGB)
        rgb=cache[n];mask=V.color_masks(rgb)[it['actor']]
        if L:
            if it['box'] is not None:
                bc=np.array([(it['box'][0]+it['box'][2])/2,(it['box'][1]+it['box'][3])/2]);name,(r_,m_,e_),bone,trunk=min(L,key=lambda t:np.linalg.norm(t[1][2]-bc))
            else:
                sc=[]
                for t in L:
                    neck,pel=P(t[3]);tor=max(20,np.linalg.norm(neck-pel));th=float(t[3].get('ThicknessScale'))
                    sc.append((measure_pixels(rgb,mask,*t[1],tor,max(8*th*canvas[0]/1920/2,.08*tor)),t))
                name,(r_,m_,e_),bone,trunk=max(sc,key=lambda s:s[0])[1]
            neck,pel=P(trunk);tor=max(20,np.linalg.norm(neck-pel));th=float(bone.get('ThicknessScale'))
        else:
            r_=m_=e_=None;tor=120.;bone=None
            for d in range(1,30):
                for mm_ in (n-d,n+d):
                    if bone is None and frame_base<=mm_<=last:
                        LL=limbs(mm_,it['actor'],it['part'])
                        if LL:bone=LL[0][2]
            th=float(bone.get('ThicknessScale'))
        bw=8*th*canvas[0]/1920
        head=None;oth=[]
        if e_ is not None:
            off=actors[it['actor']]['slot']*100
            hd=[a for a in sfr[n-frame_base].findall('AO') if a.get('ID')==str(BASE+1+off)]
            if hd:hp=P(hd[0]);head=((hp[0]+hp[1])/2,np.linalg.norm(hp[0]-hp[1])/2)
            for a in sfr[n-frame_base].findall('AO'):
                i_=int(a.get('ID'))-BASE-off
                if 2<=i_<=11 and a.get('TypeId')=='1':
                    pp=P(a)
                    if not any(np.linalg.norm(pp[0]-q)<.6 and np.linalg.norm(pp[1]-w)<.6 or np.linalg.norm(pp[1]-q)<.6 and np.linalg.norm(pp[0]-w)<.6 for q,w in ((m_,e_),(r_,m_))):oth.append((pp[0],pp[1]))
        mm=measure_axis(rgb,mask,r_,m_,e_,tor,head,oth) if e_ is not None else None
        if it['whole'] and e_ is not None:
            axis=np.array([r_+.1*(e_-r_),e_+.05*(e_-r_)]);w=3.*bw;prof=[[w*k,w*k] for k in (.4,.7,.9,1.)];mode='whole'
        elif mm is not None:
            ln=mm['ln'];axis=np.array([e_-.35*ln*mm['u'],e_+.65*ln*mm['u']])
            wl=float(np.clip(mm['wl'],.5*bw,.45*ln));wr=float(np.clip(mm['wr'],.5*bw,.45*ln))
            prof=[[wl*k,wr*k] for k in (.08,.45,.8,1.)];mode='measured'
        else:
            b=it['box']
            if e_ is not None:
                u_=(e_-m_)/np.linalg.norm(e_-m_);ln=.7*(max(b[2]-b[0],b[3]-b[1]) if b else np.linalg.norm(e_-m_));axis=np.array([e_-.35*ln*u_,e_+.65*ln*u_])
            else:
                ys,xs=np.nonzero(mask[int(b[1]):int(b[3]),int(b[0]):int(b[2])]);Q=np.stack([xs+b[0],ys+b[1]],1).astype(float);c=Q.mean(0);u_=np.linalg.svd(Q-c,full_matrices=False)[2][0]
                if (c-np.array([canvas[0]/2,canvas[1]/2]))@u_>0:u_=-u_
                ln=.7*max(b[2]-b[0],b[3]-b[1]);axis=np.array([c-ln/2*u_,c+ln/2*u_])
            w=.3*(min(b[2]-b[0],b[3]-b[1]) if b else 2*bw);prof=[[w*k,w*k] for k in (.08,.45,.8,1.)];mode='fallback'
        if e_ is not None and mode=='whole':
            ul=(e_-r_)/max(1e-6,np.linalg.norm(e_-r_));axis=np.array([r_+.1*(e_-r_),e_+max(15.,.06*np.linalg.norm(e_-r_))*ul])
        if e_ is not None and mode!='whole':
            ul=(e_-m_)/max(1e-6,np.linalg.norm(e_-m_));L0=np.linalg.norm(axis[1]-axis[0])
            ahead=max(10.,.15*L0);end_=e_+ahead*ul;start_=end_-L0*ul
            lb_=np.linalg.norm(e_-m_)
            if (start_-m_)@ul<0:start_=m_+.05*lb_*ul
            axis=np.array([start_,end_])
        u=(axis[1]-axis[0]);L_=np.linalg.norm(u)
        if L_<8:
            rep.append(dict(frame=n,actor=it['actor'],part=it['part'],src=it['src'],mode='skipped_short'));continue
        u/=L_;nv=np.array([-u[1],u[0]]);prof=np.array(prof,float)
        if it['box'] is not None and mode!='whole':
            bx=it['box'];major=max(bx[2]-bx[0],bx[3]-bx[1]);L0=np.linalg.norm(axis[1]-axis[0])
            if L0>1.15*major:axis=np.array([axis[1]-(axis[1]-axis[0])*1.15*major/L0,axis[1]])
        prof*=float(np.clip(L_/(12*bw),1.,1.6));prof=np.maximum(prof,1.5)
        ov=next((o for o in scene.get('smear_size',[]) if o['frame']==n and o['actor']==it['actor'] and o['part']==it['part']),None)
        if ov:  # 사용자 지정 크기(형식은 그대로): 끝(손끝 앞)은 두고 길이·끝 폭만 맞춘다
            axis=np.array([axis[1]-ov['length_px']*u,axis[1]]);L_=float(ov['length_px'])
            prof=prof*np.array([ov['wl_px']/max(prof[-1][0],1e-6),ov['wr_px']/max(prof[-1][1],1e-6)])
            mode=mode+'+size'
        ts=np.linspace(0,1,4);cen=axis[0]+ts[:,None]*(axis[1]-axis[0])
        pts=deform_chain(template,cen+prof[:,0:1]*nv,cen-prof[:,1:2]*nv,12)
        small=prof[-1].sum()<28 and L_<40
        pct=2.5+7.5*float(np.clip((th-TH_LO)/(TH_HI-TH_LO),0,1));t_=round(.14*pct,4)
        prof_=dict(sparse,thickness=t_) if small else dict(dense,thickness=t_,**{k:dense[k]*min(t_,.70)/.28 for k in ('max_gap','min_gap','relative_gap')})
        r=process(pts,list(canvas),prof_)
        if r['segments']>12 or mode=='whole':r['points_px'],_=clamp_tail(r['points_px'],axis)
        Q_=np.asarray(r['points_px'])
        if e_ is not None:
            base_=r_ if mode=='whole' else m_;ul=(e_-base_)/np.linalg.norm(e_-base_)
            need=float(e_@ul+max(10.,.03*np.linalg.norm(e_-base_) if mode=='whole' else .15*L_)-(Q_@ul).max())
            if need>0:Q_=Q_+need*ul  # 팔다리 끝이 스미어 끝 밖으로 나오지 않게 스미어를 민다
        r['points_px']=Q_.tolist();r['segments']=len(r['points_px'])-1
        sub=export_sfa(r,list(canvas),prof_,point_base=1700000000+(n-frame_base)*1000000+ei*3000,object_base=1300000000+ei*10000).find('Frame')
        f=out[n-frame_base]
        if not any(x.get('ID')=='1' for x in f.findall('LayerDef')):E.SubElement(f,'LayerDef',ID='1',Name='smear',Visible='true',Locked='false')
        for a in sub.findall('AO'):a.set('LayerId','1');a.set('Color',str(actors[it['actor']]['smear_color']));f.append(a)
        rep.append(dict(frame=n,actor=it['actor'],part=it['part'],src=it['src'],mode=mode,segments=r['segments'],pct=pct,len=round(L_),wl=round(float(prof[-1][0])),wr=round(float(prof[-1][1]))))
    return result,rep


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--stickman',required=True);ap.add_argument('--labels',required=True);ap.add_argument('--frames',required=True)
    ap.add_argument('--template',required=True);ap.add_argument('--scene',required=True);ap.add_argument('--out',required=True);ap.add_argument('--report')
    ap.add_argument('--density',default=str(Path(__file__).resolve().parents[1]/'profiles/smear_density_v1_1_reference.json'))
    a=ap.parse_args()
    with zipfile.ZipFile(a.stickman) as z:stick=E.fromstring(z.read(z.namelist()[0]))
    scene=json.loads(Path(a.scene).read_text())
    items=items_from_labels(json.loads(Path(a.labels).read_text())['labels'],scene.get('extra',[]))
    result,rep=build(stick,items,a.frames,json.loads(Path(a.template).read_text())[0],scene,json.loads(Path(a.density).read_text()),int(scene.get('frame_base',1)))
    with zipfile.ZipFile(a.out,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('review.xml',E.tostring(result,encoding='utf-8',xml_declaration=True))
    if a.report:Path(a.report).write_text(json.dumps(rep,ensure_ascii=False,indent=1))
    print(json.dumps(dict(smears=len([r for r in rep if r['mode']!='skipped_short'])),ensure_ascii=False))


if __name__=='__main__':
    main()
