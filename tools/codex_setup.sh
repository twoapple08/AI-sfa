#!/bin/bash
# Codex 클라우드 환경 설정 스크립트 (AI-sfa).
# Codex 환경 설정의 'Setup script' 칸에 이 파일 내용을 붙이거나: bash tools/codex_setup.sh
# 필요한 비밀값(Secrets): RCLONE_GDRIVE_AUTH_B64 — Claude 클라우드 환경 변수와 같은 값(rclone authorize가 준 base64 묶음).
# 비밀값은 설정 스크립트 단계에서만 읽힐 수 있으므로, 여기서 rclone 설정 파일로 옮겨 둔다. 값은 출력하지 않는다.
# 선택 환경 변수: CODEX_TASK=T01 이면 그 작업 자료를 미리 받는다(작업 중 인터넷이 꺼져 있어도 쓸 수 있게).
set -euo pipefail

# 1. rclone
if ! command -v rclone >/dev/null; then
  curl -sSLo /tmp/rc.zip https://downloads.rclone.org/rclone-current-linux-amd64.zip
  unzip -qo /tmp/rc.zip -d /tmp && cp /tmp/rclone-*/rclone /usr/local/bin/ && rm -rf /tmp/rc.zip /tmp/rclone-*
fi

# 2. Drive 인증(읽기 + 앱이 만든 파일 쓰기)
python3 - <<'EOF'
import base64, json, os, pathlib
raw = os.environ.get("RCLONE_GDRIVE_AUTH_B64", "").strip()
if not raw:
    raise SystemExit("RCLONE_GDRIVE_AUTH_B64 비밀값을 읽지 못했다(이름 철자, 이 환경에 연결했는지, 도메인 제한 방식인지 확인)")
d = json.loads(base64.b64decode(raw + "=" * (-len(raw) % 4)))
text = ["[gdrive]", "type = drive", "scope = drive.readonly,drive.file"]
for k in ("client_id", "client_secret"):
    if d.get(k):
        text.append(f"{k} = {d[k]}")
text.append("token = " + d["token"])
text = "\n".join(text) + "\n"
# 설정 스크립트와 작업이 다른 사용자(root / agent)로 돌 수 있어 두 곳 모두에 쓰고 주인을 맞춘다
import pwd
homes = {str(pathlib.Path.home()), "/home/agent", "/root"}
for h in homes:
    if not os.path.isdir(h):
        continue
    p = pathlib.Path(h) / ".config/rclone"
    p.mkdir(parents=True, exist_ok=True)
    (p / "rclone.conf").write_text(text)
    os.chmod(p / "rclone.conf", 0o600)
    try:
        u = pwd.getpwnam(pathlib.Path(h).name) if h != "/root" else pwd.getpwnam("root")
        for q in (pathlib.Path(h) / ".config", p, p / "rclone.conf"):
            os.chown(q, u.pw_uid, u.pw_gid)
    except (KeyError, PermissionError):
        pass
    print("rclone 설정:", p / "rclone.conf")
print("rclone 설정 완료")
EOF
rclone lsd gdrive:AI-sfa 2>/dev/null | head -3

# 3. 파이썬 도구(분석 스크립트 실행용, GPU 없음)
pip install -q opencv-python-headless numpy scipy scikit-image pillow onnxruntime huggingface_hub

# 4. 작업 자료 미리 받기
DATA=/tmp/ai-sfa-data  # 설정(root)과 작업(agent) 사용자가 달라도 읽을 수 있는 곳
mkdir -p "$DATA"
case "${CODEX_TASK:-}" in
  T01) rclone copy "gdrive:AI-sfa/00_목록/_GPT용_시트/T01_포즈추적" "$DATA/T01" ;;
  *) echo "CODEX_TASK 없음: 자료는 작업 중 rclone으로 받는다(인터넷 허용 필요)" ;;
esac
chmod -R a+rX "$DATA"; ls "$DATA" || true
echo "설정 끝. 자료: $DATA"
