#!/usr/bin/env python3
"""승낙 작가 편입 4단계: Sakugabooru source·작품 태그로 회차·최초 공개일을 매긴다.

사용: python tools/intake_step4_era.py <copyright_tags.json이 있는 폴더>
  (copyright_tags.json = https://www.sakugabooru.com/tag.json?type=3&limit=0 응답을 copyright.json으로 저장)
날짜표 D는 2026-10-18 Wikipedia(en/ja) 원문 대조 결과다. 모르면 비워 두고 미확인으로 적는다.
"""
S=sys.argv[1]
cp={t['name'] for t in json.load(open(f'{S}/copyright.json'))}
W='https://en.wikipedia.org/wiki/'
BC=W+'List_of_Black_Clover_episodes'
D={ # (work tag key, episode) -> (date, basis, conf, note)
 ('black_clover','35'):('2018-06-05',BC,'high',''),('black_clover','84'):('2019-05-21',BC,'high',''),
 ('black_clover','93'):('2019-07-23',BC,'high',''),('black_clover','136'):('2020-07-28',BC,'high',''),
 ('black_clover','151'):('2020-11-10',BC,'high',''),('black_clover','154'):('2020-12-01',BC,'high',''),
 ('black_clover','158'):('2021-01-05',BC,'high',''),
 ('black_clover','NCOP08'):('2019','https://ja.wikipedia.org/wiki/ブラッククローバー','medium','OP8 sky & blue, 제95–102화 사용(ja 위키 주제가 절). 연도는 #093=2019-07-23 기준 추론'),
 ('black_clover','NCOP13'):('2021','https://ja.wikipedia.org/wiki/ブラッククローバー','medium','OP13 Grandeur, 제158–170화(#158=2021-01-05, 방영 종료 2021-03-30)'),
 ('black_clover:_mahou_tei_no_ken','film'):('2023-06-16','https://en.wikipedia.org/wiki/List_of_Black_Clover_episodes','high','극장판 마법제의 검 공개일'),
 ('boruto:_naruto_next_generations','65'):('2018-07-19',W+'List_of_Boruto:_Naruto_Next_Generations_episodes','high',''),
 ('boruto:_naruto_next_generations','144'):('2020-02-16',W+'List_of_Boruto:_Naruto_Next_Generations_episodes','high',''),
 ('boruto:_naruto_next_generations','153'):('2020-04-19',W+'List_of_Boruto:_Naruto_Next_Generations_episodes','high',''),
 ('boruto:_naruto_next_generations','166'):('2020-09-20',W+'List_of_Boruto:_Naruto_Next_Generations_episodes','high',''),
 ('my_hero_academia_series','86'):('2020-03-21',W+'List_of_My_Hero_Academia_episodes','high',''),
 ('my_hero_academia_series','88'):('2020-04-04',W+'List_of_My_Hero_Academia_episodes','high',''),
 ('my_hero_academia_series','96'):('2021-05-15',W+'List_of_My_Hero_Academia_episodes','high',''),
 ('my_hero_academia_series','112'):('2021-09-18',W+'List_of_My_Hero_Academia_episodes','high',''),
 ('my_hero_academia_series','128'):('2023-01-14',W+'List_of_My_Hero_Academia_episodes','high',''),
 ('my_hero_academia_movie_1:_two_heroes','film'):('2018-08-03',W+'My_Hero_Academia','high','일본 개봉'),
 ('my_hero_academia_movie_2:_heroes_rising','film'):('2019-12-20',W+'My_Hero_Academia','high','일본 개봉'),
 ('my_hero_academia_movie_3:_world_heroes_mission','film'):('2021-08-06',W+'My_Hero_Academia','high','일본 개봉'),
 ('shingeki_no_kyojin','21'):('2013-09-01',W+'List_of_Attack_on_Titan_episodes','high',''),
 ('shingeki_no_kyojin','31'):('2017-05-06',W+'List_of_Attack_on_Titan_episodes','high',''),
 ('shingeki_no_kyojin','32'):('2017-05-13',W+'List_of_Attack_on_Titan_episodes','high',''),
 ('shingeki_no_kyojin','37'):('2017-06-17',W+'List_of_Attack_on_Titan_episodes','high',''),
 ('shingeki_no_kyojin_(ova)','3'):('2014-08-08',W+'List_of_Attack_on_Titan_episodes','high','OVA 3 Distress'),
 ('koutetsujou_no_kabaneri','2'):('2016-04-22',W+'Kabaneri_of_the_Iron_Fortress','high','지진 보도로 4/15에서 연기'),
 ('koutetsujou_no_kabaneri','4'):('2016-05-06',W+'Kabaneri_of_the_Iron_Fortress','high',''),
 ('koutetsujou_no_kabaneri','5'):('2016-05-12',W+'Kabaneri_of_the_Iron_Fortress','high',''),
 ('koutetsujou_no_kabaneri','12'):('2016-06-30',W+'Kabaneri_of_the_Iron_Fortress','high',''),
 ('fate/apocrypha','11'):('2017-09-10',W+'List_of_Fate/Apocrypha_episodes','high',''),
 ('fate/apocrypha','20'):('2017-11-25',W+'List_of_Fate/Apocrypha_episodes','high',''),
 ('fate/apocrypha','NCOP2'):('2017',W+'Fate/Apocrypha','medium','OP2 Ash, 13화부터(방영 2017-07-02–12-30)'),
 ("fate/stay_night:_heaven's_feel_ii._lost_butterfly",'film'):('2019-01-12',W+"Fate/stay_night:_Heaven's_Feel",'high','일본 개봉. source #02=제2장'),
 ('fate/strange_fake:_whispers_of_dawn','film'):('2023-07-02',W+'Fate/strange_Fake','high','TV 스페셜 방영'),
 ('one-punch_man_2','8'):('2019-05-29',W+'List_of_One-Punch_Man_episodes','high',''),
 ('flip_flappers','8'):('2016',W+'Flip_Flappers','medium','회차 일자 없음. 방영 2016-10-06–12-29 안'),
 ('rolling_girls','1'):('2015-01-10',W+'Rolling_Girls','high',''),('rolling_girls','4'):('2015-01-31',W+'Rolling_Girls','high',''),
 ('rolling_girls','6'):('2015-02-14',W+'Rolling_Girls','high',''),
 ('the_elusive_samurai','9'):('2024-08-31',W+'The_Elusive_Samurai','high',''),
 ('suicide_squad_isekai','5'):('2024-07-11',W+'Suicide_Squad_Isekai','high','최초 공개(일본 TV 방영은 2024-08-03)'),
 ('mօb_psycho_100_iii','4'):('2022-10-27',W+'List_of_Mob_Psycho_100_episodes','high','Sakugabooru 등록(UTC 2022-10-26)보다 하루 늦음: 시차·심야 편성 표기 차이로 추정, 연도 영향 없음'),
 ('marriagetoxin','12'):('2026-06-23',W+'Marriagetoxin','high',''),
 ('marriagetoxin','NCOP'):('2026',W+'Marriagetoxin','medium','방영 2026-04-07–06-30'),
 ('dog_days','6'):('','https://en.wikipedia.org/wiki/Dog_Days_(Japanese_TV_series)','unknown','dog_days 태그만 있어 2011/2012/2015 시리즈 중 어느 것인지 미확인'),
 ('youjo_senki','5'):('2017-02-03',W+'List_of_Saga_of_Tanya_the_Evil_episodes','high',''),
 ('flcl_alternative','1'):('2018-09-07',W+'FLCL_Alternative','high','일본 극장 공개(미국 TV 2018-09-08)'),
 ('garo_-_vanishing_line','13'):('',W+'Garo:_Vanishing_Line','unknown','회차 일자 없음. 방영 2017-10-06–2018-03-30이라 연도 미확인'),
 ('princess_connect_re:dive_season_2','4'):('2022-02-01',W+"List_of_Princess_Connect!_Re:Dive_episodes",'high',''),
 ('magi_the_labyrinth_of_magic','2'):('2012-10-14',W+'List_of_Magi:_The_Labyrinth_of_Magic_episodes','high',''),
 ('bleach:_thousand_year_blood_war_arc_season_2','25'):('2023-09-30',W+'Bleach:_Thousand-Year_Blood_War','high','S2 #12 = 통산 25'),
 ('one_piece','1017'):('2022-05-15',W+'One_Piece_season_20','high',''),
 ('scissor_seven_s4','OP'):('2023-01-18',W+'Scissor_Seven','high','시즌 4 공개일'),
 ('reverse:_1999','2nd anniversary PV'):('2025',W+'Reverse:_1999','medium','중국 출시 2023-05-31 → 2주년 2025(추론, PV 자체 공개일 미확인)'),
}
def snow(url):
    m=re.search(r'twitter\.com/[^/]+/status/(\d+)',url)
    if not m: return None
    return datetime.datetime.utcfromtimestamp(((int(m.group(1))>>22)+1288834974657)/1000).date().isoformat()
posts={}
for a in ['riooo','optical-core','yukina_kosaka']:
    for l in open(f'data/sakuga/candidates/posts_{a}.jsonl'):
        p=json.loads(l); posts[p['id']]=p
rows=[]
for f in ['intake_index_riooo_optical-core_2026-10-18.csv','intake_index_yukina_kosaka_2026-10-18.csv']:
    for r in csv.DictReader(open('data/sakuga/candidates/'+f)):
        if r['presumed']!='True': rows.append(r)
def episode(src,tags):
    m=re.match(r'#0*(\d+)',src)
    if m: return m.group(1)
    for k in ('NCOP13','NCOP08','NCOP2','2nd anniversary PV'):
        if src.startswith(k): return k
    if src.startswith('NCOP'): return 'NCOP'
    if src.startswith('OP'): return 'OP'
    return ''
FILM={'black_clover:_mahou_tei_no_ken','my_hero_academia_movie_1:_two_heroes','my_hero_academia_movie_2:_heroes_rising','my_hero_academia_movie_3:_world_heroes_mission',"fate/stay_night:_heaven's_feel_ii._lost_butterfly",'fate/strange_fake:_whispers_of_dawn'}
out={}
def resolve(pid):
    if pid in out: return out[pid]
    p=posts[pid]; src=(p['source'] or '').strip(); tags=p['tags'].split()
    works=[t for t in tags if t in cp]
    ep=episode(src,tags); res=None
    for w in sorted(works,key=lambda w:(w not in FILM)):
        if w in FILM: res=D.get((w,'film')); ep=ep or 'film'
        if not res and ep: res=D.get((w,ep))
        if res: break
    sns=snow(src); own=bool(re.search(r'reurangel_|riooorangel|OpticalCore',src))
    grade='A' if own else 'C'
    note=''
    if res:
        date,basis,conf,note=res
    elif p['parent_id'] and p['parent_id'] in posts:
        par=resolve(p['parent_id']); date,basis,conf=par['era_date'],par['basis'],par['confidence']
        note=f"parent_id={p['parent_id']} 장면의 날짜 상속"
    elif sns and own:
        date,basis,conf,note=sns,src,'medium','본인 SNS 게시일(개인작 최초 공개로 간주, 원 상업 작품이면 방영일보다 늦을 수 있음)'
    else:
        up=datetime.datetime.utcfromtimestamp(p['created_at']).date().isoformat()
        date,basis,conf='',f"https://www.sakugabooru.com/post/show/{pid}",'unknown'
        note=f"미확인. Sakugabooru 등록일 {up}은 상한일 뿐"
        if sns: note+=f", 트위터 게시일 {sns}"
    out[pid]=dict(post_id=pid,work=' '.join(works),source=src,episode=ep,era_date=date,era_year=date[:4],basis=basis,confidence=conf,proof_grade=grade,parent_id=p['parent_id'] or '',booru_posted=datetime.datetime.utcfromtimestamp(p['created_at']).date().isoformat(),note=note)
    return out[pid]
res=[]
for r in rows:
    d=dict(artist=r['artist']); d.update(resolve(int(r['post_id']))); res.append(d)
with open('data/sakuga/candidates/intake_step4_era_2026-10-18.csv','w',newline='',encoding='utf-8') as f:
    w=csv.DictWriter(f,fieldnames=list(res[0])); w.writeheader(); w.writerows(res)
import collections
print(len(res),collections.Counter((d['artist'],d['confidence']) for d in res))
print(collections.Counter((d['artist'],d['era_year'] or '미확인') for d in res))
for d in res:
    if d['confidence']=='unknown': print(d['artist'][:4],d['post_id'],d['work'][:25],d['source'][:30],d['note'][:60])
