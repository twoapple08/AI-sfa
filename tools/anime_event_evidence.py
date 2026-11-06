"""원본 애니의 연속 장과 시간 근거를 CPU에서 수집한다. 의미 판정/학습은 하지 않는다.

이미지는 저장소 밖 private-dir에만 저장한다. 출력 evidence.json도 먼저 비공개에 쓴다.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import cv2
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def extract(source, destination, start, end):
    if destination == ROOT or ROOT in destination.parents:
        raise ValueError('원본 장은 저장소 밖 비공개 경로에 저장해야 한다')
    if start < 0 or end < start:
        raise ValueError('장 범위가 잘못됐다')
    probe = json.loads(subprocess.run([
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,avg_frame_rate,r_frame_rate,nb_frames:frame=best_effort_timestamp_time',
        '-of', 'json', str(source)], check=True, capture_output=True, text=True).stdout)
    pts = [float(f['best_effort_timestamp_time']) for f in probe['frames']]
    if end >= len(pts):
        raise ValueError('영상 끝을 넘은 범위다')
    destination.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(source))
    cap.set(cv2.CAP_PROP_POS_FRAMES, start)
    cols, w, h = 4, 424, 240
    sheet = Image.new('RGB', (w * cols, (h + 24) * ((end - start + cols) // cols)), '#eeeeee')
    draw = ImageDraw.Draw(sheet)
    frames = []
    previous = None
    try:
        for i, index in enumerate(range(start, end + 1)):
            ok, frame = cap.read()
            if not ok or int(cap.get(cv2.CAP_PROP_POS_FRAMES)) != index + 1:
                raise ValueError(f'{index}장 디코딩 위치 확인 실패')
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            image.save(destination / f'f{index:04d}.png')
            x, y = (i % cols) * w, (i // cols) * (h + 24)
            # 424×240은 이 판본848×480의 검토용 축소다. 원본 PNG도 함께 저장한다.
            sheet.paste(image.resize((w, h)), (x, y))
            draw.text((x + 4, y + h + 3), f'index {index} | PTS {pts[index]:.6f}s', fill='black')
            pixel_hash = hashlib.sha256(frame.tobytes()).hexdigest()
            frames.append(dict(index=index, pts_seconds=pts[index],
                               duration_to_next_pts=pts[index + 1] - pts[index] if index + 1 < len(pts) else None,
                               decoded_pixel_sha256=pixel_hash,
                               identical_whole_frame_to_previous=previous == pixel_hash if previous else None))
            previous = pixel_hash
    finally:
        cap.release()
    sheet.save(destination / 'contact.jpg')
    result = dict(schema='anime-event-evidence/1', source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  source_md5=hashlib.md5(source.read_bytes()).hexdigest(), stream=probe['streams'][0],
                  decoded_total_frames=len(pts), range_inclusive=[start, end], index_base=0,
                  frames=frames, training_ready=False, semantic_labels_automatic=False,
                  limits=['전체 장 일치 여부는 신체 그림의 유지/카메라 움직임 판정이 아니다.',
                          '연출·부위·가림·스미어 의미는 별도 원본 판독이 필요하다.'])
    (destination / 'evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--private-dir', required=True, type=Path)
    parser.add_argument('--start', required=True, type=int)
    parser.add_argument('--end', required=True, type=int)
    args = parser.parse_args()
    result = extract(args.source.resolve(), args.private_dir.resolve(), args.start, args.end)
    print(json.dumps({k: result[k] for k in ['source_md5', 'decoded_total_frames', 'range_inclusive']}, ensure_ascii=False))
