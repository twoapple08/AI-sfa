"""레이어 번호를 아래→위 그리기 순서와 같게 맞춘다.

앱은 레이어 목록을 Layer 번호(ID)의 정수 비교로 정렬한다(AOT 0x5bd468 comparator, docs/AOT-LAYER-MEMORY-TRACE-2026-10-15.md).
불러올 때 AO의 DrawOrder는 읽지 않는다(docs/FORMAT.md). 그래서 '뒤에 깔 층'을 LayerDef 맨 앞에 적고
DrawOrder를 음수로 줘도 번호가 크면 앱에서는 위에 그려진다(2026-11-08 사용자 앱 화면: 테두리 층 ID 2가
몸·흰 머리를 덮어 색이 빠지고 몸통이 머리 위로 보임). 서버 렌더러는 LayerDef를 적은 순서대로 그려 차이를 못 봤다.
이 함수는 가장 긴 장의 LayerDef 순서(아래→위)를 기준으로 0,1,2…로 번호를 다시 매긴다. 그러면 적은 순서와
번호 순서가 같아진다. 모든 장의 LayerDef 순서가 같아야 한다(레이어 순서는 모든 장이 공유).
"""


def renumber_bottom_to_top(root):
    frames=root.findall('Frame')
    # 장마다 쓰는 레이어만 적혀 있을 수 있다(스미어 없는 장). 가장 긴 순서를 기준으로, 다른 장은 그 부분열이어야 한다.
    order=max(([l.get('ID') for l in f.findall('LayerDef')] for f in frames),key=len)
    for f in frames:
        ids=[l.get('ID') for l in f.findall('LayerDef')];pos=[order.index(x) if x in order else -1 for x in ids]
        if -1 in pos or pos!=sorted(pos):raise ValueError('장마다 레이어 순서가 다름')
    mapping={old:str(i) for i,old in enumerate(order)}
    # 같은 번호의 이름을 하나로(가장 많이 쓰인 이름). v18은 스미어 층이 장에 따라 smear/smear_review로 달랐다.
    import collections
    names={k:collections.Counter(l.get('Name') for f in frames for l in f.findall('LayerDef') if l.get('ID')==k).most_common(1)[0][0] for k in order}
    for f in frames:
        for l in f.findall('LayerDef'):l.set('Name',names[l.get('ID')]);l.set('ID',mapping[l.get('ID')])
        for a in f.findall('AO'):
            lid=a.get('LayerId','0')
            if lid not in mapping:raise ValueError(f'정의 없는 레이어 {lid}')
            a.set('LayerId',mapping[lid])
    return mapping


def check(root):
    """앱 기준(번호 오름차순=아래→위)과 적은 순서가 같은지, ID마다 (층, 종류)가 하나인지."""
    ok_order=all([int(l.get('ID')) for l in f.findall('LayerDef')]==sorted(int(l.get('ID')) for l in f.findall('LayerDef')) for f in root.findall('Frame'))
    seen={}
    for f in root.findall('Frame'):
        for a in f.findall('AO'):seen.setdefault(a.get('ID'),set()).add((a.get('LayerId'),a.get('TypeId')))
    names={}
    for f in root.findall('Frame'):
        for l in f.findall('LayerDef'):names.setdefault(l.get('ID'),set()).add(l.get('Name'))
    return dict(order_matches_ids=ok_order,layer_ids_with_multiple_names=sum(len(v)>1 for v in names.values()),ids_with_multiple_layer_or_type=sum(len(v)>1 for v in seen.values()))
