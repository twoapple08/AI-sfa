AI-sfa 프로젝트를 이어 맡아 줘. 처음 참여한다고 생각하고 아래 인계를 읽은 뒤 현재 미완 작업을 계속해. 모든 답은 한국어로 해.

저장소는 GitHub twoapple08/AI-sfa, 브랜치는 claude/new-session-gknz4t만 사용해. main은 읽지도 쓰지도 마. GitHub와 Google Drive가 연결되어 있고, 원본은 Drive AI-sfa/01_원본영상/, 분석·결과는02_분석자료/, 모바일뷰어는07_도구/SFA뷰어/에 있어.

다음 순서로 읽어:
1. AGENTS.md 전체 → HANDOFF.md → docs/NEW-COLLABORATOR-ONBOARDING-2026-11-04.md
2. .claude/skills/stickman-extraction/START-HERE.md → SKILL.md → references/CURRENT-STATE.md와DECISIONS-AND-LIMITS.md
3. docs/SESSION-COMPLETE-HANDOFF-2026-11-04.md와docs/GPT-TAKEOVER-LOG-2026-11-03.md. 로그의커밋과실제코드도대조해.
4. docs/STICKMAN-DISPLAY-MOTION-FIX-2026-11-04.md. 10초판 판단배경이필요하면STICKMAN-OVERLAP-DEBATE-2026-11-03.md의5차종결과STICKMAN-CLIP-1032-1271-2026-11-03.md.

인계 폴더: https://drive.google.com/drive/folders/1UQ9rJ3H-VYc7l1kAqVDNjebe8b-2baKK
스킬 안data/artifact_manifest.json에는13종파일의Drive ID/SHA/역할,archive_inventory.json에는중첩파일752항목,data/generalization_cases.json에는최신24개개발사례가있어. 실제자료는Git제외private-data/에모았고다른환경에서는Drive자료를내려받아scripts/restore_data.py --import-path로복원해. 원본/전체좌표/프레임/SFA/가중치/앱녹화/토큰·서명키는Git에넣거나출력하지마.

프로젝트는①사람2D모션→스틱맨SFA ②사물·배경·이펙트등그림→SFA변환기의두부품을개발중이야. 최종목표는편집가능SFA창작AI. 현재클립은일반화개선용개발자료이고held_out=false/training_ready=false야. 같은영상24사례를새영상24개나자동정답으로세지마. 새영상일반화는보정하지않은새입력에공통처리만적용한첫결과로별도검증해야해.

최신수정SFA: https://drive.google.com/file/d/1ypI8kpPl-B_D_PjCC9MybVVpoitORGGp/view
재현묶음: https://drive.google.com/file/d/1xzyOVobHLMWbr-Vc7dZnQ3fcNkQ4vFli/view
원본432–1871/재생1–1440/24fps기준60초,원본=재생+431. 최신구현8cad3d73441877720ad4f0b865e855eeb9e60d17,인계전HEAD6a851dda70fa039e46a01bbf79108d74845f01cf. 최신인계커밋은지정브랜치로그/GPT로그마지막절을봐. 11결정입력/229코드지문으로보존중간뼈대부터최종XMLf2141adf…일치검증했지만새원본에서눈판정을자동복제한것은아니야. 불일치하면해시검사를끄지말고정확한코드/입력을복구해.

최신판은99/169/320/516구겨짐·951굵기/한줄기면·868/969앞뒤·1144(원본1575)앞팔누락을수정했어. 737–784팔흔들림은팔끝이아니라병/파편오검출에끌린허브를고쳤고팔끝변경0이야. 구조검사0/직전304시험통과지만최신1분판의전장눈판정·실제앱은미완료야. 미리보기영상은만들지말고SFA와필요정지근거로계속해.

현재규칙: 사람만추출/2D/직선몸통/기본11편집망/장마다새점ID/장간객체ID유지/Flags3하나/(24,24)/틀밖허용. 투영길이는변해도돼. 머리흰Kind1/A안/내부투명연결유지. 손가락·발가락·발길이는0,근경단순연속면은유지. 고정50px폭fallback금지. 실제접촉만보완하고회피를붙이지마. 고점수/색지지/구조0을신체의미정답으로보지마. 수동/CPU/원본눈/추론/앱확인을구분하고같은증상은공통원인을관측→뺀점→출력으로찾아. 기록만하고끝내지말고확인한수정가능오류는실제수정·검증까지해.

Kaggle모니터링은네담당이야. twoapple08/aisfa-seq-refine-ab-v1 version2의마지막실제관측은2026-11-04 12:13 KST RUNNING. 상태/출력부터확인해. 본2회차는78709/전체미통과,같은부모·자료·각500update/각최대20분A/B가승인됐고v1글꼴오류후승인수정v2를실행했어. 완료/comparable/업데이트수와같은조건그림을확인해보고해. 임의재실행/3회차/새GPU학습은별도허락전하지마. 추가30시간은현재계정소진뒤다른계정을연결해준다는뜻으로아직연결되지않았어.

바로할일: 최신SFA/시트사용자판정·앱확인을이어받고,Kaggle실제출력을확인하고,남은5겹침/24수치후보는원본과대조해. 과거10초승인을새1분/일반화승인으로확대하지마. 커밋전루트에서python -m unittest discover -s tests전체OK/exit0을따로확인해(실패하면커밋하지마). 저장전지정브랜치최신을받고다른변경보존,HANDOFF/GPT로그에코드·이유·검증·SHA를남겨. 우선읽고현재상태를짧게설명한뒤미완작업을계속해.
