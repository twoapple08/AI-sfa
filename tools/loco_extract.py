"""nian41·나카무라 영상의 실제 이동 장면 변환(11-06): data/stage2/loco_candidates_judged의 '이동' 8개를 stage2_extract.convert로 motion-ir로.
사용: python tools/loco_extract.py <stage2 작업 폴더(video/·rtmw/·cuts/)> <출력 폴더>  — 결과 좌표는 비공개(저장소에 넣지 않음). compose --loco-dir <출력 폴더>."""
import sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage2_extract as X
work = sys.argv[1]; outd = sys.argv[2]
rows = [r for r in json.load(open(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/data/stage2/loco_candidates_judged_2026-11-06.json', encoding='utf-8'))['rows'] if r['judge'].startswith('이동')]
vids = dict(X.VIDEOS); vids.update(X.videos_of(work, 'yutaka_nakamura'))
res = []
for r in rows:
    vid = r['video']; W, H = vids[vid]
    R = X.load_rtmw(f'{work}/rtmw/{vid}.jsonl.gz'); cl, n = X.cached_cuts(work, vid, f'{work}/video/{vid}.mp4')
    c = next((c for c in X.candidates(vid, R, cl, H, W) if c['start'] == r['start']), None)
    if c is None: print(vid, r['start'], '후보 못 찾음'); continue
    c['animator'] = r['animator']
    ir, q = X.convert(c, W, H, f'{work}/video/{vid}.mp4')
    name = f"loco{r['idx']:02d}_{vid}_{r['start']}"
    if not ir['actors']: print(name, '변환 실패'); continue
    json.dump(ir, open(f'{outd}/{name}.json', 'w'))
    res.append(dict(name=name, note=r['note'], frames=ir['frames'], actors=len(ir['actors'])))
    print(res[-1], flush=True)
json.dump(res, open(f'{outd}/summary.json', 'w'), ensure_ascii=False, indent=1)
