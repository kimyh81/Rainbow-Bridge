import { useState, useEffect, useRef } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Audio } from 'expo-av';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Card from '@/components/Card';
import Button from '@/components/Button';
import LoadingSpinner from '@/components/LoadingSpinner';
import { generateTts } from '@/api/tts';
import { logPlay } from '@/api/playLogs';
import { COLORS } from '@/constants/colors';
import { eulreul } from '@/utils/josa';
import { fetchRecoveryGate } from '@/utils/recovery';

const TONES = [
  { value: 'female', label: '여자 목소리', emoji: '🌸' },
  { value: 'male', label: '남자 목소리', emoji: '🌿' },
  { value: 'narration', label: '나레이션', emoji: '☁️' },
];

const API_BASE =
  process.env.EXPO_PUBLIC_API_URL ||
  'https://rainbow-bridge.duckdns.org';

export default function TtsScreen() {
  const router = useRouter();
  const [gateStatus, setGateStatus] = useState('checking'); // checking | locked | teaser | open
  const [recoveryScore, setRecoveryScore] = useState(0);
  const [selectedTone, setSelectedTone] = useState('female');
  const [audioUrl, setAudioUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [error, setError] = useState(null);
  const [petName, setPetName] = useState('소중한 친구');
  const [messageText, setMessageText] = useState(null);
  const soundRef = useRef(null);

  useEffect(() => {
    Audio.setAudioModeAsync({ playsInSilentModeIOS: true });
    AsyncStorage.getItem('pet_name').then((v) => v && setPetName(v));
    AsyncStorage.getItem('message_content').then((v) => v && setMessageText(v));
    initGate();
    return () => { soundRef.current?.unloadAsync(); };
  }, []);

  async function initGate() {
    const petId = await AsyncStorage.getItem('pet_id');
    const { gateStatus: gs, score } = await fetchRecoveryGate(petId);
    setRecoveryScore(score);
    setGateStatus(gs);
  }

  async function handleGenerate() {
    if (!messageText) return;
    await soundRef.current?.stopAsync();
    await soundRef.current?.unloadAsync();
    soundRef.current = null;
    setAudioUrl(null);
    setPlaying(false);
    setLoading(true);
    setError(null);
    try {
      const petId = await AsyncStorage.getItem('pet_id');
      const petSpecies = await AsyncStorage.getItem('pet_species');
      const res = await generateTts({ pet_id: petId, text: messageText, tone: selectedTone, species: petSpecies || '강아지' });
      if (!res.audio_url) throw new Error('audio_url 없음');
      const url = res.audio_url.startsWith('http')
        ? res.audio_url
        : `${API_BASE}${res.audio_url}`;
      setAudioUrl(url);
      await AsyncStorage.setItem('tts_done', '1');
    } catch (e) {
      console.error('[TTS] 생성 실패:', e);
      setError('음성 생성에 실패했어요. 잠시 후 다시 시도해주세요.');
    } finally {
      setLoading(false);
    }
  }

  async function handlePlayPause() {
    if (!audioUrl) return;
    if (soundRef.current) {
      if (playing) {
        await soundRef.current.pauseAsync();
        setPlaying(false);
      } else {
        await soundRef.current.playAsync();
        setPlaying(true);
      }
    } else {
      try {
        const { sound } = await Audio.Sound.createAsync(
          { uri: audioUrl },
          { shouldPlay: true }
        );
        soundRef.current = sound;
        setPlaying(true);
        sound.setOnPlaybackStatusUpdate((status) => {
          if (status.didJustFinish) setPlaying(false);
        });
        const petId = await AsyncStorage.getItem('pet_id');
        if (petId) logPlay({ pet_id: petId }).catch(() => {});
      } catch (e) {
        console.error('[TTS] 재생 실패:', e, 'url:', audioUrl);
        setError('음성 재생에 실패했어요. 다시 생성해보세요.');
      }
    }
  }

  // ── 게이트 분기 ──
  if (gateStatus === 'checking') {
    return (
      <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
        <SafeAreaView style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
          <LoadingSpinner message="회복 상태를 확인하고 있어요..." />
        </SafeAreaView>
      </LinearGradient>
    );
  }

  if (gateStatus === 'locked' || gateStatus === 'teaser') {
    const pct = Math.min(100, (recoveryScore / 80) * 100);
    const filled = Math.round(pct / 10);
    const bar = '█'.repeat(filled) + '░'.repeat(10 - filled);
    return (
      <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
        <SafeAreaView style={styles.safe}>
          <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: 'center', padding: 24 }}>
            <View style={ttsGate.card}>
              <Text style={ttsGate.icon}>{gateStatus === 'locked' ? '🔇' : '🔒'}</Text>
              <Text style={ttsGate.title}>
                {gateStatus === 'locked'
                  ? '아직 목소리를 들을 준비가 안 됐어요'
                  : `${petName}의 목소리가 기다리고 있어요`}
              </Text>
              <Text style={ttsGate.desc}>
                {gateStatus === 'locked'
                  ? `이별 직후에 ${petName}의 목소리를 듣는 건\n감정 회복을 더 어렵게 할 수 있어요.\n먼저 감정 체크인으로 마음을 돌봐요.`
                  : `회복도가 80점이 되면\n${petName}의 목소리로 편지를 들을 수 있어요.`}
              </Text>
              {gateStatus === 'teaser' && (
                <View style={ttsGate.progressWrap}>
                  <Text style={ttsGate.bar}>{bar}</Text>
                  <Text style={ttsGate.scoreText}>
                    {recoveryScore > 0 ? `${recoveryScore}점 / 80점` : '체크인을 시작해보세요'}
                  </Text>
                </View>
              )}
              <TouchableOpacity
                style={ttsGate.btn}
                onPress={() => router.replace('/(app)/emotion')}
                activeOpacity={0.85}
              >
                <Text style={ttsGate.btnText}>💭 감정 체크인 하러 가기</Text>
              </TouchableOpacity>
              <Text style={ttsGate.footnote}>천천히 괜찮아요 🐾</Text>
            </View>
          </ScrollView>
        </SafeAreaView>
      </LinearGradient>
    );
  }

  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>음성으로 듣기</Text>
        <Text style={styles.subtitle}>{petName}{eulreul(petName)} 위한 추모 메시지를 들어보세요.</Text>

        {/* 톤 선택 */}
        <Card style={styles.toneCard}>
          <Text style={styles.sectionLabel}>음성 톤 선택</Text>
          <View style={styles.toneRow}>
            {TONES.map((t) => (
              <TouchableOpacity
                key={t.value}
                onPress={() => { setSelectedTone(t.value); setAudioUrl(null); }}
                style={[styles.toneBtn, selectedTone === t.value && styles.toneBtnSelected]}
                activeOpacity={0.8}
              >
                <Text style={styles.toneEmoji}>{t.emoji}</Text>
                <Text style={[styles.toneLabel, selectedTone === t.value && styles.toneLabelSelected]}>
                  {t.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </Card>

        {/* 오디오 플레이어 */}
        {audioUrl ? (
          <Card style={styles.playerCard}>
            <TouchableOpacity
              onPress={handlePlayPause}
              style={styles.playBtn}
              activeOpacity={0.85}
            >
              <Text style={styles.playIcon}>{playing ? '⏸' : '▶'}</Text>
            </TouchableOpacity>
            <View style={styles.playerInfo}>
              <Text style={styles.playerTitle}>추모 메시지 낭독</Text>
              <Text style={styles.playerTone}>
                {TONES.find((t) => t.value === selectedTone)?.label} 톤
              </Text>
            </View>
          </Card>
        ) : null}

        {/* message_content 없을 때 — 추모 메시지 화면으로 안내 */}
        {!messageText ? (
          <View style={styles.noMessageBox}>
            <Text style={styles.noMessageText}>
              📭  아직 추모 메시지가 없어요.{'\n'}먼저 추모 메시지를 받아보세요.
            </Text>
            <Button
              variant="primary"
              onPress={() => router.replace('/(app)/message')}
              style={styles.goMessageBtn}
            >
              ✉️  추모 메시지 화면으로 가기
            </Button>
          </View>
        ) : (
          loading ? (
            <LoadingSpinner message="음성을 생성하고 있어요..." />
          ) : (
            <Button
              onPress={handleGenerate}
              variant="primary"
              style={styles.btn}
            >
              {audioUrl ? '다시 생성하기' : '낭독 시작'}
            </Button>
          )
        )}

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Button
          variant={audioUrl ? 'primary' : 'ghost'}
          onPress={() => router.push('/(app)/mission')}
          style={styles.nextBtn}
        >
          다음 — 오늘의 미션
        </Button>
      </ScrollView>
    </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  scroll: { paddingHorizontal: 24, paddingVertical: 36 },
  title: { fontSize: 22, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center', marginBottom: 6 },
  subtitle: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginBottom: 28 },
  toneCard: { marginBottom: 16 },
  sectionLabel: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary, marginBottom: 12 },
  toneRow: { flexDirection: 'row', gap: 8 },
  toneBtn: {
    flex: 1, alignItems: 'center', paddingVertical: 12,
    borderRadius: 12, borderWidth: 1.5, borderColor: COLORS.divider,
    backgroundColor: COLORS.white, gap: 4,
  },
  toneBtnSelected: { borderColor: COLORS.selectedBorder, backgroundColor: '#FBF1F3' },
  toneEmoji: { fontSize: 20 },
  toneLabel: { fontSize: 12, color: COLORS.textSecondary, fontWeight: '500' },
  toneLabelSelected: { color: COLORS.selectedText, fontWeight: '700' },
  playerCard: { flexDirection: 'row', alignItems: 'center', gap: 14, marginBottom: 20 },
  playBtn: {
    width: 48, height: 48, borderRadius: 24,
    backgroundColor: COLORS.cta, alignItems: 'center', justifyContent: 'center',
    shadowColor: COLORS.cta, shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.3, shadowRadius: 6, elevation: 4,
  },
  playIcon: { fontSize: 18, color: '#fff', fontWeight: '700' },
  playerInfo: { flex: 1 },
  playerTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  playerTone: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  btn: { marginBottom: 12 },
  nextBtn: { marginTop: 4 },
  noMessageBox: {
    alignItems: 'center',
    gap: 14,
    backgroundColor: 'rgba(196,168,216,0.10)',
    borderWidth: 1,
    borderColor: 'rgba(196,168,216,0.30)',
    borderRadius: 16,
    padding: 20,
    marginBottom: 8,
  },
  noMessageText: {
    fontSize: 14,
    color: COLORS.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  goMessageBtn: { width: '100%' },
  error: { color: COLORS.danger, fontSize: 13, textAlign: 'center', marginBottom: 12 },
});

const ttsGate = StyleSheet.create({
  card: {
    backgroundColor: '#FFFFFF',
    borderRadius: 24, padding: 28,
    borderWidth: 1.5, borderColor: '#E5DCF0',
    alignItems: 'center', gap: 12,
    shadowColor: '#8A7D9E', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.10, shadowRadius: 12, elevation: 3,
  },
  icon: { fontSize: 48 },
  title: { fontSize: 17, fontWeight: '800', color: '#5B4E75', textAlign: 'center' },
  desc: { fontSize: 13, color: '#8A7D9E', textAlign: 'center', lineHeight: 21 },
  progressWrap: { alignItems: 'center', gap: 6, marginTop: 4 },
  bar: { fontSize: 16, color: '#C4A8D8', letterSpacing: 2, fontWeight: '700' },
  scoreText: { fontSize: 20, fontWeight: '800', color: '#5B4E75' },
  btn: {
    width: '100%', backgroundColor: '#C4A8D8',
    borderRadius: 14, paddingVertical: 14, alignItems: 'center',
    marginTop: 8,
    shadowColor: '#C4A8D8', shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.28, shadowRadius: 6, elevation: 3,
  },
  btnText: { fontSize: 14, fontWeight: '700', color: '#fff' },
  footnote: { fontSize: 12, color: '#B0A0C0' },
});
