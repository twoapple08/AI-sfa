"""요소 트리(무기·이펙트·배경·탈것 등과 그 부품·부산물)를 만든다.

사용: python tools/element_tree.py <출력 csv>
- 들여쓰기 2칸 = 한 단계 아래. 형식: 요소 | 난이도 | 관계 | 영어 이름들
  - 난이도: 1 지식없이, 2 형태참고, 3 기술필요
  - 관계(하위 요소만): 부품 / 탄 / 부산물 / 이펙트 / 종류
- 영어 이름 가운데 WD Tagger 일반 태그에 있으면 '태그', 없으면 'CLIP:이름'(글로 찾는 이미지 모델용)으로 나눈다.
"""
import csv
import glob
import os
import sys

SPEC = """
무기
  총 | 2 | | gun handgun rifle assault_rifle machine_gun submachine_gun shotgun sniper_rifle revolver
    탄창 | 1 | 부품 | magazine_(weapon)
    스코프 | 1 | 부품 | scope
    총검 | 1 | 부품 | bayonet
    레이저 조준선 | 2 | 부품 | laser_sight
    총알 | 1 | 탄 | bullet ammunition
    탄띠 | 1 | 탄 | ammunition_belt
    탄피 | 2 | 부산물 | shell_casing
    총구 화염 | 3 | 이펙트 | muzzle_flash
    탄도 궤적 | 3 | 이펙트 | bullet_trail tracer_fire
    탄착 불꽃·먼지 | 3 | 이펙트 | bullet_impact
  대포·포탑 | 2 | | cannon turret
    포신 | 1 | 부품 | gun_barrel
    포탄·대포알 | 1 | 탄 | cannonball artillery_shell
    포구 화염 | 3 | 이펙트 | muzzle_flash
    포연 | 3 | 부산물 | cannon_smoke
    착탄 폭발 | 3 | 이펙트 | shell_explosion
  미사일·로켓 | 2 | | missile rocket_launcher rocket
    미사일 궤적 연기 | 3 | 이펙트 | smoke_trail contrail
    추진 불꽃 | 3 | 이펙트 | rocket_exhaust
    다연장 발사 | 3 | 종류 | missile_swarm
  폭탄·수류탄 | 1 | | bomb grenade
    안전핀 | 1 | 부품 | grenade_pin
    폭탄 파편 | 3 | 부산물 | shrapnel
  검 | 2 | | sword katana holding_sword
    칼날 | 1 | 부품 | blade
    손잡이·코등이 | 1 | 부품 | sword_hilt tsuba
    칼집 | 1 | 부품 | sheath
    검광·궤적 | 3 | 이펙트 | sword_slash_trail slashing
    날 부딪힘 불꽃 | 3 | 이펙트 | sparks clashing_swords
    베인 자국 | 3 | 부산물 | cut_mark slash_mark
    날아가는 참격 | 3 | 이펙트 | energy_slash
  단검·칼 | 1 | | dagger knife
    던진 칼 | 2 | 종류 | throwing_knife kunai
  창·봉 | 2 | | spear polearm naginata
  도끼·둔기 | 2 | | axe hammer mace
  낫 | 2 | | scythe
  활 | 2 | | bow_(weapon)
    화살 | 1 | 탄 | arrow_(projectile)
    화살 궤적 | 3 | 이펙트 | arrow_trail
  방패 | 1 | | shield
    방패 충돌 불꽃 | 3 | 이펙트 | shield_impact_sparks
  사슬·채찍 | 2 | | chain whip
  발톱·손톱 | 2 | | claws long_fingernails
  촉수 | 3 | | tentacles
  광선검·에너지 칼 | 3 | | energy_sword lightsaber
  지팡이·마법봉 | 2 | | staff_(weapon) wand
  수리검·부메랑 | 2 | | shuriken boomerang
    회전 궤적 | 3 | 이펙트 | spinning_trail
  갈고리·와이어 | 2 | | grappling_hook wire
    와이어 궤적 | 3 | 이펙트 | wire_trail
  에너지 포 | 3 | | beam_cannon arm_cannon
  맨손 타격 | 3 | | punching kicking
    타격 섬광 | 3 | 이펙트 | impact_flash
    타격 충격파 | 3 | 이펙트 | impact_shockwave
원소 이펙트
  불 | 3 | | fire burning
    푸른 불 | 3 | 종류 | blue_fire
    불꽃 혀 | 3 | 부품 | flame_tongues
    불씨·불티 | 3 | 부산물 | embers sparks
    재 | 2 | 부산물 | ash
    아지랑이 | 3 | 부산물 | heat_haze
    불덩이 | 3 | 종류 | fireball
    화염 방사 | 3 | 종류 | flamethrower
  폭발 | 3 | | explosion explosive
    폭발 섬광 | 3 | 이펙트 | explosion_flash
    버섯구름·폭연 | 3 | 부산물 | mushroom_cloud
    충격파 고리 | 3 | 이펙트 | shockwave_ring
    폭발 파편 | 3 | 부산물 | debris
    연쇄 폭발 | 3 | 종류 | chain_explosions
  연기 | 3 | | smoke
    검은 연기 | 3 | 종류 | black_smoke
    흰 연기·증기 | 3 | 종류 | steam white_smoke
    연막 | 3 | 종류 | smoke_screen
  번개·전기 | 3 | | lightning electricity
    낙뢰 | 3 | 종류 | lightning_bolt_strike
    몸의 전류 | 3 | 종류 | electric_aura
    방전 불꽃 | 3 | 부산물 | electric_sparks
  물 | 3 | | water
    물보라 | 3 | 부산물 | splashing
    물방울 | 3 | 부산물 | water_drop
    파도 | 3 | 종류 | waves
    물기둥 | 3 | 종류 | water_pillar
    거품 | 2 | 부산물 | bubble
    소용돌이 | 3 | 종류 | whirlpool
  얼음 | 3 | | ice
    고드름 | 2 | 부품 | icicle
    얼음 조각 | 3 | 부산물 | ice_shards crystal
    서리 | 2 | 부산물 | frost
    냉기 | 3 | 이펙트 | cold_mist
  바람 | 3 | | wind
    회오리 | 3 | 종류 | tornado
    흩날림(잎·꽃잎) | 3 | 부산물 | falling_leaves petals
    풍압선 | 3 | 이펙트 | wind_lines
  흙·바위 | 3 | | rock floating_rock
    솟는 바위 | 3 | 종류 | rock_spikes
    모래 | 3 | 종류 | sand
    모래폭풍 | 3 | 종류 | sandstorm
    진흙 | 3 | 종류 | mud
  빛 | 3 | | light glowing
    섬광 | 3 | 종류 | flash
    빛줄기 | 3 | 종류 | light_rays
    렌즈 플레어 | 2 | 종류 | lens_flare
    빛 입자 | 3 | 부산물 | light_particles
  에너지 | 3 | | energy
    광선·레이저 | 3 | 종류 | energy_beam laser
    에너지 구 | 3 | 종류 | energy_ball
    오라 | 3 | 종류 | aura
    기 모으기 빛 | 3 | 종류 | charging_energy
    방어막·배리어 | 3 | 종류 | barrier force_field
  마법 | 3 | | magic
    마법진 | 3 | 종류 | magic_circle
    문양·룬 | 2 | 부품 | runes glowing_symbols
    소환 | 3 | 종류 | summoning
  체액 | 3 | | blood
    피 튐 | 3 | 부산물 | blood_splatter
    핏자국 | 2 | 부산물 | blood_stain
    괴물 체액 | 3 | 종류 | slime monster_blood
  독·산성 | 3 | | poison acid
    독안개 | 3 | 종류 | poison_gas
  어둠·그림자 | 3 | | darkness shadow
    그림자 촉수 | 3 | 종류 | shadow_tendrils
    검은 안개 | 3 | 종류 | dark_aura
  공간·중력 | 3 | | space_distortion
    차원문·포털 | 3 | 종류 | portal
    공간 균열 | 3 | 종류 | dimensional_rift
    블랙홀·중력 구 | 3 | 종류 | black_hole
  음파 | 3 | | sound_waves
  식물 | 3 | | plant vines
    덩굴 공격 | 3 | 종류 | thorny_vines
  금속·모래 조종 | 3 | | metal_manipulation
  날씨 | 3 | | weather
    비 | 3 | 종류 | rain
    눈 | 3 | 종류 | snow snowing
    안개 | 3 | 종류 | fog
    우박 | 3 | 종류 | hail
충격·파괴
  충격파 | 3 | | shockwave
    지면 충격파 | 3 | 종류 | ground_shockwave
    공기 왜곡 | 3 | 이펙트 | air_distortion
  파편 | 3 | | debris rubble
    돌·콘크리트 조각 | 3 | 종류 | rubble brick
    나무 조각 | 3 | 종류 | wood_splinters
    금속 조각 | 3 | 종류 | metal_scrap
    유리 조각 | 3 | 종류 | glass_shards shards broken_glass
  먼지 | 3 | | dust dust_cloud
    흙먼지 기둥 | 3 | 종류 | dust_plume
  균열 | 3 | | cracks
    지면 균열 | 3 | 종류 | cracked_ground
    벽 균열 | 3 | 종류 | cracked_wall
    크레이터 | 2 | 종류 | crater
  붕괴 | 3 | | destruction collapse
  그을음·탄 자국 | 2 | | scorch_marks burn_marks
  녹아내림 | 3 | | melting
    건물 붕괴 | 3 | 종류 | collapsing_building
    다리 붕괴 | 3 | 종류 | collapsing_bridge
연출
  스미어 | 3 | | motion_blur smear_frame
  속도선 | 2 | | speed_lines motion_lines
    집중선 | 2 | 종류 | emphasis_lines focus_lines
  잔상 | 3 | | afterimage
    분신 | 3 | 종류 | clone
  임팩트 프레임 | 3 | | impact_frame
    흑백 | 2 | 종류 | monochrome greyscale
    단색 | 2 | 종류 | limited_palette
    명암 반전 | 2 | 종류 | negative_image
    선화만 | 3 | 종류 | lineart
  카메라 | 3 | | camera_movement
    회전·궤도 | 3 | 종류 | rotating_camera
    흔들림 | 2 | 종류 | camera_shake
    줌·돌진 | 3 | 종류 | zoom
    배경동화 | 3 | 종류 | background_animation
  구도 | 2 | | composition
    어안 | 2 | 종류 | fisheye
    기울인 구도 | 1 | 종류 | dutch_angle
    올려다보기 | 2 | 종류 | from_below
    내려다보기 | 2 | 종류 | from_above
    원근 강조 | 3 | 종류 | perspective foreshortening
  빛·색 연출 | 2 | | lighting
    실루엣 | 1 | 종류 | silhouette
    역광 | 2 | 종류 | backlighting
    색수차 | 1 | 종류 | chromatic_aberration
    화면 분할 | 1 | 종류 | split_screen
  시간 연출 | 2 | | time_effect
    슬로모션·정지 | 2 | 종류 | slow_motion freeze_frame
  화면 처리 | 2 | | post_processing
    피사계 심도(흐림) | 2 | 종류 | depth_of_field blurry_background
    빛 번짐(블룸) | 2 | 종류 | bloom
    필름 입자 | 1 | 종류 | film_grain
    컷인 | 2 | 종류 | cut-in
    화면 전환(와이프) | 2 | 종류 | screen_wipe
  2차 움직임 | 3 | | secondary_motion
    천·망토 휘날림 | 3 | 종류 | cape floating_clothes
    머리카락 휘날림 | 3 | 종류 | floating_hair
지형·자연
  산 | 2 | | mountain mountainous_horizon
    절벽 | 2 | 부품 | cliff
    바위 | 2 | 부품 | rock
    동굴 | 2 | 부품 | cave
    협곡 | 2 | 종류 | canyon
  물가 | 3 | | river ocean lake
    강 | 3 | 종류 | river
    바다 | 3 | 종류 | ocean
    호수 | 2 | 종류 | lake
    폭포 | 3 | 종류 | waterfall
    해변·모래사장 | 1 | 종류 | beach shore
    섬 | 1 | 종류 | island
    수중 | 3 | 종류 | underwater
  숲 | 2 | | forest
    나무 | 2 | 부품 | tree
    나뭇잎 | 2 | 부품 | leaf
    풀 | 2 | 부품 | grass
    대나무 | 2 | 종류 | bamboo
  들판 | 1 | | field
  늪·습지 | 2 | | swamp
  정글 | 2 | | jungle
  빙하·빙산 | 2 | | glacier iceberg
  사막 | 1 | | desert
    모래 언덕 | 2 | 부품 | dune
  설원 | 2 | | snow
    눈 덮인 산 | 2 | 종류 | snowy_mountain
  화산 | 3 | | volcano
    용암 | 3 | 부품 | lava
    화산재 | 3 | 부산물 | volcanic_ash
  하늘 | 1 | | sky
    구름 | 3 | 부품 | cloud cloudy_sky
    노을·해 | 1 | 부품 | sunset sun
    밤하늘·별 | 1 | 부품 | night_sky starry_sky
    무지개 | 1 | 부품 | rainbow
    오로라 | 3 | 부품 | aurora
  우주 | 1 | | space
    행성·달 | 1 | 부품 | planet moon
    운석 | 3 | 부품 | meteor
    성운 | 2 | 부품 | nebula
인공 배경
  도시 | 2 | | city cityscape
    고층 빌딩 | 1 | 부품 | skyscraper
    도로·거리 | 1 | 부품 | road street
    간판·네온 | 1 | 부품 | sign neon_lights
    전봇대·전선 | 1 | 부품 | power_lines utility_pole
    신호등 | 1 | 부품 | traffic_light
    가로등 | 1 | 부품 | lamppost
  건물 | 1 | | building
    유리창 | 1 | 부품 | window
    벽 | 1 | 부품 | wall
    지붕 | 1 | 부품 | rooftop
    계단 | 2 | 부품 | stairs
    철근 | 2 | 부산물 | rebar
  실내 | 1 | | indoors
    복도 | 1 | 종류 | hallway
    기둥 | 1 | 부품 | pillar
    가구 | 2 | 부품 | furniture
  폐허 | 2 | | ruins
    무너진 잔해 더미 | 3 | 부품 | rubble
  다리 | 2 | | bridge
  철로 | 1 | | railroad_tracks
  성·탑 | 2 | | castle tower
  공장·기계 | 2 | | machinery
    톱니 | 1 | 부품 | gears
    파이프 | 1 | 부품 | pipe
    전선·케이블 | 2 | 부품 | cable wire
  항구 | 2 | | harbor pier
    크레인 | 2 | 부품 | crane_(machine)
  학교·교실 | 1 | | school classroom
  신사·절 | 2 | | shrine torii temple
  주택가 | 1 | | residential_area house
  지하·지하철 | 2 | | subway underground
  경기장·투기장 | 2 | | arena stadium
  기지·요새 | 2 | | military_base fortress
    성벽 | 2 | 부품 | castle_wall
  연구소·실험실 | 2 | | laboratory
  우주정거장 | 2 | | space_station
탈것
  자동차 | 2 | | car
    바퀴 | 1 | 부품 | wheel
    타이어 자국 | 2 | 부산물 | tire_marks
    배기 연기 | 3 | 부산물 | exhaust
    전조등 빛 | 2 | 이펙트 | headlights
  오토바이 | 2 | | motorcycle
  트럭 | 2 | | truck
  기차 | 2 | | train
    객차 | 2 | 부품 | train_car
  배 | 2 | | ship boat watercraft
    돛 | 1 | 부품 | sail
    항적 물보라 | 3 | 부산물 | wake_(water)
  군함 | 2 | | warship
    함포 | 2 | 부품 | naval_gun
  비행기 | 2 | | airplane aircraft
    프로펠러 | 2 | 부품 | propeller
    비행운 | 3 | 부산물 | contrail
  헬기 | 2 | | helicopter
    로터 | 2 | 부품 | rotor
  우주선 | 2 | | spacecraft
    추진 불꽃 | 3 | 이펙트 | thruster_flame
  전차 | 2 | | tank
    무한궤도 | 2 | 부품 | tank_treads
  버스 | 2 | | bus
  자전거 | 2 | | bicycle
  잠수함 | 2 | | submarine
  비행선 | 2 | | airship
  말·탈것 동물 | 3 | | horse horseback_riding
상대·생물
  로봇·메카 | 2 | | mecha robot
    장갑판 | 2 | 부품 | armor_plates
    관절 | 2 | 부품 | mechanical_joints
    추진기 불꽃 | 3 | 이펙트 | thrusters
    미사일 포드 | 2 | 부품 | missile_pod
    장갑 파편 | 3 | 부산물 | mecha_debris
    눈·센서 빛 | 2 | 이펙트 | glowing_eyes
  괴물 | 3 | | monster
    이빨·입 | 2 | 부품 | teeth sharp_teeth
    촉수 | 3 | 부품 | tentacles
    체액 | 3 | 부산물 | slime
  거대 생물 | 3 | | giant kaiju
  용 | 3 | | dragon
    날개 | 3 | 부품 | dragon_wings
    비늘 | 2 | 부품 | scales
    브레스 | 3 | 이펙트 | breath_weapon
  짐승 | 2 | | animal wolf
    털 휘날림 | 3 | 이펙트 | fur
  새 | 2 | | bird
    깃털 | 2 | 부산물 | feathers
  곤충·벌레 | 2 | | insect bug
  해골·언데드 | 2 | | skeleton skull zombie
  군중·군대 | 2 | | crowd army soldier
  유령·정령 | 3 | | ghost spirit
  슬라임 | 3 | | slime_(creature)
  식물 괴물 | 3 | | plant_monster
장비·의상
  갑옷 | 2 | | armor
    갑옷 파편 | 3 | 부산물 | broken_armor
  투구·헬멧 | 2 | | helmet
  가면 | 1 | | mask
  망토 | 2 | | cape cloak
  고글 | 1 | | goggles
  날개 장비·추진팩 | 2 | | jetpack mechanical_wings
"""


def main():
    out = sys.argv[1]
    d = glob.glob(os.path.expanduser('~/.cache/huggingface/hub/models--SmilingWolf--wd-vit-tagger-v3/snapshots/*'))[0]
    names = {r['name'] for r in csv.DictReader(open(os.path.join(d, 'selected_tags.csv'))) if r['category'] == '0'}
    rows, stack = [], []
    for line in SPEC.strip('\n').split('\n'):
        if not line.strip():
            continue
        lv = (len(line) - len(line.lstrip(' '))) // 2
        parts = [x.strip() for x in line.split('|')]
        stack = stack[:lv]
        pid = stack[-1] if stack else ''
        rid = str(len(rows) + 1)
        if len(parts) == 1:
            rows.append([rid, pid, lv, parts[0], '', '', '', ''])
        else:
            en = parts[3].split()
            rows.append([rid, pid, lv, parts[0], parts[2], parts[1], ' '.join(x for x in en if x in names),
                         ' '.join(x for x in en if x not in names)])
        stack.append(rid)
    with open(out, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['번호', '부모번호', '단계', '요소', '관계', '난이도', '태그', 'CLIP'])
        w.writerows(rows)
    el = [r for r in rows if r[2] > 0]
    print('전체', len(rows), '분류', sum(r[2] == 0 for r in rows), '요소', sum(r[2] == 1 for r in rows),
          '하위', sum(r[2] == 2 for r in rows), '태그만', sum(bool(r[6]) and not r[7] for r in el),
          'CLIP만', sum(bool(r[7]) and not r[6] for r in el), '둘다', sum(bool(r[6]) and bool(r[7]) for r in el))


if __name__ == '__main__':
    main()
