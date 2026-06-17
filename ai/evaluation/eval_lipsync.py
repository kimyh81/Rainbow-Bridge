"""립싱크 평가 — 동물/캐릭터 아바타용 (상관계수 + 지연)

SyncNet은 사람 얼굴로 학습된 모델이라 동물/캐릭터에 적용 불가.
입 벌림 픽셀 면적 ↔ 오디오 RMS 상관계수로 측정.

사전 설치:
    pip install opencv-python librosa numpy scipy

사용법:
    python ai/evaluation/eval_lipsync.py --video path/to/voiced.mp4
    python ai/evaluation/eval_lipsync.py --video voiced.mp4 --fps 25 --out result.json

판정 기준 (팀 내부):
    상관계수 ≥ 0.70  AND  |lag| ≤ 100ms → PASS
"""

from __future__ import annotations

import argparse
import json


def extract_mouth_openness(video_path: str, fps: float) -> list[float]:
    """프레임별 입 영역(하단 1/3) 밝기 분산으로 입 벌림 추정."""
    try:
        import cv2
    except ImportError:
        raise SystemExit("opencv-python 미설치 — pip install opencv-python")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"영상 파일을 열 수 없습니다: {video_path}")

    mouth_values: list[float] = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        # 얼굴 하단 1/3 영역을 입 대리 지표로 사용
        mouth_region = gray[int(h * 2 / 3):, int(w * 0.25): int(w * 0.75)]
        mouth_values.append(float(mouth_region.std()))
    cap.release()
    return mouth_values


def extract_audio_rms(video_path: str, n_frames: int) -> list[float]:
    """영상에서 오디오 추출 후 RMS 포락선을 프레임 수에 맞게 리샘플."""
    try:
        import librosa
        import numpy as np
    except ImportError:
        raise SystemExit("librosa 미설치 — pip install librosa")

    import numpy as np

    y, sr = librosa.load(video_path, sr=None, mono=True)
    rms = librosa.feature.rms(y=y)[0]
    # 프레임 수에 맞춰 선형 보간
    resampled = np.interp(
        np.linspace(0, len(rms) - 1, n_frames),
        np.arange(len(rms)),
        rms,
    )
    return resampled.tolist()


def compute_sync(
    mouth: list[float],
    audio: list[float],
    fps: float,
) -> dict:
    import numpy as np
    from scipy.signal import correlate

    m = np.array(mouth)
    a = np.array(audio)

    # 정규화
    m_n = (m - m.mean()) / (m.std() + 1e-8)
    a_n = (a - a.mean()) / (a.std() + 1e-8)

    corr_val = float(np.corrcoef(m_n, a_n)[0, 1])

    # 지연 계산
    full_corr = correlate(m_n, a_n, mode="full")
    lag_frames = int(full_corr.argmax()) - (len(m_n) - 1)
    lag_ms = lag_frames / fps * 1000

    passed = corr_val >= 0.70 and abs(lag_ms) <= 100

    return {
        "correlation": round(corr_val, 4),   # 1에 가까울수록 좋음 (목표 ≥0.7)
        "lag_ms": round(lag_ms, 1),           # 0에 가까울수록 좋음 (목표 ±100ms)
        "n_frames": len(mouth),
        "fps": fps,
        "pass": passed,
    }


def run(video_path: str, fps: float | None = None) -> dict:
    try:
        import cv2
    except ImportError:
        raise SystemExit("opencv-python 미설치 — pip install opencv-python")

    cap = cv2.VideoCapture(video_path)
    detected_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    cap.release()

    fps = fps or detected_fps
    print(f"[LipSync] 영상: {video_path}  FPS: {fps}")

    print("  입 벌림 추출 중...")
    mouth = extract_mouth_openness(video_path, fps)
    print(f"  프레임 수: {len(mouth)}")

    print("  오디오 RMS 추출 중...")
    audio = extract_audio_rms(video_path, len(mouth))

    result = compute_sync(mouth, audio, fps)
    result["video"] = video_path

    status = "✅ PASS" if result["pass"] else "❌ FAIL"
    print(f"\n{status}")
    print(f"  상관계수 : {result['correlation']:.4f}  (목표 ≥ 0.70)")
    print(f"  지연     : {result['lag_ms']:+.1f} ms  (목표 ±100ms)")
    print(f"  프레임   : {result['n_frames']}장 @ {result['fps']}fps")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="립싱크 평가 (캐릭터/동물 아바타용)")
    parser.add_argument("--video", required=True, help="평가할 MP4 영상 경로")
    parser.add_argument("--fps", type=float, default=None, help="FPS 직접 지정 (없으면 영상에서 자동)")
    parser.add_argument("--out", help="결과 저장 JSON 경로 (선택)")
    args = parser.parse_args()

    result = run(args.video, args.fps)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장: {args.out}")


if __name__ == "__main__":
    main()
