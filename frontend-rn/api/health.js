import api from './axiosInstance';

/**
 * 삼성헬스(→Health Connect)에서 읽은 걸음·수면 원본을 백엔드로 전송합니다.
 * 가공하지 않고 readRecords 응답을 그대로 넘깁니다 — 파싱은 백엔드가 합니다.
 * (axiosInstance 인터셉터가 Authorization: Bearer 토큰을 자동으로 붙여줍니다)
 *
 * @param {object} params
 * @param {string} params.pet_id          반려동물 id
 * @param {object} [params.steps_result]  readRecords('Steps') 응답 그대로
 * @param {object} [params.sleep_result]  readRecords('SleepSession') 응답 그대로
 * @returns {Promise<{ok: boolean, date: string, steps: number, sleep_hours: number}>}
 */
export async function syncHealth({ pet_id, steps_result, sleep_result }) {
  const body = { pet_id };
  // 둘 중 하나만 있어도 OK — 없는 건 생략
  if (steps_result) body.steps_result = steps_result;
  if (sleep_result) body.sleep_result = sleep_result;
  const res = await api.post('/api/v1/health/sync', body);
  return res.data;
}
