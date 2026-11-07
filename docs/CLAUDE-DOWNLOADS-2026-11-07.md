# Claude 자료 다운로드 — 로그인 없이 받는 공유사본

사용자가 기존 비공개 Drive 자료 전부를 Claude가 받을 수 있게 요청했다. 기존 원본은 보존하고 전달본을 새 폴더로 복사했다. 이 폴더는 **링크를 아는 사람 읽기**, 검색 노출 꺼짐이며 기존 비공개 링크의 권한이 바뀐 것은 아니다.

**공유 폴더:** https://drive.google.com/drive/folders/1VSqs4ujWnby8bwQOCI_zaHEXyT2lJnnY

**먼저 받을 인계32파일묶음:** https://drive.google.com/file/d/1iG75vAikQAro6IYlomKH0i6xDPHLAVTc/view

이 묶음은 원본과 동일한3,327,073바이트/SHA256 `c763561989c46fd05332f1500962d0de34d9bb36aafb71e62f42edb5a6254958`로 **로그인 없이 전체 다운로드 검증**했다.

## Claude에서 직접 다운로드

```bash
curl -L --fail 'https://drive.usercontent.google.com/download?id=1iG75vAikQAro6IYlomKH0i6xDPHLAVTc&export=download&confirm=t' -o claude_session_bundle.zip
```

공유사본71개 전체의이름·새ID·기존ID대응·바이트·MD5·다운로드URL은 `data/claude_shared_downloads_2026-11-07.json`에있다. 이전인계문서의비공개ID가아니라**이새목록**을사용한다. 현재스미어기술은별도 `스미어기술_코드프로필_독립묶음.zip`에도분리했다. 코드와프로필은동일Git브랜치에도이미있다.

공유본에는최신/이전SFA·영상·비교이미지·v8~v14·선택v13 B4·밀도v1·현재레칸v2·자동탐지실패자료·코드/프로필·초기observed/발검토·원본영상/RTMW를포함한다. 실패결과를승인판으로오인하지않도록전체인계문서의판정을따른다. 원본/좌표를Git에올린것은아니며,이파일은사용자가공유를요청한Drive사본의링크색인이다.

**검증:** 71개전부무인증다운로드HTTP200/HTML아님/파일선두64바이트확인. 모든파일전체바이트를재다운로드검사한것은아니며,핵심묶음은전체SHA까지검사했다. 실제Claude계정실행은아직미확인이다.

## 파일 목록

|파일|바이트|공유사본|
|---|---:|---|
|1913231262086463573.jsonl.gz|4864151|[받기](https://drive.usercontent.google.com/download?id=17TB3ZQ_rK-nA_L4XQ0GbM1VMS9lZBO8t&export=download&confirm=t)|
|1913231262086463573.mp4|34716419|[받기](https://drive.usercontent.google.com/download?id=16GL1ut1Sg4llD_qtQ-WGrukc5X6moWag&export=download&confirm=t)|
|Claude_세션인계_비공개실행자료_2026-11-07.zip|3327073|[받기](https://drive.usercontent.google.com/download?id=1iG75vAikQAro6IYlomKH0i6xDPHLAVTc&export=download&confirm=t)|
|nian41_10초_기본폭_vs_폭55퍼센트.png|1302225|[받기](https://drive.usercontent.google.com/download?id=14Lr1h2XOGchaJAjJ4EW3WKDQiWnrIbP3&export=download&confirm=t)|
|nian41_10초_레칸_스미어200퍼센트_머리채움수정.sfa|575382|[받기](https://drive.usercontent.google.com/download?id=1vWp7QFsU8gV8dHyaYmyLh6n_h_OxLbMS&export=download&confirm=t)|
|nian41_10초_레칸_스미어누락보충_v2.sfa|758831|[받기](https://drive.usercontent.google.com/download?id=1XOKc3L1Z7p4kWvhdcZKOZ9x_4qWB2oUX&export=download&confirm=t)|
|nian41_10초_레칸_스미어누락보충_v2_원본겹침.mp4|5008126|[받기](https://drive.usercontent.google.com/download?id=1ALhsIq5Dq2BBydINWrFdVAeOvRyZDvaN&export=download&confirm=t)|
|nian41_10초_레칸_원본겹침_머리채움수정.mp4|4961014|[받기](https://drive.usercontent.google.com/download?id=14eRvzl6bqE4RBxDVGFuF6zpVQ-CZtoI_&export=download&confirm=t)|
|nian41_10초_스미어_기본폭.sfa|330253|[받기](https://drive.usercontent.google.com/download?id=1ViNiz7mY4kzResbjlI5kZ0xGCqLUz8f9&export=download&confirm=t)|
|nian41_10초_스미어_두버전.zip|3348596|[받기](https://drive.usercontent.google.com/download?id=1HDCrHL1hoZee7CIYB6H-dafoswqQkf_L&export=download&confirm=t)|
|nian41_10초_스미어_폭55퍼센트.sfa|330026|[받기](https://drive.usercontent.google.com/download?id=1a3v3zP_PCTzmNY1G7j6y3LwEDmnR8K9L&export=download&confirm=t)|
|nian41_10초_스미어선200퍼센트_부위비례폭_경량.sfa|314459|[받기](https://drive.usercontent.google.com/download?id=11sKM1g8122y6iBYg-69L6eaav2M2Scjf&export=download&confirm=t)|
|nian41_기본폭_부위굵기100_70_경량두판.zip|1458775|[받기](https://drive.usercontent.google.com/download?id=1hgw5mN5600Gv419ipTbmwd-_BjtDIFMv&export=download&confirm=t)|
|nian41_기본폭_부위굵기100_vs70.png|935146|[받기](https://drive.usercontent.google.com/download?id=1Fx7UPZGZtTyyPIOUOB6MzBiRahzHVEaS&export=download&confirm=t)|
|nian41_기본폭_부위굵기100퍼센트_경량.sfa|313841|[받기](https://drive.usercontent.google.com/download?id=17nbGKoy1GHbkZEss8EdU9KWuLr5G8XyH&export=download&confirm=t)|
|nian41_기본폭_부위굵기70퍼센트_경량.sfa|314068|[받기](https://drive.usercontent.google.com/download?id=1al3AKkVxI20aARlFX4G29j_mCGJ5qTYM&export=download&confirm=t)|
|nian41_기존스미어선200퍼센트_부위비례폭_비교.png|1029023|[받기](https://drive.usercontent.google.com/download?id=1O4HbiI1G2R9wmvWU-AGQAM-AvQRqd0zu&export=download&confirm=t)|
|nian41_스미어누락보충_원본이전보충_비교.png|1430278|[받기](https://drive.usercontent.google.com/download?id=1NxqZuKPcHt8Wa0jUdVRNB08xsCg8qG9R&export=download&confirm=t)|
|nian41_자동탐색_미적용후보_1.png|500361|[받기](https://drive.usercontent.google.com/download?id=1nUvh41TkYsz7YCPs3MqxqaqX6f_K4MJr&export=download&confirm=t)|
|nian41_전체240장_스미어자동후보탐색.mp4|4743712|[받기](https://drive.usercontent.google.com/download?id=1P3JGPZKwLaLVY_PyLnuyleTd-I1f09Dx&export=download&confirm=t)|
|nian41_전체스미어자동후보탐색_영상시트자료.zip|6081144|[받기](https://drive.usercontent.google.com/download?id=1H0T7NnbWcLwRrvrk6A1ebkDpv3Nnxffz&export=download&confirm=t)|
|smear_v1_six_cases.png|33756|[받기](https://drive.usercontent.google.com/download?id=1T8xYWPaxBoPU8Q9eNI8MoLMQkTbSdm0o&export=download&confirm=t)|
|straight_sweep_effect_fixed.sfa|144694|[받기](https://drive.usercontent.google.com/download?id=1Gd6TQMN0J8p6QSbQW_Z8nv_HMky5RvdL&export=download&confirm=t)|
|가려진어깨_수정_v6.sfa|54529|[받기](https://drive.usercontent.google.com/download?id=1ZfpSNcl8B6TOwbpwpjdwPRfNviLYPECi&export=download&confirm=t)|
|가려진어깨_수정_v6.zip|1921372|[받기](https://drive.usercontent.google.com/download?id=1YtQu15bwtRWETb4aD6g1uaV4Dpe3pLBA&export=download&confirm=t)|
|선택했던_v13_B4_12_26_원본보존.png|87666|[받기](https://drive.usercontent.google.com/download?id=1knSTxo3YxK2IhdqNrA3oiMbMEJGvJhXp&export=download&confirm=t)|
|선택했던_v13_B4_원본.sfa|1813|[받기](https://drive.usercontent.google.com/download?id=1AtLBsKj9JUMhWrn5JdC5NxknbTRQyepx&export=download&confirm=t)|
|스미어_56경로_전체이미지_비교.zip|11166762|[받기](https://drive.usercontent.google.com/download?id=1rsidSK0RuO8zIXaoBjjgokNeHID1gWlG&export=download&confirm=t)|
|스미어_v10_굵기고정_밀도A_B비교.png|168615|[받기](https://drive.usercontent.google.com/download?id=1IjjGhbRjJWOgeNSdhy1ZAqexZThNIpu6&export=download&confirm=t)|
|스미어_v10_밀도A_B_SFA비교묶음.zip|2482558|[받기](https://drive.usercontent.google.com/download?id=1zkF4SiEcJyIP1HCSC0LBQ6HmII4QG6QI&export=download&confirm=t)|
|스미어_v11_기존점유지_추가점안쪽_비교.png|159186|[받기](https://drive.usercontent.google.com/download?id=13AEky1WZwP_tMCGW5mMd66HlPTaHDm71&export=download&confirm=t)|
|스미어_v11_추가점안쪽_SFA비교묶음.zip|2333388|[받기](https://drive.usercontent.google.com/download?id=153HjzVPOj8qQTrHBgu2HCKlNSH8XWYIb&export=download&confirm=t)|
|스미어_v12_간격깊이변화_SFA비교묶음.zip|2327490|[받기](https://drive.usercontent.google.com/download?id=1Sc7vzxOl40-nfY4veQVVyQznsuC0R_gR&export=download&confirm=t)|
|스미어_v12_추가점_간격과깊이_변화.png|152964|[받기](https://drive.usercontent.google.com/download?id=1wQWJv1qfcfICZp7YXQx-6AKUnSDLCWj8&export=download&confirm=t)|
|스미어_v13_깊이12에서26퍼센트_SFA묶음.zip|2329335|[받기](https://drive.usercontent.google.com/download?id=1FC2jx5_HkGqVbpUZkwfeJ-qJeEdgsRSr&export=download&confirm=t)|
|스미어_v13_깊이12에서26퍼센트_비교.png|153855|[받기](https://drive.usercontent.google.com/download?id=1YEHRBOeE7d07NHNEUrFaZ5SODuFpctCQ&export=download&confirm=t)|
|스미어_v14_3번_14선_SFA비교묶음.zip|338010|[받기](https://drive.usercontent.google.com/download?id=16lNJa1jVjGhRlA81W5zhZSzRQcsNLCyJ&export=download&confirm=t)|
|스미어_v14_3번만_12선에서14선_비교.png|56666|[받기](https://drive.usercontent.google.com/download?id=1GOM865fe4HlIkR0Qemi-7SNpTJ9NZGJv&export=download&confirm=t)|
|스미어_v5_원본겹침_9장.png|1832936|[받기](https://drive.usercontent.google.com/download?id=1P_yH0_Ceq_XcKDwplY0I3rcScQQwvW_t&export=download&confirm=t)|
|스미어_v5_원본겹침_대표장.png|278215|[받기](https://drive.usercontent.google.com/download?id=1SBGfO7JaW_HeDa8wCB6QA9XtyXInpNZj&export=download&confirm=t)|
|스미어_v5_원본겹침_확대.png|354425|[받기](https://drive.usercontent.google.com/download?id=1GT2VSYQTUGtGm8TleOC_qOp7THvhUUvi&export=download&confirm=t)|
|스미어_v5_확대비교.png|41839|[받기](https://drive.usercontent.google.com/download?id=1Uuh_e8xEQCgMwOq8y-9QoB3LAduViD3V&export=download&confirm=t)|
|스미어_v8_38선과12선_입력포함_비교묶음.zip|1134727|[받기](https://drive.usercontent.google.com/download?id=1sUWHCu1-UpesnD9jEMO4Jd8392cp3zQQ&export=download&confirm=t)|
|스미어_v8_원본과수동경계_비교.png|60669|[받기](https://drive.usercontent.google.com/download?id=1Ju9W45aRv8TFUKWbPxsssRrgSYlhfHN6&export=download&confirm=t)|
|스미어_v9_다른모양3개_원본비교.png|153937|[받기](https://drive.usercontent.google.com/download?id=1UL-JesFrs8uzA9e1JTXBmRIbYnd2ARQV&export=download&confirm=t)|
|스미어_v9_다른모양_SFA와비교묶음.zip|2028305|[받기](https://drive.usercontent.google.com/download?id=1r1kFJzYVuRfLqQniphgHj6MxlEB_YLMA&export=download&confirm=t)|
|스미어_거리밀도시스템_v1_간격과깊이자동비교.png|163460|[받기](https://drive.usercontent.google.com/download?id=11jh6rggsrNbU_cMvKyJnptUN3w4-HkP2&export=download&confirm=t)|
|스미어_거리밀도시스템_v1_실행코드와SFA.zip|1246149|[받기](https://drive.usercontent.google.com/download?id=1yHxbzecXSc03UB8BOwvMazQtYmRRpIY8&export=download&confirm=t)|
|스미어_길이통합_v5.sfa|48703|[받기](https://drive.usercontent.google.com/download?id=1Ki0lblcEwt550hZc6NymxMRVO1xXfyhX&export=download&confirm=t)|
|스미어_길이통합_v5_전체.zip|983224|[받기](https://drive.usercontent.google.com/download?id=1ezz46eUqeQCs2nO_KjFzILxKpd7V_iEa&export=download&confirm=t)|
|스미어_도구별_선추출_비교.png|353170|[받기](https://drive.usercontent.google.com/download?id=1cxeX1TJYhncDDv__h8IjZXMdo9wGmhnb&export=download&confirm=t)|
|스미어_도구별_영역분리_비교.png|365839|[받기](https://drive.usercontent.google.com/download?id=1VfYXzvQF3JQu-cdd7xaMrZPRJtcwgGup&export=download&confirm=t)|
|스미어_연결길이_원본비교_v7.png|306278|[받기](https://drive.usercontent.google.com/download?id=1j9aSJGWAyXwfwQKdHOF7fFxSxoRyalCV&export=download&confirm=t)|
|스미어_연결길이연장_v7.sfa|54723|[받기](https://drive.usercontent.google.com/download?id=1Dm6JAgj_g5Xyzu8HTEsk3a8qYeecVZgO&export=download&confirm=t)|
|스미어_연결길이연장_v7.zip|613893|[받기](https://drive.usercontent.google.com/download?id=13SQw2GUq-vNtwoHq9qFbV0dutMv_Eksr&export=download&confirm=t)|
|스미어_외곽과중심선_비교.png|204503|[받기](https://drive.usercontent.google.com/download?id=13-kEuv2Ec9FMh5Uo-ILkwIZE7I2M8sm8&export=download&confirm=t)|
|스미어_전체도구_실행상태.png|181679|[받기](https://drive.usercontent.google.com/download?id=1siibgtZNMmU-FS7vO-rxThL_gTV8WaBq&export=download&confirm=t)|
|스미어_조합별_원본겹침_비교.png|294373|[받기](https://drive.usercontent.google.com/download?id=1s0LxMND8TMcsiRd0z4akw3vb30nXWGY6&export=download&confirm=t)|
|스미어기술_코드프로필_독립묶음.zip|23040|[받기](https://drive.usercontent.google.com/download?id=1d-eFSJj2r_OqGE_FrFDgDH6u1ly-TXPp&export=download&confirm=t)|
|애니19_사람만수정_스미어동일.sfa|7964|[받기](https://drive.usercontent.google.com/download?id=1f1x3fO4Q_cJgug1x0qJUIzvubsvq4EXl&export=download&confirm=t)|
|애니19_사람만수정_이전비교.png|642802|[받기](https://drive.usercontent.google.com/download?id=1VJyljXRIp7Fn-j6iG9z5v7FDhUFqmDbn&export=download&confirm=t)|
|애니19_양팔몸스미어_v1.sfa|6991|[받기](https://drive.usercontent.google.com/download?id=1UsEM7i-E3jGIaZmHnS7oGSzbw4BLxJjo&export=download&confirm=t)|
|애니19_양팔몸스미어_전체비교.png|580701|[받기](https://drive.usercontent.google.com/download?id=1OKcinq-VT11kgi4kV3LL5yq-GdHUJEQT&export=download&confirm=t)|
|애니19_원본SFA템플릿복구.sfa|6473|[받기](https://drive.usercontent.google.com/download?id=1xuyrJ90GNFcBK6Hyk5Px-GWYSdrSEd3y&export=download&confirm=t)|
|애니19_원본SFA템플릿복구_전체비교.png|578132|[받기](https://drive.usercontent.google.com/download?id=1jsLGXxUSdHZXmMzH0yMVqw6x2fftgSxb&export=download&confirm=t)|
|애니19프레임_v1_원본겹침비교.png|289158|[받기](https://drive.usercontent.google.com/download?id=1IgV-pDqmSq_wJs4se033rjKhTciTpdXB&export=download&confirm=t)|
|애니19프레임_스미어_v1.sfa|1381|[받기](https://drive.usercontent.google.com/download?id=1eU7EXFJJLOj__KKHKHssJa3_PDfIP9sv&export=download&confirm=t)|
|어깨_팔꿈치_원본비교_v6.png|761700|[받기](https://drive.usercontent.google.com/download?id=1cg-r80FYGKYC9Q3eBElg6g1PSGPZFG7N&export=download&confirm=t)|
|초기_observed_뼈대검토.zip|647444|[받기](https://drive.usercontent.google.com/download?id=1cMjOmm5kcmewVAJ3UfscDcW1p5UN4Ih8&export=download&confirm=t)|
|초기_뒤꿈치검토_v3.zip|630564|[받기](https://drive.usercontent.google.com/download?id=1wozgNiqFoItNjEaVNq2L1ifhHNFW_Q6W&export=download&confirm=t)|
|초기_발끝검토_v2.zip|625161|[받기](https://drive.usercontent.google.com/download?id=1KD-DoVYHe22Mo9cmWQ7YyatUIlgkl0Or&export=download&confirm=t)|
