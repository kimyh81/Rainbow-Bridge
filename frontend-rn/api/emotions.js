import api from './axiosInstance';

export async function postEmotion({ pet_id, score, note, sleep_quality }) {
  // sleep_quality(1~5)는 선택값 — 미션 난이도 보정용(소람님 mission.py _apply_sleep)
  const res = await api.post('/api/v1/emotions', { pet_id, score, note, sleep_quality });
  return res.data;
}

export async function getEmotions(petId) {
  const res = await api.get(`/api/v1/emotions?pet_id=${petId}`);
  return res.data;
}
