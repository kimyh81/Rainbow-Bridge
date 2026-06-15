export const mockPet = {
  _id: 'pet_001',
  name: '콩이',
  species: '강아지',
  period: '2018-2026',
  memories: ['공원 산책', '간식 좋아함', '낮잠 자는 거 좋아함'],
  photo_url: null,
};

export const mockEmotion = {
  id: 'emo_001',
  pet_id: 'pet_001',
  score: 6,
  note: '오늘 콩이 생각이 많이 났어',
  risk_level: 0,
  created_at: '2026-06-04T00:00:00Z',
  crisis_message: null,
};

export const mockMessage = {
  _id: 'msg_001',
  pet_id: 'pet_001',
  content:
    '콩이는 당신과 함께한 모든 순간을 소중히 간직하고 있을 거예요. 공원 산책도, 함께한 낮잠도 모두 아름다운 기억입니다.',
  tone: '따뜻함',
};

// 난이도(difficulty)는 소람님 LLM이 회복 단계에 맞춰 내려줌 — gentle/small/active
// 아래는 L1(45~79점) 예시 구성: gentle×2 + small×1
export const mockMissions = [
  { id: 'mis_001', pet_id: 'pet_001', title: '집 앞 5분 산책', description: '집 근처를 5분만 천천히 걸어보세요.', category: '행동활성화', difficulty: 'gentle', rationale: '작은 활동이 가라앉은 기분을 끌어올려요', completed: false, skipped: false, created_at: '2026-06-04T00:00:00Z', completed_at: null },
  { id: 'mis_002', pet_id: 'pet_001', title: '콩이 사진 한 장 바라보기', description: '함께한 사진 한 장을 천천히 바라보세요.', category: '지속적 유대', difficulty: 'gentle', rationale: '기억을 이어가며 슬픔을 따뜻하게 바꿔요', completed: false, skipped: false, created_at: '2026-06-04T00:00:00Z', completed_at: null },
  { id: 'mis_003', pet_id: 'pet_001', title: '오늘 감정 한 줄', description: '지금 느끼는 감정을 한 줄로만 적어보세요.', category: '표현적 글쓰기', difficulty: 'small', rationale: '감정을 글로 꺼내면 마음이 가벼워져요', completed: false, skipped: false, created_at: '2026-06-04T00:00:00Z', completed_at: null },
];

export const mockTimeline = [
  { _id: 'tl_001', type: 'emotion', ref_id: 'emo_001', created_at: '2026-06-01' },
  { _id: 'tl_002', type: 'message', ref_id: 'msg_001', created_at: '2026-06-02' },
];

export const mockReport = {
  pet_id: 'pet_001',
  period: '2026-06',
  usage: { messages: 3, emotions: 5, missions: 2 },
  emotion_trend: [
    { created_at: '06-01', score: 6 },
    { created_at: '06-02', score: 4 },
    { created_at: '06-03', score: 7 },
    { created_at: '06-04', score: 5 },
    { created_at: '06-05', score: 8 },
  ],
  mission_completion_rate: 0.6,
  revisit: 5,
  sleep_trend: [
    { created_at: '06-01', hours: 6.5 },
    { created_at: '06-02', hours: 5.0 },
    { created_at: '06-03', hours: 7.0 },
    { created_at: '06-04', hours: 6.0 },
    { created_at: '06-05', hours: 7.5 },
  ],
};
