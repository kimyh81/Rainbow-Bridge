import api from './axiosInstance';

/**
 * 기념일(D+30·D+100) 케어 메시지를 가져옵니다.
 * - days_since 생략 시: 백엔드가 오늘 날짜(반려동물 period) 기준으로 자동 확인.
 *   기념일이 아니면 백엔드가 404를 반환하므로, 호출부에서 catch해 null 처리하세요.
 * - days_since 지정 시: 강제 생성 (데모·시연용).
 *
 * 응답: { message, days_since, milestone_label, source,
 *         crisis_message?, risk_level?, support_message?, welfare_resources? }
 */
export async function getAnniversaryCare({ pet_id, days_since } = {}) {
  const q = days_since != null ? `?days_since=${days_since}` : '';
  const res = await api.get(`/api/v1/care/pets/${pet_id}/anniversary${q}`);
  return res.data;
}
