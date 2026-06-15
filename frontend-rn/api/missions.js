import api from './axiosInstance';

export async function getMissions({ pet_id }) {
  const res = await api.get(`/api/v1/missions/${pet_id}`);
  return res.data;
}

export async function completeMission({ mission_id }) {
  const res = await api.patch(`/api/v1/missions/${mission_id}/complete`, { completed: true });
  return res.data;
}

// 미션 건너뛰기 — 세종님 백엔드가 같은 난이도 대체 미션을 1개 만들어 반환
// 응답: { skipped_mission, replacement } (replacement는 대체 미션 없으면 null)
export async function skipMission({ mission_id }) {
  const res = await api.patch(`/api/v1/missions/${mission_id}/skip`);
  return res.data;
}
