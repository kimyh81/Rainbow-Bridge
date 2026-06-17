import { useRef, useState, useCallback, useEffect } from 'react';

/**
 * 영상 재생 중 화면 렌더 FPS를 측정하는 훅 (requestAnimationFrame 기반).
 *
 * 평가용 — "폰에서 끊김 없이 재생되는지(≥30fps 유지율)"의 근사 지표입니다.
 * ⚠️ expo-av가 네이티브 디코더의 실제 드랍 프레임을 JS로 주지 않아, 이 값은
 *    화면(UI 스레드) 렌더 성능 근사치입니다. 디코더 레벨 드랍과 100% 동일하진 않습니다.
 *
 * 사용:
 *   const { measuring, result, start, stop } = useRenderFps();
 *   // 영상 재생 중 start() → 잠시 후 stop() → result 확인
 *
 * result: { fps_avg, fps_ge30_ratio, fps_min } | null  (소람님 평가 JSON 형식)
 */
export function useRenderFps() {
  const [measuring, setMeasuring] = useState(false);
  const [result, setResult] = useState(null);
  const rafRef = useRef(null);
  const frames = useRef(0);
  const lastSec = useRef(0);
  const samples = useRef([]); // 초당 FPS 샘플

  const now = () => (global.performance?.now ? global.performance.now() : Date.now());

  const loop = useCallback((t) => {
    frames.current += 1;
    const elapsed = t - lastSec.current;
    if (elapsed >= 1000) {
      samples.current.push((frames.current * 1000) / elapsed);
      frames.current = 0;
      lastSec.current = t;
    }
    rafRef.current = requestAnimationFrame(loop);
  }, []);

  const start = useCallback(() => {
    samples.current = [];
    frames.current = 0;
    lastSec.current = now();
    setResult(null);
    setMeasuring(true);
    rafRef.current = requestAnimationFrame(loop);
  }, [loop]);

  const stop = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = null;
    setMeasuring(false);
    const s = samples.current;
    if (s.length === 0) {
      setResult(null);
      return null;
    }
    const avg = s.reduce((a, b) => a + b, 0) / s.length;
    const min = Math.min(...s);
    const ge30 = s.filter((f) => f >= 30).length / s.length;
    const r = {
      fps_avg: Math.round(avg * 10) / 10,
      fps_ge30_ratio: Math.round(ge30 * 100) / 100,
      fps_min: Math.round(min),
    };
    setResult(r);
    return r;
  }, []);

  // 언마운트 시 루프 정리
  useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current); }, []);

  return { measuring, result, start, stop };
}
