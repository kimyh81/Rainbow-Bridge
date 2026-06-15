import { useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useRouter, useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Video, ResizeMode } from 'expo-av';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Card from '@/components/Card';
import Button from '@/components/Button';
import LoadingSpinner from '@/components/LoadingSpinner';
import { getMissions, completeMission, skipMission } from '@/api/missions';
import { mockMissions } from '@/api/mock';
import { API_URL } from '@/api/axiosInstance';
import { COLORS } from '@/constants/colors';
import { gwa } from '@/utils/josa';

const COMPLETED_KEY = 'mission_completed_ids';

// 난이도 배지 — 소람님 LLM이 difficulty 필드(gentle/small/active)로 내려줌.
// 회복 단계(점수/레벨)는 백엔드가 결정하고, 프론트는 받은 난이도만 부드럽게 표시한다.
//   gentle(G): 0~44점 기본 / small(Sm): 승격~ / active(A): 80점+ (L0)에서 등장
const DIFFICULTY_META = {
  gentle: { label: '가볍게', emoji: '🌱', bg: '#EAF7EF', fg: '#3E9B6B' },
  small: { label: '한 걸음 더', emoji: '🌿', bg: '#E9F0FB', fg: '#4A77C0' },
  active: { label: '활동', emoji: '☀️', bg: '#FCF2E2', fg: '#C8862F' },
};

export default function MissionScreen() {
  const router = useRouter();
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(null);
  const [skipping, setSkipping] = useState(null);
  const [petName, setPetName] = useState('소중한 친구');

  useFocusEffect(
    useCallback(() => {
      AsyncStorage.getItem('pet_name').then((v) => v && setPetName(v));
      fetchMissions();
    }, [])
  );

  async function fetchMissions() {
    // 날짜가 바뀌었으면 완료 목록 초기화
    // 서버(UTC) 기준 날짜로 맞춘다 — 로컬 자정과 UTC 자정이 최대 9시간 어긋나
    // 완료 목록이 엉뚱한 시점에 초기화되던 문제 방지 (BUG-11)
    const today = new Date().toISOString().slice(0, 10);
    const savedDate = await AsyncStorage.getItem('mission_completed_date');
    if (savedDate !== today) {
      await AsyncStorage.removeItem(COMPLETED_KEY);
      await AsyncStorage.setItem('mission_completed_date', today);
    }

    try {
      const petId = await AsyncStorage.getItem('pet_id');
      const data = await getMissions({ pet_id: petId });

      // 저장된 완료 ID 불러와서 병합 (오프라인 체크 유지)
      const saved = await AsyncStorage.getItem(COMPLETED_KEY);
      const savedIds = saved ? JSON.parse(saved) : [];
      const merged = data.map((m) => ({
        ...m,
        completed: m.completed || savedIds.includes(m.id),
      }));
      setMissions(merged);

      // 로컬엔 완료지만 서버에 미반영된 미션 → 백그라운드로 완료 재동기화.
      // 완료 API가 실패했던 건이 재진입 때 서버에 반영돼, 서버값으로 리셋되는 문제 방지 (BUG-06)
      data.forEach((m) => {
        if (!m.completed && savedIds.includes(m.id)) {
          completeMission({ mission_id: m.id }).catch(() => {});
        }
      });
    } catch {
      const saved = await AsyncStorage.getItem(COMPLETED_KEY);
      const savedIds = saved ? JSON.parse(saved) : [];
      const merged = mockMissions.map((m) => ({
        ...m,
        completed: m.completed || savedIds.includes(m.id),
      }));
      setMissions(merged);
    } finally {
      setLoading(false);
    }
  }

  async function persistCompleted(updatedList) {
    const ids = updatedList.filter((m) => m.completed).map((m) => m.id);
    await AsyncStorage.setItem(COMPLETED_KEY, JSON.stringify(ids));
  }

  async function handleComplete(missionId) {
    setCompleting(missionId);
    try {
      const updated = await completeMission({ mission_id: missionId });
      const next = missions.map((m) => (m.id === missionId ? updated : m));
      setMissions(next);
      await persistCompleted(next);
    } catch {
      const next = missions.map((m) =>
        m.id === missionId ? { ...m, completed: true } : m
      );
      setMissions(next);
      await persistCompleted(next);
    } finally {
      setCompleting(null);
    }
  }

  // 미션 건너뛰기 — 세종님 백엔드가 같은 난이도 대체 미션을 만들어 그 자리에 끼워준다.
  // replacement가 없으면(더 줄 미션이 없으면) 해당 미션을 목록에서 숨긴다(skipped).
  async function handleSkip(missionId) {
    setSkipping(missionId);
    try {
      const { replacement } = await skipMission({ mission_id: missionId });
      setMissions((prev) =>
        prev.map((m) =>
          m.id === missionId
            ? replacement
              ? { ...replacement, completed: false }
              : { ...m, skipped: true }
            : m
        )
      );
    } catch {
      // 백엔드 실패 시 — 일단 목록에서 숨겨 다른 미션에 집중하게 한다
      setMissions((prev) =>
        prev.map((m) => (m.id === missionId ? { ...m, skipped: true } : m))
      );
    } finally {
      setSkipping(null);
    }
  }

  // skip된 미션은 화면에서 제외 (대체 미션이 그 자리를 채움)
  const visibleMissions = missions.filter((m) => !m.skipped);
  const doneCount = visibleMissions.filter((m) => m.completed).length;
  const totalCount = visibleMissions.length;

  if (loading) {
    return (
      <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
        <SafeAreaView style={styles.safe}>
          <LoadingSpinner message="미션을 불러오고 있어요..." />
        </SafeAreaView>
      </LinearGradient>
    );
  }

  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
    <SafeAreaView style={styles.safe}>
      {/* 헤더 */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBtn} activeOpacity={0.7}>
          <Text style={styles.headerBack}>← 뒤로</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>오늘의 미션</Text>
        <View style={styles.headerSpacer} />
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.subtitle}>{petName}{gwa(petName)} 함께했던 일상으로 천천히 돌아가요.</Text>

        {/* 완료율 바 */}
        <View style={styles.progressRow}>
          <View style={styles.progressTrack}>
            <View
              style={[
                styles.progressFill,
                { width: totalCount ? `${(doneCount / totalCount) * 100}%` : '0%' },
              ]}
            />
          </View>
          <Text style={styles.progressLabel}>{doneCount}/{totalCount} 완료</Text>
        </View>

        {/* 미션 카드 목록 */}
        <View style={styles.missionList}>
          {visibleMissions.map((mission) => {
            const diff = DIFFICULTY_META[mission.difficulty];
            // 슬라이드쇼 같은 자동 생성 특별 미션은 건너뛸 수 없음
            const isSpecial = !!mission.video_url || String(mission.id).startsWith('slideshow');
            return (
              <Card key={mission.id} style={[styles.missionCard, mission.completed && styles.missionCardDone]}>
                <View style={styles.missionRow}>
                  <Text style={styles.missionEmoji}>{mission.completed ? '✅' : '🌱'}</Text>
                  <View style={styles.missionInfo}>
                    {diff ? (
                      <View style={[styles.diffBadge, { backgroundColor: diff.bg }]}>
                        <Text style={[styles.diffBadgeText, { color: diff.fg }]}>
                          {diff.emoji} {diff.label}
                        </Text>
                      </View>
                    ) : null}
                    <Text style={[styles.missionTitle, mission.completed && styles.missionTitleDone]}>
                      {'📋 '}{mission.title}
                    </Text>
                    {mission.description ? (
                      <Text style={styles.missionDesc}>{mission.description}</Text>
                    ) : null}
                    {mission.rationale ? (
                      <Text style={styles.missionRationale}>
                        {'💡 '}{mission.rationale}{mission.category ? ` — (${mission.category})` : ''}
                      </Text>
                    ) : null}
                  </View>
                </View>

                {mission.video_url ? (
                  <View style={styles.slideshowCard}>
                    <Text style={styles.slideshowBadge}>✅ 완성</Text>
                    <Text style={styles.slideshowLabel}>🎞️ 추모 슬라이드쇼가 준비됐어요</Text>
                    <Video
                      source={{
                        uri: mission.video_url.startsWith('http')
                          ? mission.video_url
                          : `${API_URL}${mission.video_url}`,
                      }}
                      style={styles.video}
                      useNativeControls
                      resizeMode={ResizeMode.CONTAIN}
                      isLooping={false}
                    />
                    <Text style={styles.videoDisclaimer}>
                      {petName}{gwa(petName)} 함께한 추억 사진으로 만든 슬라이드쇼예요.
                    </Text>
                  </View>
                ) : null}

                {!mission.completed && !isSpecial ? (
                  <>
                    <Button
                      variant="primary"
                      onPress={() => handleComplete(mission.id)}
                      loading={completing === mission.id}
                      disabled={skipping === mission.id}
                      style={styles.completeBtn}
                    >
                      완료했어요
                    </Button>
                    <TouchableOpacity
                      onPress={() => handleSkip(mission.id)}
                      disabled={skipping === mission.id || completing === mission.id}
                      style={styles.skipBtn}
                      activeOpacity={0.7}
                    >
                      <Text style={styles.skipText}>
                        {skipping === mission.id ? '다른 미션을 가져오는 중…' : '오늘은 이 미션 건너뛰기'}
                      </Text>
                    </TouchableOpacity>
                  </>
                ) : null}
              </Card>
            );
          })}
        </View>

        {doneCount === totalCount && totalCount > 0 ? (
          <Text style={styles.allDone}>🎉 오늘 미션을 모두 완료했어요!</Text>
        ) : null}
      </ScrollView>
    </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#E5DCF0',
    backgroundColor: 'transparent',
  },
  headerBtn: { paddingHorizontal: 4, paddingVertical: 4 },
  headerBack: { fontSize: 14, color: '#8A7D9E' },
  headerTitle: { fontSize: 16, fontWeight: '700', color: '#5B4E75' },
  headerSpacer: { width: 56 },
  scroll: { paddingHorizontal: 20, paddingVertical: 24 },
  subtitle: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginBottom: 24 },
  progressRow: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 24 },
  progressTrack: { flex: 1, height: 6, backgroundColor: '#EDE5DF', borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: COLORS.primary, borderRadius: 3 },
  progressLabel: { fontSize: 13, color: COLORS.textPrimary, fontWeight: '600', minWidth: 52 },
  missionList: { gap: 14 },
  missionCard: {},
  missionCardDone: { opacity: 0.65 },
  missionRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, marginBottom: 4 },
  missionEmoji: { fontSize: 24, marginTop: 1 },
  missionInfo: { flex: 1 },
  diffBadge: { alignSelf: 'flex-start', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, marginBottom: 6 },
  diffBadgeText: { fontSize: 11, fontWeight: '700' },
  missionTitle: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary },
  missionTitleDone: { textDecorationLine: 'line-through', color: COLORS.textLight },
  missionDesc: { fontSize: 13, color: COLORS.textSecondary, marginTop: 3 },
  missionRationale: { fontSize: 12, color: '#9B8DB8', marginTop: 6, lineHeight: 17 },
  completeBtn: { marginTop: 12 },
  skipBtn: { alignSelf: 'center', paddingVertical: 8, marginTop: 8 },
  skipText: { fontSize: 13, color: '#9B8DB8', fontWeight: '600', textDecorationLine: 'underline' },
  allDone: { textAlign: 'center', color: COLORS.primary, fontWeight: '700', fontSize: 15, marginTop: 20 },
  slideshowCard: {
    marginTop: 14,
    backgroundColor: '#F0F8F6',
    borderRadius: 14,
    padding: 14,
    borderWidth: 1,
    borderColor: '#7DCFBC',
  },
  slideshowBadge: { fontSize: 11, fontWeight: '700', color: '#2D7A4F', marginBottom: 6 },
  slideshowLabel: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 10 },
  video: { width: '100%', aspectRatio: 1, borderRadius: 10, backgroundColor: '#000' },
  videoDisclaimer: { fontSize: 12, color: COLORS.textSecondary, marginTop: 8, lineHeight: 18 },
});
