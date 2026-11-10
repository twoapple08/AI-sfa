"""SFA 확인 영상(원본 겹침 / SFA만). 레이어는 앱처럼 번호 오름차순으로 그린다(docs/FORMAT.md 레이어 번호).

원본 영상과 결과 영상은 비공개다. 서버 렌더러(sfa_render) 기준 미리보기이며 앱 표시 확인이 아니다.
예: python tools/sfa_overlay_video.py --sfa 결과.sfa --video 원본.mp4 --first-frame 1032 --crop-y 63 \
      --audio-start 43 --overlay 겹침.mp4 --solo SFA만.mp4
"""
import argparse,copy,json,subprocess,zipfile
import xml.etree.ElementTree as E
import numpy as np
import sfa_render as R


_FIRST={}


def first_seen(root):
    """객체 ID → 파일 전체에서 처음 나온 순번. 앱은 DrawOrder를 읽지 않고 이 순서로 그린다(docs/FORMAT.md, AOT 추적)."""
    key=id(root)
    if key not in _FIRST:
        order={}
        for f in root.findall('Frame'):
            for a in f.findall('AO'):order.setdefault(a.get('ID'),len(order))
        _FIRST[key]=order
    return _FIRST[key]


def app_order(frame,root=None):
    """앱 그리기 순서의 장 복사본: LayerDef 번호순, 같은 레이어 안은 파일 전체 첫 등장 순서(DrawOrder 무시)."""
    f=copy.deepcopy(frame);ls=sorted(f.findall('LayerDef'),key=lambda l:int(l.get('ID')))
    for l in f.findall('LayerDef'):f.remove(l)
    for i,l in enumerate(ls):f.insert(i,l)
    if root is not None:
        order=first_seen(root)
        for a in f.findall('AO'):a.set('DrawOrder',str(order.get(a.get('ID'),10**9)))
    return f


def render_alpha(root,frame,w,h):
    """흰/검 배경 두 번 그려 알파와 색을 얻는다(안티앨리어싱·흰 머리 채움 보존)."""
    f=app_order(frame,root)
    f.set('BackgroundColor','-1');white=R.render_frame(root,f,w,h).astype(np.float32)
    f.set('BackgroundColor','-16777216');black=R.render_frame(root,f,w,h).astype(np.float32)
    alpha=np.clip(1-np.mean(white-black,axis=2)/255,0,1)
    return black,alpha


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sfa',required=True);ap.add_argument('--video');ap.add_argument('--first-frame',type=int,default=0)
    ap.add_argument('--crop-y',type=int,default=0,help='원본에서 SFA 캔버스가 시작하는 y(px)')
    ap.add_argument('--canvas',default='1152x648');ap.add_argument('--fps',type=int,default=24)
    ap.add_argument('--audio-start',type=float,help='원본 소리 시작 초(없으면 소리 없음)')
    ap.add_argument('--overlay');ap.add_argument('--solo')
    a=ap.parse_args();W,H=map(int,a.canvas.split('x'))
    with zipfile.ZipFile(a.sfa) as z:root=E.fromstring(z.read(z.namelist()[0]))
    frames=root.findall('Frame');R.PARAMS.update(pad=0,thick_mul=W/1920)
    def encoder(path,w,h):
        cmd=['ffmpeg','-nostdin','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{w}x{h}','-r',str(a.fps),'-i','-']
        if a.audio_start is not None and a.video:cmd+=['-ss',str(a.audio_start),'-t',str(len(frames)/a.fps),'-i',a.video,'-map','0:v','-map','1:a?','-c:a','aac']
        cmd+=['-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-t',str(len(frames)/a.fps),'-movflags','+faststart',path]
        return subprocess.Popen(cmd,stdin=subprocess.PIPE)
    solo=encoder(a.solo,W,H) if a.solo else None
    over=dec=None
    if a.overlay:
        if not a.video:raise SystemExit('--overlay에는 --video가 필요')
        probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',a.video]))['streams'][0]
        VW,VH=probe['width'],probe['height']
        if VW!=W or a.crop_y+H>VH:raise SystemExit('원본 크기와 캔버스/crop-y가 맞지 않음')
        dec=subprocess.Popen(['ffmpeg','-nostdin','-v','error','-i',a.video,'-vf',f'select=between(n\\,{a.first_frame}\\,{a.first_frame+len(frames)-1})','-vsync','0','-f','rawvideo','-pix_fmt','rgb24','-'],stdout=subprocess.PIPE)
        over=encoder(a.overlay,VW,VH)
    try:
        for f in frames:
            black,alpha=render_alpha(root,f,W,H)
            if solo:
                white=black+255*(1-alpha[:,:,None]);solo.stdin.write(np.clip(white,0,255).round().astype(np.uint8).tobytes())
            if over:
                data=dec.stdout.read(VW*VH*3)
                if len(data)!=VW*VH*3:raise ValueError('원본 장수 부족')
                img=np.frombuffer(data,np.uint8).reshape(VH,VW,3).copy();crop=img[a.crop_y:a.crop_y+H].astype(np.float32)
                img[a.crop_y:a.crop_y+H]=np.clip(black+crop*(1-alpha[:,:,None]),0,255).round().astype(np.uint8)
                over.stdin.write(img.tobytes())
        for p in (solo,over):
            if p:p.stdin.close();assert p.wait()==0
        if dec:dec.kill()
    except BaseException:
        for p in (solo,over,dec):
            if p:p.kill()
        raise
    for path in (a.solo,a.overlay):
        if path:
            n=subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames','-of','csv=p=0',path]).decode().strip()
            if int(n)!=len(frames):raise SystemExit(f'{path}: 장 수 {n} != {len(frames)}')
            print(path,'장',n)


if __name__=='__main__':
    main()
