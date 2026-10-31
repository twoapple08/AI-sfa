# 학교 PC 세팅 안내 (2026-10-26)

PC: i7-8700(6코어 12스레드), 램 16GB, **GTX 1050 Ti 4GB**, C SSD(재부팅하면 초기화), D HDD 301GB(유지).
→ **모든 것을 D:\sfa 에 설치**하고, 사용자 폴더·AppData·캐시·임시 폴더도 D로 돌린다(`school_env.bat`). 재부팅 뒤에도 D에 설치된 것을 그대로 쓴다.

## 역할
- 그림 생성 몇 장 바로 해 보기: ComfyUI(브라우저 화면), SDXL Illustrious-XL v1.0 + 이펙트 LoRA.
- 그림 → SFA 변환: 파일을 bat에 끌어다 놓기(서버 CPU 4코어보다 빠름).
- 학습·대량 생성은 Kaggle에서 한다(1050 Ti 4GB로 SDXL 학습은 불가).

## 준비물 (Drive `AI-sfa/학교PC/`)
`school_setup.bat`, `school_env.bat` 두 파일만 있으면 된다. 나머지(`school_comfy.bat`, `school_comfy_nofp8.bat`, `school_to_sfa_fx.bat`, `school_to_sfa_line.bat`, `school_workflow.json`)는 설치하면서 저장소에서 받아 D:\sfa 에 놓는다.

## 순서
1. `D:\sfa` 폴더를 만들고 `school_setup.bat`, `school_env.bat` 을 넣는다.
2. `school_setup.bat` 더블클릭. 처음 한 번 약 12GB를 받는다(파이썬·torch 약 4GB, 기본 모델 6.9GB, LoRA 0.5GB). HDD라 시간이 걸린다. 끊기면 다시 실행하면 이어 받는다.
3. 그림 생성: `D:\sfa\school_comfy.bat` → 브라우저에 http://127.0.0.1:8188 이 열림 → `D:\sfa\school_workflow.json` 을 화면에 끌어다 놓기 → 오른쪽 **Queue Prompt**. 결과는 `D:\sfa\ComfyUI\output`.
   - 작업 흐름: 기본 모델 → 이펙트 LoRA(4바퀴, 강도 1.0) → 긍정·부정 프롬프트 → 1344×768, 28단계, CFG 6, euler_ancestral.
   - LoRA 칸에서 2·4·6바퀴(`nkmr_fx_ilxl-000002/000004`, `nkmr_fx_ilxl`)를 고를 수 있다. 2차 LoRA는 결과가 나오면 `D:\sfa\ComfyUI\models\loras` 에 넣는다.
4. SFA 변환:
   - 이펙트 그림 → `school_to_sfa_fx.bat` 에 끌어다 놓기 → `<이름>_fx.sfa`(층 쌓기) + 비교 그림.
   - 선화 있는 그림 → `school_to_sfa_line.bat` → `<이름>_line.sfa`(선 객체) + 선화 지도 + 비교 그림.
   - 여러 파일을 한 번에 끌어다 놓아도 된다.

## 1050 Ti 설정 근거와 확인할 것
- 이 세대(Pascal)는 반정밀도(fp16) 계산이 매우 느리다. 그래서 `school_comfy.bat` 은 그림 모델을 **fp8로 보관하고 계산은 fp32**(`--fp8_e4m3fn-unet`), 저용량 모드(`--lowvram`)로 4GB에 맞춘다.
- 첫 실행에서 한 장 걸리는 시간을 재서 알려 달라(예상 수 분, 미측정). 그림이 깨지거나 흐리면 `school_comfy_nofp8.bat`(fp8 없이, 램 더 씀)으로 비교.
- 서버(Claude 환경)에서는 다른 GitHub 저장소 주소가 막혀 ComfyUI v0.3.10 주소를 직접 열어 보지 못했다. 받기에 실패하면 화면을 찍어 보낸다.
- 학교 네트워크가 Hugging Face·GitHub를 막으면 모델 받기가 실패한다. 그때도 화면을 찍어 보낸다.
- 사용자 그림체 LoRA(`LoCon_ILv1_gwangsa`)는 tucker·scalar 옵션이 있어 ComfyUI에서 완전히 맞게 읽히는지 미확인.

## 오류가 나면
창이 멈춘 화면을 찍어 보낸다. 설치는 다시 실행하면 된 단계는 건너뛴다.
