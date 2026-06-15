import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../api/axiosInstance';

const CACHE_KEY = 'recovery_cache';
const CACHE_TTL = 3600000; // 1시간

function scoreToGate(score, riskGated) {
  if (riskGated) return 'locked'; // risk_level 2+ → 점수 무관하게 잠김
  if (score >= 80) return 'open';
  if (score >= 45) return 'teaser';
  return 'locked';
}

/**
 * 회복 게이트 상태를 확인합니다.
 * 반환: { gateStatus: 'locked' | 'teaser' | 'open', score: number, riskGated: boolean }
 *
 * Continuing Bonds 연구에 근거:
 *  - locked  (0~44점):  이별 직후 취약기 — 강한 자극 차단
 *  - teaser (45~79점):  회복 중 — 찌라시 카드로 동기 부여
 *  - open   (80점~  ):  충분한 회복 — 추모 편지·TTS 언락
 *
 * 백엔드 불가 시 캐시 → farewell_date 기반 시간 게이트 순서로 폴백합니다.
 */
export async function fetchRecoveryGate(petId) {
  // 1순위: API 직접 조회
  if (petId) {
    try {
      const res = await api.get(`/api/v1/emotions/recovery/${petId}`);
      const data = res.data;
      await AsyncStorage.setItem(CACHE_KEY, JSON.stringify({ ...data, ts: Date.now() }));
      // 백엔드가 gate_status 3단계 필드를 내려주면 그대로 사용, 없으면 score로 계산
      const riskGated = (data.latest_risk_level ?? 0) >= 2;
      return {
        gateStatus: data.gate_status ?? scoreToGate(data.recovery_pct ?? 0, riskGated),
        score: data.recovery_pct ?? 0,
        riskGated,
      };
    } catch {}
  }

  // 2순위: 1시간 이내 캐시
  try {
    const raw = await AsyncStorage.getItem(CACHE_KEY);
    if (raw) {
      const cached = JSON.parse(raw);
      if (cached.ts && Date.now() - cached.ts < CACHE_TTL) {
        const riskGated = (cached.latest_risk_level ?? 0) >= 2;
        return {
          gateStatus: scoreToGate(cached.recovery_pct ?? 0, riskGated),
          score: cached.recovery_pct ?? 0,
          riskGated,
        };
      }
    }
  } catch {}

  // 3순위: farewell_date 기반 시간 게이트
  try {
    const fd = await AsyncStorage.getItem('pet_farewell_date');
    if (fd) {
      const days = Math.floor((Date.now() - new Date(fd).getTime()) / 86400000);
      if (days <= 2) {
        return { gateStatus: 'locked', score: 20, riskGated: false };
      }
      if (days <= 13) {
        // 3~13일: 점수를 선형으로 증가 (30~69점 범위)
        const score = Math.min(79, 30 + (days - 3) * 4);
        return { gateStatus: 'teaser', score, riskGated: false };
      }
      return { gateStatus: 'open', score: 82, riskGated: false };
    }
  } catch {}

  // 4순위: 정보 없음 → 찌라시(teaser) 노출로 체크인 유도
  return { gateStatus: 'teaser', score: 0, riskGated: false };
}
