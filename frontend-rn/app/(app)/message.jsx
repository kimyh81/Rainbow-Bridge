import { useState, useEffect, useRef, useCallback } from 'react';
import { View, Text, StyleSheet, Animated, Easing, ScrollView, TouchableOpacity, Modal } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { Video, ResizeMode } from 'expo-av';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { Audio } from 'expo-av';
import SafetyModal from '@/components/SafetyModal';
import Button from '@/components/Button';
import LoadingSpinner from '@/components/LoadingSpinner';
import { generateMessage, getLatestMessage } from '@/api/messages';
import { recordPlay } from '@/api/media';
import { generateTts } from '@/api/tts';
import { COLORS } from '@/constants/colors';
import { fetchRecoveryGate } from '@/utils/recovery';
import { doLogout } from './_layout';

const BGM_3RD = require('../../assets/audio/bgm_3rd.mp3');
const BGM_1ST = require('../../assets/audio/bgm_1st.mp3');

const API_BASE =
  process.env.EXPO_PUBLIC_API_URL ||
  'https://rainbow-bridge.duckdns.org';

const LINE_DELAY = 1500;
const LINE_DURATION = 900;
const BGM_FADE_DURATION = 500;
const TTS_START_OFFSET = LINE_DURATION / 2;

function makeFallbackMessage(petName) {
  const name = petName || '소중한 친구';
  return {
    id: 'local',
    content: `${name}와 함께했던 모든 순간들이 얼마나 소중했는지 기억해요.\n그 따뜻한 기억들은 언제나 마음속에 살아있을 거예요.\n지금 많이 힘드시겠지만, 조금씩 천천히 나아가도 괜찮아요.\n${name}는 보호자와 함께한 시간을 언제나 행복하게 기억할 거예요.`,
    tone: 'warm',
    first_person: false,
    source: 'local',
    risk_level: 0,
    content_unlocked: false,
    allow_first_person: false,
  };
}

function speciesIcon(species) {
  if (species === '강아지') return '🐾';
  if (species === '고양이') return '🐱';
  return '🌸';
}

function splitLines(content) {
  if (!content) return [];
  return content
    .split(/(?<=[.!?])\s+|\n/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function ResourceCard({ resource }) {
  return (
    <View style={styles.resourceCard}>
      <View style={styles.rcHeader}>
        <Text style={styles.rcName}>{resource.name}</Text>
        {resource.category && <Text style={styles.rcCat}>{resource.category}</Text>}
      </View>
      {resource.contact && <Text style={styles.rcContact}>{resource.contact}</Text>}
      {resource.description && <Text style={styles.rcDesc}>{resource.description}</Text>}
    </View>
  );
}

function MsgStar({ top, left, size, duration, delay }) {
  const opacity = useRef(new Animated.Value(0.1)).current;
  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: duration / 2, delay, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.1, duration: duration / 2, useNativeDriver: true }),
      ])
    ).start();
  }, []);
  return (
    <Animated.View style={{
      position: 'absolute', top, left,
      width: size, height: size, borderRadius: size / 2,
      backgroundColor: '#fff', opacity, zIndex: 1,
    }} />
  );
}

// ─────────────────────────────────────────────────────────────
// 회복 게이트 — 잠김 화면 (score 0~49)
// 근거: 이별 직후 강한 자극은 집착·현실 부정으로 이어질 수 있음
//       (Continuing Bonds 연구, RECOVERY_GATE.md)
// ─────────────────────────────────────────────────────────────
function GateLockedScreen({ petName, onGoCheckin, onGoMission, onGoHome, onLogout }) {
  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={gate.gradient}>
      <SafeAreaView style={gate.safe}>
        <View style={gate.navRow}>
          <TouchableOpacity onPress={onGoHome} style={gate.navBtn} activeOpacity={0.7}>
            <Text style={gate.navHome}>홈</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={onLogout} style={gate.navBtn} activeOpacity={0.7}>
            <Text style={gate.navLogout}>로그아웃</Text>
          </TouchableOpacity>
        </View>
        <ScrollView contentContainerStyle={gate.scroll}>
          <View style={gate.card}>
            <Text style={gate.lockIcon}>🌙</Text>
            <Text style={gate.title}>아직 마음을 추스르는 중이에요</Text>
            <Text style={gate.desc}>
              이별 직후에는 강한 추모 편지가{'\n'}감정 회복을 더 어렵게 할 수 있어요.{'\n\n'}
              매일 감정을 기록하고 작은 미션으로{'\n'}하루하루 회복해나가면,{'\n'}
              {petName || '아이'}의 편지를 받을 수 있어요.
            </Text>
            <View style={gate.divider} />
            <TouchableOpacity style={gate.primaryBtn} onPress={onGoCheckin} activeOpacity={0.85}>
              <Text style={gate.primaryBtnText}>💭 감정 체크인 하러 가기</Text>
            </TouchableOpacity>
            <TouchableOpacity style={gate.secondaryBtn} onPress={onGoMission} activeOpacity={0.85}>
              <Text style={gate.secondaryBtnText}>🌱 오늘의 미션 보기</Text>
            </TouchableOpacity>
            <Text style={gate.footnote}>
              AI가 생성하는 편지는 충분히 마음을 추스른 뒤에 받는 게{'\n'}훨씬 더 따뜻하게 느껴질 거예요.
            </Text>
          </View>
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

// ─────────────────────────────────────────────────────────────
// 회복 게이트 — 찌라시 카드 (score 50~79)
// 근거: RECOVERY_GATE.md — "회복하면 OO이의 편지를 받을 수 있다"는
//       찌라시가 회복 동기를 만든다
// ─────────────────────────────────────────────────────────────
function GateTeaserScreen({ petName, score, onGoCheckin, onGoHome, onLogout }) {
  const pct = Math.max(0, Math.min(99, ((score - 50) / 30) * 100));
  const filledBlocks = Math.floor(pct / 10);
  const bar = '█'.repeat(filledBlocks) + '░'.repeat(10 - filledBlocks);

  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={gate.gradient}>
      <SafeAreaView style={gate.safe}>
        <View style={gate.navRow}>
          <TouchableOpacity onPress={onGoHome} style={gate.navBtn} activeOpacity={0.7}>
            <Text style={gate.navHome}>홈</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={onLogout} style={gate.navBtn} activeOpacity={0.7}>
            <Text style={gate.navLogout}>로그아웃</Text>
          </TouchableOpacity>
        </View>
        <ScrollView contentContainerStyle={gate.scroll}>
          <View style={gate.teaserCard}>
            <Text style={gate.teaserLock}>🔒</Text>
            <Text style={gate.teaserTitle}>{petName || '아이'}가 남긴 편지</Text>
            <Text style={gate.teaserDesc}>
              {petName || '아이'}와의 추억을 바탕으로 쓴{'\n'}특별한 편지가 기다리고 있어요.
            </Text>

            <View style={gate.progressWrap}>
              <Text style={gate.progressBar}>{bar}</Text>
              <Text style={gate.progressLabel}>
                {score > 0 ? `${score}점` : '체크인을 시작해보세요'}
              </Text>
              <Text style={gate.progressHint}>80점이 되면 열립니다</Text>
            </View>

            <Text style={gate.teaserEncourage}>천천히 괜찮아요 🐾</Text>

            <View style={gate.divider} />
            <TouchableOpacity style={gate.primaryBtn} onPress={onGoCheckin} activeOpacity={0.85}>
              <Text style={gate.primaryBtnText}>💭 감정 체크인으로 회복도 높이기</Text>
            </TouchableOpacity>
            <Text style={gate.footnote}>
              감정 체크인과 오늘의 미션을 꾸준히 하면 회복도가 올라가요.
            </Text>
          </View>
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

export default function MessageScreen() {
  const router = useRouter();
  // gate: 'checking' | 'locked' | 'teaser' | 'open'
  const [gateStatus, setGateStatus] = useState('checking');
  const [recoveryScore, setRecoveryScore] = useState(0);
  const [phase, setPhase] = useState('loading'); // loading | envelope | letter
  const [message, setMessage] = useState(null);
  const [error, setError] = useState('');
  const [petName, setPetName] = useState('소중한 친구');
  const [petSpecies, setPetSpecies] = useState('');
  const [petVideoUrl, setPetVideoUrl] = useState(null);
  const [petVideoAssetId, setPetVideoAssetId] = useState(null);
  const [videoModalVisible, setVideoModalVisible] = useState(false);
  const [safetyOpen, setSafetyOpen] = useState(false);
  const [lines, setLines] = useState([]);
  const [visibleCount, setVisibleCount] = useState(0);
  const [done, setDone] = useState(false);
  const [welfareExpanded, setWelfareExpanded] = useState(false);
  const [envelopeOpened, setEnvelopeOpened] = useState(false);

  // 봉투 애니메이션
  const flapAnim = useRef(new Animated.Value(0)).current;
  const envelopeAnim = useRef(new Animated.Value(1)).current;
  // 편지지 애니메이션
  const paperOpacity = useRef(new Animated.Value(0)).current;
  const paperTranslate = useRef(new Animated.Value(40)).current;
  // 편지 본문 블록 슬라이드업 (한 줄씩 → 전체 블록)
  const contentSlide = useRef(new Animated.Value(36)).current;
  const contentFade = useRef(new Animated.Value(0)).current;

  const bgmRef = useRef(null);
  const ttsRef = useRef(null);
  const timersRef = useRef([]);
  const parsedRef = useRef([]);

  // ✉️ 흔들림 애니메이션
  const paperFloat = useRef(new Animated.Value(0)).current;
  const stars = useRef(
    Array.from({ length: 16 }).map(() => ({
      top: Math.random() * 600 + 20,
      left: Math.random() * 340 + 10,
      size: Math.random() * 1.8 + 1.2,
      duration: (Math.random() * 2 + 2.2) * 1000,
      delay: Math.random() * 3000,
    }))
  ).current;

  // ✉️ 편지 단계에서만 흔들림 루프
  useEffect(() => {
    if (phase !== 'letter') return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(paperFloat, { toValue: 1, duration: 1300, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
        Animated.timing(paperFloat, { toValue: 0, duration: 1300, easing: Easing.inOut(Easing.sin), useNativeDriver: true }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [phase]);

  useEffect(() => {
    AsyncStorage.getItem('pet_name').then((v) => v && setPetName(v));
    AsyncStorage.getItem('pet_species').then((v) => v && setPetSpecies(v));
    AsyncStorage.getItem('pet_video_url').then((v) => v && setPetVideoUrl(v));
    AsyncStorage.getItem('pet_video_asset_id').then((v) => v && setPetVideoAssetId(v));
    initGate();
    return () => cleanup();
  }, []);

  // 화면 벗어날 때 BGM/TTS 완전 해제
  useFocusEffect(
    useCallback(() => {
      return () => {
        if (bgmRef.current) {
          bgmRef.current.stopAsync().catch(() => {});
          bgmRef.current.unloadAsync().catch(() => {});
          bgmRef.current = null;
        }
        if (ttsRef.current) {
          ttsRef.current.stopAsync().catch(() => {});
          ttsRef.current.unloadAsync().catch(() => {});
          ttsRef.current = null;
        }
        timersRef.current.forEach(clearTimeout);
        timersRef.current = [];
      };
    }, [])
  );

  async function initGate() {
    const petId = await AsyncStorage.getItem('pet_id');
    const { gateStatus: gs, score, riskGated } = await fetchRecoveryGate(petId);
    setRecoveryScore(score);
    setGateStatus(gs);
    if (gs === 'open') {
      if (riskGated) setSafetyOpen(true);
      loadMessage();
    }
  }

  function cleanup() {
    timersRef.current.forEach(clearTimeout);
    if (bgmRef.current) bgmRef.current.unloadAsync();
    if (ttsRef.current) ttsRef.current.unloadAsync();
  }

  async function saveMessage(data) {
    setMessage(data);
    await AsyncStorage.setItem('message_id', data.id || data._id || '');
    // unavailable 상태(LLM 실패 안내문)는 TTS에 저장하지 않음
    if (data.source !== 'unavailable') {
      await AsyncStorage.setItem('message_content', data.content || '');
      await AsyncStorage.setItem('message_tone', data.tone || 'warm');
    }
    if (data.risk_level >= 2 || data.source === 'safety') setSafetyOpen(true);
  }

  async function loadMessage() {
    const petId = await AsyncStorage.getItem('pet_id');
    const petNameLocal = await AsyncStorage.getItem('pet_name') || '소중한 친구';
    try {
      const existing = await getLatestMessage(petId);
      if (!existing || existing.source === 'unavailable') throw new Error('unavailable');
      await saveMessage(existing);
    } catch {
      try {
        const data = await generateMessage({ pet_id: petId });
        if (!data || data.source === 'unavailable') throw new Error('unavailable');
        await saveMessage(data);
      } catch {
        await saveMessage(makeFallbackMessage(petNameLocal));
      }
    }
  }

  // 메시지 도착 → 봉투 단계로
  useEffect(() => {
    if (!message) return;
    if (message.source === 'unavailable') { setPhase('letter'); return; }
    const parsed = splitLines(message.content);
    parsedRef.current = parsed;
    setLines(parsed);
    setPhase('envelope');
  }, [message]);

  // 봉투 열기 버튼
  function openEnvelope() {
    if (envelopeOpened) return;
    setEnvelopeOpened(true);
    Animated.sequence([
      Animated.parallel([
        Animated.timing(flapAnim, {
          toValue: 1, duration: 450, easing: Easing.inOut(Easing.ease), useNativeDriver: true,
        }),
      ]),
      Animated.parallel([
        Animated.timing(envelopeAnim, {
          toValue: 0, duration: 350, easing: Easing.in(Easing.ease), useNativeDriver: true,
        }),
        Animated.timing(paperOpacity, {
          toValue: 1, duration: 500, easing: Easing.out(Easing.cubic), useNativeDriver: true,
        }),
        Animated.timing(paperTranslate, {
          toValue: 0, duration: 500, easing: Easing.out(Easing.cubic), useNativeDriver: true,
        }),
      ]),
    ]).start(() => {
      setPhase('letter');
      startSequence(parsedRef.current, message.first_person, message);
    });
  }

  async function regenerate() {
    cleanup();
    setDone(false);
    setEnvelopeOpened(false);
    setVisibleCount(0);
    setLines([]);
    setWelfareExpanded(false);
    setMessage(null);
    setError('');
    flapAnim.setValue(0);
    envelopeAnim.setValue(1);
    paperOpacity.setValue(0);
    paperTranslate.setValue(40);
    contentSlide.setValue(36);
    contentFade.setValue(0);
    setPhase('loading');
    try {
      const petId = await AsyncStorage.getItem('pet_id');
      const petNameLocal = await AsyncStorage.getItem('pet_name') || '소중한 친구';
      try {
        const data = await generateMessage({ pet_id: petId });
        await saveMessage(data);
      } catch {
        await saveMessage(makeFallbackMessage(petNameLocal));
      }
    } catch {
      setError('메시지 생성에 실패했어요. 다시 시도해주세요.');
    }
  }

  async function handleWatchVideo() {
    if (petVideoAssetId) recordPlay(petVideoAssetId).catch(() => {});
    setVideoModalVisible(true);
  }

  async function requestFirstPerson() {
    cleanup();
    setDone(false);
    setEnvelopeOpened(false);
    setVisibleCount(0);
    setLines([]);
    setWelfareExpanded(false);
    setMessage(null);
    setError('');
    flapAnim.setValue(0);
    envelopeAnim.setValue(1);
    paperOpacity.setValue(0);
    paperTranslate.setValue(40);
    contentSlide.setValue(36);
    contentFade.setValue(0);
    setPhase('loading');
    try {
      const petId = await AsyncStorage.getItem('pet_id');
      const data = await generateMessage({ pet_id: petId, request_first_person: true });
      await saveMessage(data);
    } catch {
      setError('편지 생성에 실패했어요. 다시 시도해주세요.');
    }
  }

  async function startSequence(parsed, isFirstPerson, msgData) {
    await Audio.setAudioModeAsync({ playsInSilentModeIOS: true });

    // 전체 텍스트 블록 슬라이드업 (한 줄씩 대신)
    setVisibleCount(parsed.length);
    Animated.parallel([
      Animated.timing(contentSlide, { toValue: 0, duration: 600, useNativeDriver: true }),
      Animated.timing(contentFade, { toValue: 1, duration: 600, useNativeDriver: true }),
    ]).start();

    // BGM
    const bgmFile = isFirstPerson ? BGM_1ST : BGM_3RD;
    if (bgmFile) {
      try {
        const { sound } = await Audio.Sound.createAsync(bgmFile, { isLooping: true, volume: 0 });
        bgmRef.current = sound;
        await sound.playAsync();
        let vol = 0;
        const fade = setInterval(async () => {
          vol = Math.min(0.7, vol + 0.05);
          await sound.setVolumeAsync(vol);
          if (vol >= 0.7) clearInterval(fade);
        }, BGM_FADE_DURATION / 20);
      } catch {}
    }

    // TTS — 콘텐츠 등장 직후 재생
    try {
      const petId = await AsyncStorage.getItem('pet_id');
      const petGender = await AsyncStorage.getItem('pet_gender');
      if (!petId || !msgData.content) throw new Error('pet_id 또는 content 없음');
      const tone = msgData.first_person
        ? (petGender === '남아' ? 'male' : 'female')
        : 'narration';
      const ttsData = await generateTts({ pet_id: petId, text: msgData.content, tone });
      if (!ttsData?.audio_url) throw new Error('audio_url 없음');
      const audioUri = ttsData.audio_url.startsWith('http')
        ? ttsData.audio_url
        : `${API_BASE}${ttsData.audio_url}`;
      const { sound } = await Audio.Sound.createAsync(
        { uri: audioUri },
        { volume: 1.0, shouldPlay: false },
      );
      ttsRef.current = sound;
      timersRef.current.push(setTimeout(() => {
        sound.playAsync().catch((e) => console.warn('[TTS] playAsync 실패:', e));
      }, 800));
    } catch (e) {
      console.warn('[TTS] 생성 실패:', e?.message ?? e);
    }

    timersRef.current.push(setTimeout(() => setDone(true), 1200));
  }

  const isFirst = message?.first_person;
  const icon = speciesIcon(petSpecies);
  const featuredResources = message?.welfare_resources?.filter(r => r.featured) ?? [];
  const extraResources = message?.welfare_resources?.filter(r => !r.featured) ?? [];

  // 봉투 flap: translateY 0→-120, opacity 1→0
  const flapTranslate = flapAnim.interpolate({ inputRange: [0, 1], outputRange: [0, -120] });
  const flapOpacity = flapAnim.interpolate({ inputRange: [0, 0.8, 1], outputRange: [1, 0.3, 0] });

  // ── 게이트 화면 렌더링 ──
  if (gateStatus === 'checking') {
    return (
      <LinearGradient key="light" colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.safe}>
        <SafeAreaView style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <LoadingSpinner message="회복 상태를 확인하고 있어요..." />
        </SafeAreaView>
      </LinearGradient>
    );
  }
  if (gateStatus === 'locked') {
    return (
      <GateLockedScreen
        petName={petName}
        onGoCheckin={() => router.replace('/(app)/emotion')}
        onGoMission={() => router.replace('/(app)/mission')}
        onGoHome={() => router.replace('/(app)/home')}
        onLogout={doLogout}
      />
    );
  }
  if (gateStatus === 'teaser') {
    return (
      <GateTeaserScreen
        petName={petName}
        score={recoveryScore}
        onGoCheckin={() => router.replace('/(app)/emotion')}
        onGoHome={() => router.replace('/(app)/home')}
        onLogout={doLogout}
      />
    );
  }

  return (
    <LinearGradient key="dark" colors={['#2a3445', '#2c2742', '#241e32']} style={styles.safeGradient}>
      <SafeAreaView style={styles.safeInner}>
        {/* 헤더 — 홈·로그아웃 */}
        <View style={styles.msgHeader}>
          <TouchableOpacity onPress={() => router.replace('/(app)/home')} style={styles.msgHeaderBtn} activeOpacity={0.7}>
            <Text style={styles.msgHeaderHome}>홈</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={doLogout} style={styles.msgHeaderBtn} activeOpacity={0.7}>
            <Text style={styles.msgHeaderLogout}>로그아웃</Text>
          </TouchableOpacity>
        </View>

        <SafetyModal isOpen={safetyOpen} onClose={() => setSafetyOpen(false)} />

        {/* 배경 별 반짝임 */}
        {stars.map((st, i) => <MsgStar key={i} {...st} />)}

        {/* 영상 풀스크린 모달 */}
        <Modal
          visible={videoModalVisible}
          transparent
          animationType="fade"
          onRequestClose={() => setVideoModalVisible(false)}
        >
          <View style={styles.videoModal}>
            <TouchableOpacity
              style={styles.videoModalClose}
              onPress={() => setVideoModalVisible(false)}
              activeOpacity={0.8}
            >
              <Text style={styles.videoModalCloseText}>✕</Text>
            </TouchableOpacity>
            {petVideoUrl ? (
              <Video
                source={{ uri: petVideoUrl }}
                style={styles.fullscreenVideo}
                resizeMode={ResizeMode.CONTAIN}
                shouldPlay
                useNativeControls
                isLooping
              />
            ) : (
              <Text style={styles.videoModalNoUrl}>영상을 불러올 수 없어요.</Text>
            )}
          </View>
        </Modal>

        {/* 로딩 */}
        {phase === 'loading' && !error && (
          <View style={styles.center}>
            <LoadingSpinner message={`${petName}의 편지를 가져오고 있어요...`} />
          </View>
        )}

        {/* 에러 */}
        {error && (
          <View style={styles.center}>
            <Text style={styles.error}>{error}</Text>
            <Button variant="primary" onPress={regenerate}>다시 시도</Button>
          </View>
        )}

        {/* unavailable */}
        {phase === 'letter' && message?.source === 'unavailable' && (
          <View style={styles.center}>
            <Text style={styles.unavailable}>{message.content}</Text>
            <Button variant="ghost" onPress={regenerate} style={{ marginTop: 16 }}>다시 시도</Button>
          </View>
        )}

        {/* ── 봉투 단계 ── */}
        {phase === 'envelope' && (
          <View style={styles.center}>
            <Animated.View style={[
              styles.envelope, isFirst && styles.envelopeFirst,
              { opacity: envelopeAnim, transform: [{ scaleY: envelopeAnim }] },
            ]}>
              {/* Flap */}
              <Animated.View style={[
                styles.envelopeFlap, isFirst && styles.envelopeFlapFirst,
                { transform: [{ translateY: flapTranslate }], opacity: flapOpacity },
              ]}>
                <View style={[styles.foldLineLeft, isFirst && styles.foldLineFirst]} />
                <View style={[styles.foldLineRight, isFirst && styles.foldLineFirst]} />
              </Animated.View>

              {/* 봉투 바디 */}
              <View style={styles.envelopeBody}>
                <Text style={styles.envelopeSeal}>✉️</Text>
                <Text style={[styles.envelopeName, isFirst && styles.envelopeNameFirst]}>
                  · {petName} ·
                </Text>
                <Text style={[styles.envelopeSubtitle, isFirst && styles.envelopeSubtitleFirst]}>
                  편지가 도착했어요
                </Text>
              </View>
            </Animated.View>

            {/* 열기 버튼 */}
            <Animated.View style={{ opacity: envelopeAnim, marginTop: 28 }}>
              <TouchableOpacity
                style={[styles.openBtn, isFirst && styles.openBtnFirst]}
                onPress={openEnvelope}
              >
                <Text style={styles.openBtnText}>✉️  열어볼까요?</Text>
              </TouchableOpacity>
            </Animated.View>
          </View>
        )}

        {/* ── 편지지 단계 ── */}
        {(phase === 'envelope' || phase === 'letter') && message && message.source !== 'unavailable' && (
          <Animated.View
            pointerEvents={phase === 'envelope' ? 'none' : 'auto'}
            style={[
              styles.paperWrap,
              { opacity: paperOpacity, transform: [{ translateY: paperTranslate }] },
              phase === 'envelope' && styles.paperHidden,
            ]}>
            <ScrollView
              style={styles.paperScroll}
              contentContainerStyle={styles.paperScrollContent}
              showsVerticalScrollIndicator={false}
              scrollEnabled={phase === 'letter'}
            >
              {/* 편지 단계 — ✉️ 제목 헤더 */}
              {phase === 'letter' && (
                <View style={styles.letterTitleWrap}>
                  <Animated.Text style={[styles.letterIcon, { transform: [
                    { translateY: paperFloat.interpolate({ inputRange: [0, 1], outputRange: [-3, 3] }) },
                    { rotate: paperFloat.interpolate({ inputRange: [0, 1], outputRange: ['-3deg', '3deg'] }) },
                  ]}]}>✉️</Animated.Text>
                  <Text style={styles.letterTitle}>{petName}가 편지를 남겼어요</Text>
                  <Text style={styles.letterSub}>{petName}가 하고 싶었던 말을 전해드릴게요.</Text>
                </View>
              )}

              <View style={[styles.paper, isFirst && styles.paperFirst]}>
                {/* 편지지 상단 */}
                <View style={styles.paperHeader}>
                  {isFirst && <Text style={styles.speciesIcon}>{icon}</Text>}
                  <Text style={[styles.petLabel, isFirst && styles.petLabelFirst]}>· {petName} ·</Text>
                  <View style={[styles.headerLine, isFirst && styles.headerLineFirst]} />
                </View>

                {/* LivePortrait 영상 */}
                {petVideoUrl && (
                  <View style={[styles.videoWrap, isFirst && styles.videoWrapFirst]}>
                    <Video source={{ uri: petVideoUrl }} style={styles.video}
                      resizeMode={ResizeMode.COVER} isLooping shouldPlay isMuted />
                  </View>
                )}

                {/* 편지 본문 — 전체 블록 슬라이드업 */}
                <Animated.View style={{ opacity: contentFade, transform: [{ translateY: contentSlide }] }}>
                  <View style={styles.bodyContent}>
                    {lines.map((line, i) =>
                      i < visibleCount ? (
                        <Text key={i} style={[styles.line, isFirst && styles.lineFirst]}>
                          {line}
                        </Text>
                      ) : null
                    )}
                  </View>
                </Animated.View>

                {/* 편지 끝 AI 안내 */}
                <View style={styles.aiFooter}>
                  <View style={styles.aiFooterLine} />
                  <Text style={styles.aiFooterText}>AI가 생성한 메시지입니다</Text>
                </View>
              </View>

              {/* 윤리 고지 — 편지 카드 밖, 버튼 위에 분리 배치 */}
              {done && (
                <View style={styles.disclaimerWrap}>
                  <Text style={styles.disclaimer}>
                    {isFirst
                      ? 'AI가 보호자가 전해준 추억을 바탕으로 재해석한 꿈 속 작별 인사입니다.'
                      : 'AI가 생성한 추모 글입니다. 반려동물이 직접 한 말이 아닙니다.'}
                  </Text>
                </View>
              )}

              {done && (
                <Button variant="ghost" onPress={regenerate} style={styles.regenBtn}>
                  🌸 다시 재생
                </Button>
              )}

              {/* 영상 보기 버튼 — pet_video_url이 있을 때만 표시 */}
              {done && petVideoUrl && (
                <TouchableOpacity
                  style={styles.watchVideoBtn}
                  onPress={handleWatchVideo}
                  activeOpacity={0.85}
                >
                  <Text style={styles.watchVideoBtnText}>🎬  영상 보기</Text>
                </TouchableOpacity>
              )}

              {/* 회복 게이트 — content_unlocked / allow_first_person */}
              {done && (
                <View style={styles.gateSection}>
                  {message?.content_unlocked === true && (
                    <TouchableOpacity
                      style={styles.gateBtnWrap}
                      onPress={() => router.push('/(app)/mission')}
                      activeOpacity={0.8}
                    >
                      <LinearGradient
                        colors={['rgba(123,200,164,0.22)', 'rgba(184,208,232,0.18)']}
                        start={{ x: 0, y: 0 }}
                        end={{ x: 1, y: 0 }}
                        style={styles.gateBtn}
                      >
                        <Text style={styles.gateBtnEmoji}>🌱</Text>
                        <View style={styles.gateBtnBody}>
                          <Text style={styles.gateBtnText}>오늘의 회복 미션 보기</Text>
                          <Text style={styles.gateBtnSub}>일상 복귀를 위한 작은 활동들이에요</Text>
                        </View>
                        <Text style={styles.gateBtnArrow}>›</Text>
                      </LinearGradient>
                    </TouchableOpacity>
                  )}
                  {message?.allow_first_person && !isFirst && (
                    <TouchableOpacity
                      style={styles.firstPersonBtnWrap}
                      onPress={requestFirstPerson}
                      activeOpacity={0.8}
                    >
                      <LinearGradient
                        colors={['rgba(253,243,220,0.22)', 'rgba(232,201,122,0.14)']}
                        start={{ x: 0, y: 0 }}
                        end={{ x: 1, y: 0 }}
                        style={styles.gateBtn}
                      >
                        <Text style={styles.gateBtnEmoji}>✉️</Text>
                        <View style={styles.gateBtnBody}>
                          <Text style={[styles.gateBtnText, { color: '#E8C97A' }]}>아이가 직접 쓴 편지 받기</Text>
                          <Text style={styles.gateBtnSub}>AI가 추억을 바탕으로 재해석한 편지예요</Text>
                        </View>
                      </LinearGradient>
                    </TouchableOpacity>
                  )}
                </View>
              )}

              {/* 상담 자원 섹션 — risk_level 1/2 이상이고 welfare_resources 있을 때 */}
              {done && (featuredResources.length > 0 || extraResources.length > 0) && (
                <View style={styles.welfareSection}>
                  {message.support_message && (
                    <View style={styles.supportBanner}>
                      <Text style={styles.supportText}>{message.support_message}</Text>
                    </View>
                  )}
                  {message.crisis_message && (
                    <View style={styles.crisisBanner}>
                      <Text style={styles.crisisText}>{message.crisis_message}</Text>
                    </View>
                  )}
                  <Text style={styles.welfareSectionTitle}>상담 자원 안내</Text>
                  {featuredResources.map((r, i) => <ResourceCard key={`f-${i}`} resource={r} />)}
                  {extraResources.length > 0 && (
                    <>
                      <TouchableOpacity
                        style={styles.expandToggle}
                        onPress={() => setWelfareExpanded(e => !e)}
                        activeOpacity={0.7}
                      >
                        <Text style={styles.expandToggleText}>
                          {welfareExpanded ? '접기 ▲' : `더 보기 (${extraResources.length}곳) ▼`}
                        </Text>
                      </TouchableOpacity>
                      {welfareExpanded && extraResources.map((r, i) => <ResourceCard key={`nf-${i}`} resource={r} />)}
                    </>
                  )}
                </View>
              )}
            </ScrollView>
          </Animated.View>
        )}
      </SafeAreaView>
    </LinearGradient>
  );
}

const ENVELOPE_W = '88%';
const FLAP_H = 80;

const styles = StyleSheet.create({
  safe: { flex: 1 },
  safeGradient: { flex: 1 },
  safeInner: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },

  // ── 봉투 ──
  envelope: {
    width: ENVELOPE_W,
    backgroundColor: '#FFF8EE',
    borderRadius: 12,
    overflow: 'hidden',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.4,
    shadowRadius: 20,
    elevation: 14,
  },
  envelopeFirst: { backgroundColor: '#FDF3DC', borderWidth: 1, borderColor: '#E8C97A' },
  envelopeFlap: {
    height: FLAP_H,
    backgroundColor: '#F5EDDE',
    justifyContent: 'center',
    alignItems: 'center',
    overflow: 'hidden',
  },
  envelopeFlapFirst: { backgroundColor: '#F5E6B8' },
  foldLineLeft: {
    position: 'absolute', top: 0, left: 0, width: 120, height: 1,
    backgroundColor: '#D4C0A0',
    transform: [{ rotate: '35deg' }, { translateX: -10 }, { translateY: 28 }],
  },
  foldLineRight: {
    position: 'absolute', top: 0, right: 0, width: 120, height: 1,
    backgroundColor: '#D4C0A0',
    transform: [{ rotate: '-35deg' }, { translateX: 10 }, { translateY: 28 }],
  },
  foldLineFirst: { backgroundColor: '#C9A84C' },
  envelopeBody: {
    paddingVertical: 28, paddingHorizontal: 24,
    alignItems: 'center', gap: 8,
    borderTopWidth: 1, borderTopColor: '#E8DCC8',
  },
  envelopeSeal: { fontSize: 40, marginBottom: 4 },
  envelopeName: { fontSize: 14, color: '#A08060', letterSpacing: 3, fontWeight: '500' },
  envelopeNameFirst: { color: '#9A6B20', letterSpacing: 4 },
  envelopeSubtitle: { fontSize: 13, color: '#B8A080' },
  envelopeSubtitleFirst: { color: '#C09040' },
  openBtn: {
    paddingVertical: 14, paddingHorizontal: 32, borderRadius: 28,
    backgroundColor: 'rgba(255,248,238,0.15)',
    borderWidth: 1, borderColor: 'rgba(255,248,238,0.4)',
  },
  openBtnFirst: { borderColor: 'rgba(232,201,122,0.5)', backgroundColor: 'rgba(253,243,220,0.15)' },
  openBtnText: { fontSize: 16, color: '#EDE8F5', letterSpacing: 1 },

  // ── 편지지 ──
  paperHidden: { position: 'absolute', pointerEvents: 'none' },
  paperWrap: {
    flex: 1,
    paddingHorizontal: 20,
    paddingVertical: 32,
  },
  paperScroll: { flex: 1 },
  paperScrollContent: { flexGrow: 1, gap: 20, paddingBottom: 32, paddingTop: 8 },
  paper: {
    width: '100%',
    backgroundColor: '#FFF8EE',
    borderRadius: 16,
    paddingHorizontal: 28,
    paddingTop: 28,
    paddingBottom: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.35,
    shadowRadius: 20,
    elevation: 12,
    overflow: 'hidden',
  },
  paperFirst: { backgroundColor: '#FDF3DC', borderWidth: 1, borderColor: '#E8C97A' },
  paperHeader: { alignItems: 'center', marginBottom: 20, gap: 10 },
  speciesIcon: { fontSize: 28, marginBottom: 4 },
  petLabel: { fontSize: 13, color: '#A08060', letterSpacing: 3, fontWeight: '500' },
  petLabelFirst: { color: '#9A6B20', letterSpacing: 4 },
  headerLine: { width: 48, height: 1, backgroundColor: '#D4C0A0' },
  headerLineFirst: { backgroundColor: '#C9A84C', width: 64 },
  videoWrap: {
    alignSelf: 'center', width: 120, height: 120, borderRadius: 60,
    overflow: 'hidden', marginBottom: 20, borderWidth: 3, borderColor: '#D4C0A0',
    shadowColor: '#000', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.2, shadowRadius: 8, elevation: 6,
  },
  videoWrapFirst: { borderColor: '#C9A84C', width: 140, height: 140, borderRadius: 70 },
  video: { width: '100%', height: '100%' },
  bodyContent: { gap: 16, paddingBottom: 4 },
  line: { fontSize: 16, color: '#3A2A1A', lineHeight: 27, textAlign: 'center', fontWeight: '400' },
  lineFirst: { color: '#4A2E0A', fontStyle: 'italic', fontWeight: '400' },
  footerLine: { width: 48, height: 1, backgroundColor: '#D4C0A0' },
  disclaimerWrap: { alignItems: 'center', paddingHorizontal: 16 },
  disclaimer: { fontSize: 11, color: 'rgba(255,255,255,0.50)', textAlign: 'center', lineHeight: 17 },
  regenBtn: { alignSelf: 'center' },

  // ── 상담 자원 ──
  welfareSection: { gap: 10 },
  welfareSectionTitle: {
    fontSize: 11, fontWeight: '600', color: 'rgba(255,255,255,0.4)',
    textAlign: 'center', letterSpacing: 1.5, marginBottom: 2,
  },
  supportBanner: {
    backgroundColor: 'rgba(180,150,220,0.15)',
    borderWidth: 1, borderColor: 'rgba(196,168,216,0.35)',
    borderRadius: 12, padding: 14,
  },
  supportText: { fontSize: 13, color: '#C4A8D8', lineHeight: 20, textAlign: 'center' },
  crisisBanner: {
    backgroundColor: 'rgba(240,140,60,0.15)',
    borderWidth: 1, borderColor: 'rgba(232,140,60,0.4)',
    borderRadius: 12, padding: 14,
  },
  crisisText: { fontSize: 13, color: '#E8A060', lineHeight: 20, textAlign: 'center', fontWeight: '600' },
  resourceCard: {
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
    borderRadius: 12, padding: 14, gap: 5,
  },
  rcHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  rcName: { fontSize: 13, fontWeight: '700', color: 'rgba(255,255,255,0.85)', flex: 1 },
  rcCat: {
    fontSize: 11, color: 'rgba(255,255,255,0.38)',
    backgroundColor: 'rgba(255,255,255,0.07)',
    paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8,
  },
  rcContact: { fontSize: 14, color: '#C4A8D8', fontWeight: '600' },
  rcDesc: { fontSize: 12, color: 'rgba(255,255,255,0.45)', lineHeight: 18 },
  expandToggle: {
    alignSelf: 'center', paddingHorizontal: 18, paddingVertical: 8, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.07)',
    borderWidth: 1, borderColor: 'rgba(255,255,255,0.10)',
  },
  expandToggleText: { fontSize: 13, color: 'rgba(255,255,255,0.45)' },

  // ── 회복 게이트 ──
  gateSection: { gap: 10, marginTop: 4 },
  gateBtnWrap: {
    borderRadius: 16,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(123,200,164,0.30)',
  },
  firstPersonBtnWrap: {
    borderRadius: 16,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(232,201,122,0.35)',
  },
  gateBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 14,
    paddingHorizontal: 16,
    gap: 12,
  },
  gateBtnEmoji: { fontSize: 22 },
  gateBtnBody: { flex: 1 },
  gateBtnText: { fontSize: 13, fontWeight: '700', color: '#7BC8A4' },
  gateBtnSub: { fontSize: 11, color: 'rgba(255,255,255,0.40)', marginTop: 2 },
  gateBtnArrow: { fontSize: 18, color: 'rgba(255,255,255,0.35)' },

  // ── 커스텀 헤더 (headerShown: false 화면) ──
  msgHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255,255,255,0.08)',
  },
  msgHeaderBtn: { paddingHorizontal: 8, paddingVertical: 4 },
  msgHeaderHome: { fontSize: 14, fontWeight: '700', color: '#C4A8D8' },
  msgHeaderLogout: { fontSize: 14, fontWeight: '700', color: '#E57373' },

  // ── 영상 보기 버튼 ──
  watchVideoBtn: {
    alignSelf: 'center',
    paddingVertical: 12,
    paddingHorizontal: 28,
    borderRadius: 20,
    backgroundColor: 'rgba(184,144,255,0.15)',
    borderWidth: 1,
    borderColor: 'rgba(196,168,216,0.45)',
    marginTop: 4,
  },
  watchVideoBtnText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#C4A8D8',
    letterSpacing: 0.5,
  },

  // ── 영상 풀스크린 모달 ──
  videoModal: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.96)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  videoModalClose: {
    position: 'absolute',
    top: 52,
    right: 20,
    zIndex: 10,
    padding: 10,
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderRadius: 20,
  },
  videoModalCloseText: {
    fontSize: 20,
    color: '#fff',
    fontWeight: '700',
  },
  fullscreenVideo: {
    width: '100%',
    aspectRatio: 9 / 16,
  },
  videoModalNoUrl: {
    fontSize: 14,
    color: 'rgba(255,255,255,0.5)',
  },

  error: { color: COLORS.danger, fontSize: 14, textAlign: 'center', marginBottom: 16 },
  unavailable: { fontSize: 15, color: COLORS.textSecondary, textAlign: 'center', marginBottom: 20, lineHeight: 24 },
  aiFooter: { alignItems: 'center', marginTop: 20, gap: 8 },
  aiFooterLine: { width: 48, height: 1, backgroundColor: '#D4C0A0' },
  aiFooterText: { fontSize: 11, color: '#B0987A', textAlign: 'center', letterSpacing: 0.5 },

  // ── 편지 단계 제목 헤더 ──
  letterTitleWrap: { alignItems: 'center', paddingBottom: 4, gap: 4 },
  letterIcon: { fontSize: 40, textAlign: 'center', marginBottom: 6 },
  letterTitle: { fontSize: 21, fontWeight: '700', color: '#fff', textAlign: 'center' },
  letterSub: { fontSize: 12.5, color: 'rgba(255,255,255,0.55)', textAlign: 'center', lineHeight: 20 },
});

// ── 게이트 화면 전용 스타일 ──
const gate = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  scroll: { flexGrow: 1, justifyContent: 'center', padding: 24 },
  navRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#E5DCF0',
  },
  navBtn: { paddingHorizontal: 8, paddingVertical: 4 },
  navHome: { fontSize: 14, fontWeight: '700', color: '#C4A8D8' },
  navLogout: { fontSize: 14, fontWeight: '700', color: '#E57373' },

  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 24, padding: 28,
    borderWidth: 1.5, borderColor: '#E5DCF0',
    alignItems: 'center',
    shadowColor: '#8A7D9E', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.10, shadowRadius: 12, elevation: 3,
  },
  lockIcon: { fontSize: 48, marginBottom: 12 },
  title: { fontSize: 18, fontWeight: '800', color: '#5B4E75', textAlign: 'center', marginBottom: 12 },
  desc: { fontSize: 14, color: '#8A7D9E', textAlign: 'center', lineHeight: 22, marginBottom: 16 },
  divider: { width: '100%', height: 1, backgroundColor: '#E5DCF0', marginVertical: 16 },

  primaryBtn: {
    width: '100%', backgroundColor: '#C4A8D8',
    borderRadius: 14, paddingVertical: 14,
    alignItems: 'center', marginBottom: 10,
    shadowColor: '#C4A8D8', shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.30, shadowRadius: 6, elevation: 3,
  },
  primaryBtnText: { fontSize: 14, fontWeight: '700', color: '#fff' },
  secondaryBtn: {
    width: '100%', borderRadius: 14, paddingVertical: 13,
    alignItems: 'center', borderWidth: 1.5, borderColor: '#C4A8D8',
    backgroundColor: 'transparent',
  },
  secondaryBtnText: { fontSize: 14, fontWeight: '600', color: '#8A7D9E' },
  footnote: { fontSize: 11, color: '#B0A0C0', textAlign: 'center', lineHeight: 18, marginTop: 14 },

  // teaser 카드
  teaserCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 24, padding: 28,
    borderWidth: 1.5, borderColor: '#D4C4E8',
    alignItems: 'center',
    shadowColor: '#8A7D9E', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.10, shadowRadius: 12, elevation: 3,
  },
  teaserLock: { fontSize: 44, marginBottom: 10 },
  teaserTitle: { fontSize: 18, fontWeight: '800', color: '#5B4E75', marginBottom: 10 },
  teaserDesc: { fontSize: 14, color: '#8A7D9E', textAlign: 'center', lineHeight: 22, marginBottom: 20 },
  progressWrap: { width: '100%', alignItems: 'center', gap: 6, marginBottom: 16 },
  progressBar: { fontSize: 16, color: '#C4A8D8', letterSpacing: 2, fontWeight: '700' },
  progressLabel: { fontSize: 22, fontWeight: '800', color: '#5B4E75' },
  progressHint: { fontSize: 12, color: '#A89FBC' },
  teaserEncourage: { fontSize: 15, color: '#8A7D9E', marginBottom: 8 },
});
