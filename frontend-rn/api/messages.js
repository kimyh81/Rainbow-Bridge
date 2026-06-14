import api from './axiosInstance';

export async function generateMessage({ pet_id, request_first_person = false }) {
  const res = await api.post('/api/v1/messages', { pet_id, request_first_person });
  return res.data;
}

export async function getLatestMessage(petId) {
  const res = await api.get(`/api/v1/messages/${petId}/latest`);
  return res.data;
}
