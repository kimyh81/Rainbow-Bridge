import api from './axiosInstance';

// 사진 업로드 → { asset_id } 반환. photos.jsx에서 사진 등록 시 사용.
export async function uploadMedia(formData) {
  const res = await api.post('/api/v1/media/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}

// 추모 영상 자동 생성 → DB에서 최적 사진 자동 선택 후 LivePortrait 실행
// { asset_id, message, selected_photo } 반환
export async function generateMedia(petId) {
  const res = await api.post(`/api/v1/media/generate/${petId}`);
  return res.data;
}

// 영상 생성 상태 조회 → { asset_id, status: processing|done|error, video_url }
export async function getMediaStatus(assetId) {
  const res = await api.get(`/api/v1/media/${assetId}`);
  return res.data;
}

// 영상 능동 시청(버튼 탭)만 play_count +1. 배경 자동재생은 카운트 안 함.
export async function recordPlay(assetId) {
  const res = await api.post(`/api/v1/media/${assetId}/play`);
  return res.data;
}

// 사진 삭제 — 서버 파일 + DB 문서 함께 제거
export async function deleteMedia(assetId) {
  await api.delete(`/api/v1/media/${assetId}`);
}
