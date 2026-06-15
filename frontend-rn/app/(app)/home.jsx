import { useEffect, useState } from 'react';
import {
  View, Text, Pressable, StyleSheet, ScrollView,
  Modal, ActivityIndicator, TouchableOpacity,
} from 'react-native';
import { router } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { LinearGradient } from 'expo-linear-gradient';
import { fetchRecoveryGate } from '@/utils/recovery';
import { iga } from '@/utils/josa';

// ── 회복 여정 선물 로드맵 노드 ──────────────────────
function JourneyNode({ emoji, label, done }) {
  return (
    <View style={styles.journeyNode}>
      <View style={[styles.journeyCircle, done && styles.journeyCircleDone]}>
        <Text style={[styles.journeyEmoji, !done && styles.journeyEmojiDim]}>{emoji}</Text>
      </View>
      <Text numberOfLines={1} style={[styles.journeyLabel, done && styles.journeyLabelDone]}>{label}</Text>
    </View>
  );
}

// ── 회복 여정 선물 카드 (추모 편지 자리) ─────────────
function GiftJourneyCard({ gateStatus, hasVideo, hasLetter }) {
  const letterReady = gateStatus === 'teaser' || gateStatus === 'open';
  const firstPersonReady = gateStatus === 'open';
  const steps = [
    { emoji: '🎞️', label: 'GIF', done: hasVideo },
    { emoji: '✉️', label: '위로 편지', done: letterReady },
    { emoji: '🌠', label: '별에서 온 편지', done: firstPersonReady },
    { emoji: '📦', label: '패키지', done: hasVideo || hasLetter },
  ];

  return (
    <Pressable
      style={({ pressed }) => [styles.journeyCard, pressed && { opacity: 0.9 }]}
      onPress={() => router.push('/(app)/gift')}
    >
      <LinearGradient
        colors={['#EDFAF3', '#F0EAFA']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.journeyGrad}
      >
        <View style={styles.journeyHead}>
          <Text style={styles.journeyTitle}>🎁 회복 여정 선물</Text>
          <Text style={styles.journeySub}>천천히 걸으면 하나씩 도착해요</Text>
        </View>

        {/* 로드맵 레일 */}
        <View style={styles.journeyRail}>
          {steps.reduce((acc, s, i) => {
            if (i > 0) {
              acc.push(
                <View key={`c${i}`} style={[styles.journeyConn, s.done && styles.journeyConnDone]} />
              );
            }
            acc.push(<JourneyNode key={`n${i}`} {...s} />);
            return acc;
          }, [])}
        </View>

        <View style={styles.journeyBtn}>
          <Text style={styles.journeyBtnText}>자세히 보기 ›</Text>
        </View>
      </LinearGradient>
    </Pressable>
  );
}

// ── 큰 카드 (메인 기능) ──────────────────────────
function BigCard({ emoji, title, desc, route, gradient, badge, disabled }) {
  return (
    <Pressable
      style={({ pressed }) => [
        styles.bigCard,
        disabled && styles.bigCardDisabled,
        pressed && !disabled && { opacity: 0.82 },
      ]}
      onPress={() => !disabled && route && router.push(route)}
      disabled={!!disabled}
    >
      <LinearGradient
        colors={gradient || ['#F9F5FF', '#F0EAFA']}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.bigCardGrad}
      >
        <View style={styles.bigCardLeft}>
          <Text style={styles.bigCardEmoji}>{emoji}</Text>
          <View style={styles.bigCardBody}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <Text style={[styles.bigCardTitle, disabled && styles.bigCardTitleDisabled]}>
                {title}
              </Text>
              {badge ? (
                <View style={styles.badge}>
                  <Text style={styles.badgeText}>{badge}</Text>
                </View>
              ) : null}
            </View>
            <Text style={[styles.bigCardDesc, disabled && styles.bigCardDescDisabled]}>
              {desc}
            </Text>
          </View>
        </View>
        {!disabled && <Text style={styles.bigCardArrow}>›</Text>}
      </LinearGradient>
    </Pressable>
  );
}

// ── 작은 카드 (서브 기능) ──────────────────────────
function SmallCard({ emoji, title, route }) {
  return (
    <Pressable
      style={({ pressed }) => [styles.smallCard, pressed && { opacity: 0.75 }]}
      onPress={() => router.push(route)}
    >
      <Text style={styles.smallCardEmoji}>{emoji}</Text>
      <Text style={styles.smallCardTitle}>{title}</Text>
      <Text style={styles.smallCardArrow}>›</Text>
    </Pressable>
  );
}

// ── 생존 모드 홈 ──────────────────────────────────
function SurvivalHome({ onFarewellPress }) {
  return (
    <>
      <Text style={styles.sectionTitle}>오늘 무엇을 할까요?</Text>

      <BigCard
        emoji="📋"
        title="버킷리스트"
        desc="함께 하고 싶은 것들을 체크해요"
        route="/(app)/bucketlist"
        gradient={['#F0EAFA', '#E8DFF5']}
      />
      <BigCard
        emoji="📔"
        title="일기 & 추억 메모"
        desc="함께한 소중한 하루하루를 기록해요"
        route="/(app)/diary"
        gradient={['#FDEEF4', '#F5E6FA']}
      />
      <BigCard
        emoji="📸"
        title="사진 기록"
        desc="소중한 순간들을 사진으로 남겨요"
        route="/(app)/photos"
        gradient={['#FEF3F7', '#FDEAF0']}
      />
      <BigCard
        emoji="🩺"
        title="증상 안내"
        desc="반려동물 증상을 확인해요"
        route="/(app)/symptoms"
        gradient={['#FFF8FA', '#FFF3F6']}
      />

      <TouchableOpacity
        style={styles.farewellBtn}
        onPress={onFarewellPress}
        activeOpacity={0.65}
      >
        <Text style={styles.farewellBtnText}>무지개다리를 건넜어요 🌈</Text>
      </TouchableOpacity>
    </>
  );
}

// ── 이별 후 모드 홈 ───────────────────────────────
function MemorialHome({ gateStatus, hasVideo, hasLetter }) {
  return (
    <>
      <Text style={styles.sectionTitle}>오늘을 함께해요</Text>

      <BigCard
        emoji="💭"
        title="감정 체크인"
        desc="오늘 마음이 어떤지 솔직하게 기록해요"
        route="/(app)/emotion"
        gradient={['#F5E6FA', '#EDF4FB']}
      />

      <BigCard
        emoji="🌱"
        title="오늘의 미션"
        desc="작은 일상 활동으로 회복의 첫 걸음을 내딛어요"
        route="/(app)/mission"
        gradient={['#EDF5FF', '#F0EAFA']}
      />

      <GiftJourneyCard gateStatus={gateStatus} hasVideo={hasVideo} hasLetter={hasLetter} />

      <Text style={[styles.sectionTitle, { marginTop: 16 }]}>더 보기</Text>
      <View style={styles.subRow}>
        <SmallCard emoji="🌿" title="추모 타임라인" route="/(app)/timeline" />
        <SmallCard emoji="📊" title="회복 리포트" route="/(app)/report" />
      </View>
      <View style={styles.subRow}>
        <SmallCard emoji="🎞️" title="추모 영상 만들기" route="/(app)/media" />
        <SmallCard emoji="🔊" title="음성으로 듣기" route="/(app)/tts" />
      </View>
    </>
  );
}

// ── 메인 화면 ──────────────────────────────────────
export default function HomeScreen() {
  const [petName, setPetName] = useState('');
  const [petSpecies, setPetSpecies] = useState('');
  const [petGender, setPetGender] = useState('');
  const [petStartDate, setPetStartDate] = useState('');
  const [guardianTitle, setGuardianTitle] = useState('');
  const [callerName, setCallerName] = useState('보호자');
  const [memorialMode, setMemorialMode] = useState(false);
  const [gateStatus, setGateStatus] = useState('locked');
  const [hasVideo, setHasVideo] = useState(false);
  const [hasLetter, setHasLetter] = useState(false);
  const [farewellDate, setFarewellDate] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [transitioning, setTransitioning] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    const [name, species, gender, startDate, guardTitle, caller, mode, fd, petId, video, letter] = await Promise.all([
      AsyncStorage.getItem('pet_name'),
      AsyncStorage.getItem('pet_species'),
      AsyncStorage.getItem('pet_gender'),
      AsyncStorage.getItem('pet_start_date'),
      AsyncStorage.getItem('pet_guardian_title'),
      AsyncStorage.getItem('caller_name'),
      AsyncStorage.getItem('memorial_mode'),
      AsyncStorage.getItem('pet_farewell_date'),
      AsyncStorage.getItem('pet_id'),
      AsyncStorage.getItem('pet_video_url'),
      AsyncStorage.getItem('message_content'),
    ]);
    if (name) setPetName(name);
    if (species) setPetSpecies(species);
    if (gender) setPetGender(gender);
    if (startDate) setPetStartDate(startDate);
    if (guardTitle) setGuardianTitle(guardTitle);
    if (caller) setCallerName(caller);
    if (mode === 'true') setMemorialMode(true);
    if (fd) setFarewellDate(fd);
    setHasVideo(!!video);
    setHasLetter(!!letter);
    const { gateStatus: gs } = await fetchRecoveryGate(petId);
    setGateStatus(gs);
  }

  async function confirmFarewell() {
    setTransitioning(true);
    try {
      await AsyncStorage.setItem('memorial_mode', 'true');
      setMemorialMode(true);
    } finally {
      setTransitioning(false);
      setShowModal(false);
    }
  }

  const speciesEmoji =
    petSpecies === '강아지' ? '🐶' : petSpecies === '고양이' ? '🐱' : '🐾';

  const daysAfter = farewellDate
    ? Math.max(0, Math.floor((Date.now() - new Date(farewellDate).getTime()) / 86400000))
    : null;

  const petDisplay = petName || '소중한 친구';

  return (
    <LinearGradient
      colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']}
      locations={[0, 0.35, 0.6, 1]}
      style={styles.gradient}
    >
      <SafeAreaView style={styles.safe}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          showsVerticalScrollIndicator={false}
        >
          <Text style={styles.logoSub}>소중한 가족을 기억해요</Text>

          {/* 반려동물 카드 */}
          <View style={styles.petCard}>
            <Text style={styles.petEmoji}>{speciesEmoji}</Text>
            <View style={styles.petInfo}>
              <Text style={styles.petName}>{petDisplay}</Text>
              {(petGender || petSpecies) ? (
                <Text style={styles.petMeta}>
                  {[petGender, petSpecies].filter(Boolean).join(' · ')}
                </Text>
              ) : null}
              {petStartDate && farewellDate ? (
                <Text style={styles.petPeriod}>{petStartDate} ~ {farewellDate}</Text>
              ) : null}
              <Text style={styles.petSub}>
                {memorialMode && daysAfter !== null
                  ? `이별 후 D+${daysAfter}`
                  : `${callerName || '보호자'}님과 함께하는 공간이에요`}
              </Text>
            </View>
          </View>

          {memorialMode
            ? <MemorialHome gateStatus={gateStatus} hasVideo={hasVideo} hasLetter={hasLetter} />
            : <SurvivalHome onFarewellPress={() => setShowModal(true)} />
          }
        </ScrollView>
      </SafeAreaView>

      {/* 이별 전환 확인 모달 */}
      <Modal visible={showModal} transparent animationType="fade">
        <View style={styles.modalOverlay}>
          <View style={styles.modalBox}>
            <Text style={styles.modalEmoji}>🌈</Text>
            <Text style={styles.modalTitle}>
              {petDisplay}{iga(petDisplay)}{'\n'}무지개다리를 건넜군요.
            </Text>
            <Text style={styles.modalDesc}>
              고이 보내드릴게요.{'\n'}함께한 소중한 기억들이 남아있어요.
            </Text>
            {transitioning ? (
              <ActivityIndicator color="#C4A8D8" style={{ marginTop: 24 }} />
            ) : (
              <View style={styles.modalBtns}>
                <TouchableOpacity
                  style={styles.modalBtnPrimary}
                  onPress={confirmFarewell}
                  activeOpacity={0.8}
                >
                  <Text style={styles.modalBtnPrimaryText}>네, 이별했어요</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  style={styles.modalBtnSecondary}
                  onPress={() => setShowModal(false)}
                  activeOpacity={0.8}
                >
                  <Text style={styles.modalBtnSecondaryText}>아직 함께 있어요</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        </View>
      </Modal>
    </LinearGradient>
  );
}

// ── 스타일 ─────────────────────────────────────────
const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  scroll: { paddingHorizontal: 18, paddingVertical: 28, paddingBottom: 60 },

  logo: {
    fontSize: 22, fontWeight: '700', color: '#5B4E75',
    textAlign: 'center', marginBottom: 4,
  },
  logoSub: {
    fontSize: 13, color: '#8A7D9E',
    textAlign: 'center', marginBottom: 22,
  },

  petCard: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    backgroundColor: '#FFFFFF',
    borderRadius: 18, paddingVertical: 16, paddingHorizontal: 20,
    marginBottom: 22,
    borderWidth: 1.5, borderColor: '#E5DCF0',
    shadowColor: '#8A7D9E',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.09, shadowRadius: 8, elevation: 2,
  },
  petEmoji: { fontSize: 36 },
  petInfo: { flex: 1 },
  petName: { fontSize: 18, fontWeight: '800', color: '#5B4E75' },
  petMeta: { fontSize: 12, color: '#A89FBC', marginTop: 3 },
  petPeriod: { fontSize: 11, color: '#B8B0CC', marginTop: 2 },
  petSub: { fontSize: 13, color: '#8A7D9E', marginTop: 4 },

  sectionTitle: {
    fontSize: 13, fontWeight: '700', color: '#A89FBC',
    marginBottom: 10, paddingHorizontal: 2, letterSpacing: 0.3,
  },

  // BigCard
  bigCard: {
    marginBottom: 12, borderRadius: 18, overflow: 'hidden',
    borderWidth: 1.5, borderColor: '#E5DCF0',
    shadowColor: '#8A7D9E',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08, shadowRadius: 8, elevation: 2,
  },
  bigCardDisabled: { opacity: 0.55 },
  bigCardGrad: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 18, paddingHorizontal: 18,
  },
  bigCardLeft: { flexDirection: 'row', alignItems: 'center', flex: 1, gap: 14 },
  bigCardEmoji: { fontSize: 30 },
  bigCardBody: { flex: 1 },
  bigCardTitle: { fontSize: 15, fontWeight: '800', color: '#5B4E75' },
  bigCardTitleDisabled: { color: '#A89FBC' },
  bigCardDesc: { fontSize: 12, color: '#8A7D9E', marginTop: 4, lineHeight: 18 },
  bigCardDescDisabled: { color: '#B0A0C0' },
  bigCardArrow: { fontSize: 22, color: '#C4A8D8', marginLeft: 6 },

  badge: {
    backgroundColor: '#EDE5FA', borderRadius: 8,
    paddingHorizontal: 8, paddingVertical: 2,
  },
  badgeText: { fontSize: 10, color: '#8A5CB0', fontWeight: '700' },

  // ── 회복 여정 선물 카드 ──
  journeyCard: {
    marginBottom: 12, borderRadius: 18, overflow: 'hidden',
    borderWidth: 1.5, borderColor: '#E5DCF0',
    shadowColor: '#8A7D9E',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08, shadowRadius: 8, elevation: 2,
  },
  journeyGrad: { paddingVertical: 18, paddingHorizontal: 18 },
  journeyHead: { marginBottom: 16 },
  journeyTitle: { fontSize: 15, fontWeight: '800', color: '#5B4E75' },
  journeySub: { fontSize: 12, color: '#8A7D9E', marginTop: 3 },

  journeyRail: { flexDirection: 'row', alignItems: 'flex-start', paddingHorizontal: 2 },
  journeyConn: {
    flex: 1, height: 3, marginTop: 20, borderRadius: 2,
    backgroundColor: '#DDD0EF',
  },
  journeyConnDone: { backgroundColor: '#A98BD1' },
  journeyNode: { alignItems: 'center', minWidth: 42, paddingHorizontal: 3 },
  journeyCircle: {
    width: 42, height: 42, borderRadius: 21,
    alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#FFFFFF', borderWidth: 2, borderColor: '#E0D3F0',
  },
  journeyCircleDone: { backgroundColor: '#EFE3FB', borderColor: '#B99BDE' },
  journeyEmoji: { fontSize: 18 },
  journeyEmojiDim: { opacity: 0.4 },
  journeyLabel: { fontSize: 10, color: '#A89FBC', marginTop: 5 },
  journeyLabelDone: { color: '#7A5CA8', fontWeight: '700' },

  journeyBtn: {
    alignSelf: 'flex-end', marginTop: 16,
    paddingVertical: 9, paddingHorizontal: 16, borderRadius: 12,
    backgroundColor: 'rgba(169,139,209,0.18)',
  },
  journeyBtnText: { fontSize: 13, fontWeight: '800', color: '#7A5CA8' },

  // SmallCard
  subRow: { flexDirection: 'row', gap: 12, marginBottom: 12 },
  smallCard: {
    flex: 1, backgroundColor: '#FFFFFF',
    borderRadius: 16, borderWidth: 1.5, borderColor: '#E5DCF0',
    paddingVertical: 18, paddingHorizontal: 14, alignItems: 'center',
    shadowColor: '#8A7D9E',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07, shadowRadius: 6, elevation: 1,
  },
  smallCardEmoji: { fontSize: 26, marginBottom: 6 },
  smallCardTitle: { fontSize: 12, fontWeight: '700', color: '#5B4E75', textAlign: 'center' },
  smallCardArrow: { fontSize: 14, color: '#C4A8D8', marginTop: 6 },

  // 무지개다리 버튼 (조용하게)
  farewellBtn: {
    marginTop: 28, marginBottom: 8,
    alignSelf: 'center',
    paddingVertical: 10, paddingHorizontal: 16,
  },
  farewellBtnText: {
    fontSize: 13, color: '#B0A0C0',
    textDecorationLine: 'underline', textAlign: 'center',
  },

  // 모달
  modalOverlay: {
    flex: 1, backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'center', alignItems: 'center', padding: 24,
  },
  modalBox: {
    backgroundColor: '#FFFFFF', borderRadius: 24,
    padding: 28, width: '100%', alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.14, shadowRadius: 20, elevation: 10,
  },
  modalEmoji: { fontSize: 48, marginBottom: 14 },
  modalTitle: {
    fontSize: 18, fontWeight: '800', color: '#5B4E75',
    textAlign: 'center', lineHeight: 26, marginBottom: 10,
  },
  modalDesc: {
    fontSize: 14, color: '#8A7D9E',
    textAlign: 'center', lineHeight: 22, marginBottom: 26,
  },
  modalBtns: { width: '100%', gap: 10 },
  modalBtnPrimary: {
    backgroundColor: '#C4A8D8', borderRadius: 14,
    paddingVertical: 14, alignItems: 'center',
  },
  modalBtnPrimaryText: { color: '#FFFFFF', fontSize: 15, fontWeight: '700' },
  modalBtnSecondary: {
    backgroundColor: '#F3EFF9', borderRadius: 14,
    paddingVertical: 14, alignItems: 'center',
  },
  modalBtnSecondaryText: { color: '#8A7D9E', fontSize: 15, fontWeight: '600' },
});
