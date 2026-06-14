import { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Card from '@/components/Card';
import Button from '@/components/Button';
import LoadingSpinner from '@/components/LoadingSpinner';
import { getMissions, completeMission } from '@/api/missions';
import { mockMissions } from '@/api/mock';
import { COLORS } from '@/constants/colors';
import { gwa } from '@/utils/josa';
import { doLogout } from './_layout';

const COMPLETED_KEY = 'mission_completed_ids';

export default function MissionScreen() {
  const router = useRouter();
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [completing, setCompleting] = useState(null);
  const [petName, setPetName] = useState('소중한 친구');

  useEffect(() => {
    AsyncStorage.getItem('pet_name').then((v) => v && setPetName(v));
    fetchMissions();
  }, []);

  async function fetchMissions() {
    // 날짜가 바뀌었으면 완료 목록 초기화
    const today = new Date().toDateString();
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

  const doneCount = missions.filter((m) => m.completed).length;

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
        <View style={styles.headerRight}>
          <TouchableOpacity onPress={doLogout} style={styles.headerBtn} activeOpacity={0.7}>
            <Text style={styles.headerLogout}>로그아웃</Text>
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.subtitle}>{petName}{gwa(petName)} 함께했던 일상으로 천천히 돌아가요.</Text>

        {/* 완료율 바 */}
        <View style={styles.progressRow}>
          <View style={styles.progressTrack}>
            <View
              style={[
                styles.progressFill,
                { width: missions.length ? `${(doneCount / missions.length) * 100}%` : '0%' },
              ]}
            />
          </View>
          <Text style={styles.progressLabel}>{doneCount}/{missions.length} 완료</Text>
        </View>

        {/* 미션 카드 목록 */}
        <View style={styles.missionList}>
          {missions.map((mission) => (
            <Card key={mission.id} style={[styles.missionCard, mission.completed && styles.missionCardDone]}>
              <View style={styles.missionRow}>
                <Text style={styles.missionEmoji}>{mission.completed ? '✅' : '🌱'}</Text>
                <View style={styles.missionInfo}>
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

              {!mission.completed ? (
                <Button
                  variant="primary"
                  onPress={() => handleComplete(mission.id)}
                  loading={completing === mission.id}
                  style={styles.completeBtn}
                >
                  완료했어요
                </Button>
              ) : null}
            </Card>
          ))}
        </View>

        {doneCount === missions.length && missions.length > 0 ? (
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
  headerRight: { flexDirection: 'row', gap: 12 },
  headerHome: { fontSize: 14, fontWeight: '700', color: '#C4A8D8' },
  headerLogout: { fontSize: 14, fontWeight: '700', color: '#E57373' },
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
  missionTitle: { fontSize: 15, fontWeight: '600', color: COLORS.textPrimary },
  missionTitleDone: { textDecorationLine: 'line-through', color: COLORS.textLight },
  missionDesc: { fontSize: 13, color: COLORS.textSecondary, marginTop: 3 },
  missionRationale: { fontSize: 12, color: '#9B8DB8', marginTop: 6, lineHeight: 17 },
  completeBtn: { marginTop: 12 },
  allDone: { textAlign: 'center', color: COLORS.primary, fontWeight: '700', fontSize: 15, marginTop: 20 },
});
