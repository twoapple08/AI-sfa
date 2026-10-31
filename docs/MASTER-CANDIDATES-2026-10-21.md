# 고수 후보 통계 (2026-10-21, Claude) — 보충 계획 5단계, 메타데이터만

Sakugabooru 게시물 수 상위 200명과 지정 후보(웨일린 장)를 대상으로, 공백 분야 태그 수와 나카무라식 태그 비율을 셌다. **영상은 받지 않았다.** 승낙 전 후보 목록이다.

- 도구: `tools/master_candidates.py`
- 결과: `data/style_kb/master_candidates_2026-10-21.csv`(205명)
- **나카무라 유사도:** 스타일 태그 9개의 비율 벡터 코사인 값이다(smears·debris·yutapon_cubes·background_animation·smoke·explosions·beams·lightning·fire).
  - **한계:** 많은 애니메이터가 0.95 근처에 몰려 변별력이 약하다.
  - `yutapon_cubes`(나카무라 큐브 파편) 수가 더 직접적인 표지다.
  - 실제 섞임은 블라인드 시험(`docs/BLIND-TEST-DESIGN-2026-10-21.md`)으로 정한다.
- **그 밖의 한계**
  - 게시물 수에는 셀 시대 작업도 섞여 있다. 연도는 보지 않았다.
  - 상위 200명에는 디즈니 고전 애니메이터(milt_kahl 등)도 들어 있다.
  - 태그는 거칠다. vehicle이 무슨 탈것인지 모른다.
- 아래 표에서 뺀 사람: 이미 승낙한 5명(나카무라·nian41·riooo·optical-core·yukina)과 사용자가 반려한 3명(isuta_meister·katsumi_ishizuka·sota_shigetsugu)
- 표에 넣은 사람: 유사도 0.90 이상이고 게시물 50개 이상인 사람

## 분야별 상위 (게시물 수)

| 분야 | 후보(태그 게시물 수) |
|---|---|
| 탈것 (`vehicle`) | toshiyuki_inoue 42, shinsaku_kozuma 39, hisashi_mori 31, tsutomu_oshiro 30, takafumi_hori 24, yasunori_miyazawa 22 |
| 미사일 (`missiles`) | mitsuo_iso 16, ryo_tanaka 14, keisuke_watabe 13, yoh_yoshinari 11, chikashi_kubota 10, ken_otsuka 9 |
| 군중 (`crowd`) | norio_matsumoto 38, toshiyuki_inoue 25, shinji_otsuka 18, yasunori_miyazawa 17, yuki_hayashi 17, shinsaku_kozuma 16 |
| 짐승·동물 (`animals`) | toshiyuki_inoue 69, ryo_tanaka 31, takeshi_honda 29, takahiro_kishida 29, norio_matsumoto 27, yasunori_miyazawa 22 |
| 물·액체 (`liquid`) | hironori_tanaka 172, toshiyuki_sato 101, toshiyuki_inoue 99, ryo_tanaka 85, kazuhiro_miwa 82, yasunori_miyazawa 71 |
| 생물 (`creatures`) | toshiyuki_sato 110, tsutomu_oshiro 110, toshiyuki_inoue 109, naotoshi_shida 101, hironori_tanaka 98, ryo_tanaka 96 |
| 메카 (`mecha`) | yoh_yoshinari 110, ryo_tanaka 87, ken_otsuka 79, hiroyuki_imaishi 64, tsutomu_oshiro 61, keisuke_watabe 59 |
| 바람 (`wind`) | yong-ce_tu 119, hironori_tanaka 82, kazuhiro_miwa 82, tatsuya_yoshihara 76, nozomu_abe 72, hayato_kurosaki 67 |

## 나카무라 큐브(yutapon_cubes)를 쓴 애니메이터

yong-ce_tu 5, masahiro_sato 4, takafumi_torii 4, hironori_tanaka 3, arifumi_imai 3, yoshimichi_kameda 3, masami_mori 3, tatsuya_miki 3, shingo_yamashita 3, takahiro_shikama 3 (나카무라 본인 55)

## 웨일린 장(weilin_zhang, 사용자 지정 후보)

- 게시물 81개(post 검색 기준), 나카무라 유사도 0.958
- 분야 태그: 탈것 7, 미사일 2, 물·액체 16, 생물 23, 짐승 8, 군중 6, 메카 0, 바람 20
- 스타일 태그: smears 37, debris 27, yutapon_cubes 1
- 판단: 유사도는 상위권(0.958)이지만 게시물 수가 적어 분야를 채우는 양은 작다. 탈것·미사일 보충원으로는 약하고 바람·생물 쪽이다.

## 다음

- 분야별 상위 후보 가운데 승낙 후보를 사용자와 고른다.
- 그 후보의 영상 몇 개로 '섞임 점수'(cv·CLIP 거리)와 블라인드 시험을 한다. 시험용 다운로드 범위는 사용자가 정한다.
- 탈것·미사일은 후보들도 태그 수가 적다. 계획대로 3D 형태와 번역 규칙이 주력이다.
