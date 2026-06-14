import api from './axiosInstance';

export async function generateTts({ pet_id, text, tone, species }) {
  if (!pet_id || !text) throw new Error('pet_id와 text는 필수입니다.');
  const res = await api.post('/api/v1/tts', {
    pet_id,
    text,
    tone: tone || 'narration',
    species: species || '강아지',
  });
  return res.data;
}
