import { useState, useCallback } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity, Dimensions } from 'react-native';
import { useRouter } from 'expo-router';
import { useFocusEffect } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import Svg, { Polyline, Circle } from 'react-native-svg';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Card from '@/components/Card';
import LoadingSpinner from '@/components/LoadingSpinner';
import { getReport } from '@/api/report';
import { mockReport } from '@/api/mock';
import { COLORS } from '@/constants/colors';
import { eulreul } from '@/utils/josa';
import { doLogout } from './_layout';
import { hasPermission, openPermissionSettings, collectTodayReport } from '../../modules/usage-stats/src';

const CHART_W = Dimensions.get('window').width - 80;
const CHART_H = 90;

function formatLabel(raw) {
  if (!raw) return '';
  if (raw.includes('T')) return raw.slice(5, 10).replace('-', '/');
  return raw;
}

function ComboChart({ data, valueKey, color, maxOverride }) {
  if (!data || data.length === 0) return null;
  const values = data.map((d) => d[valueKey] ?? 0);
  const maxVal = maxOverride ?? Math.max(...values, 1);
  const barW = Math.floor((CHART_W - (data.length - 1) * 4) / data.length);

  const points = data.map((d, i) => {
    const x = i * (barW + 4) + barW / 2;
    const y = CHART_H - Math.max(4, ((d[valueKey] ?? 0) / maxVal) * (CHART_H - 12));
    return { x, y };
  });
  const polyPoints = points.map((p) => `${p.x},${p.y}`).join(' ');

  return (
    <View style={{ height: CHART_H + 28 }}>
      <View style={[StyleSheet.absoluteFill, { flexDirection: 'row', alignItems: 'flex-end', gap: 4, height: CHART_H }]}>
        {data.map((d, i) => (
          <View key={i} style={{ width: barW, alignItems: 'center', justifyContent: 'flex-end', height: CHART_H }}>
            <View
              style={{
                width: barW * 0.65,
                height: Math.max(4, ((d[valueKey] ?? 0) / maxVal) * (CHART_H - 12)),
                backgroundColor: color + '55',
                borderRadius: 3,
              }}
            />
          </View>
        ))}
      </View>
      <Svg width={CHART_W} height={CHART_H} style={StyleSheet.absoluteFill}>
        <Polyline
          points={polyPoints}
          fill="none"
          stroke={color}
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {points.map((p, i) => (
          <Circle key={i} cx={p.x} cy={p.y} r={3} fill={color} />
        ))}
      </Svg>
      <View style={{ flexDirection: 'row', gap: 4, marginTop: CHART_H + 4 }}>
        {data.map((d, i) => (
          <View key={i} style={{ width: barW, alignItems: 'center' }}>
            <Text style={styles.barLabel}>{formatLabel(d.created_at)}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

export default function ReportScreen() {
  const router = useRouter();
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [petName, setPetName] = useState('소중한 친구');
  const [usageReport, setUsageReport] = useState(null);
  const [permissionGranted, setPermissionGranted] = useState(null);

  useFocusEffect(
    useCallback(() => {
      AsyncStorage.getItem('pet_name').then((v) => v && setPetName(v));
      fetchReport();
      fetchUsageReport();
    }, [])
  );

  async function fetchReport() {
    setLoading(true);
    try {
      const petId = await AsyncStorage.getItem('pet_id');
      const data = await getReport(petId);
      setReport(data);
    } catch {
      setReport(mockReport);
    } finally {
      setLoading(false);
    }
  }

  async function fetchUsageReport() {
    try {
      const granted = await hasPermission();
      setPermissionGranted(granted);
      if (granted) {
        const data = await collectTodayReport();
        setUsageReport(data);
      }
    } catch {
      // 네이티브 모듈 미지원 환경(iOS/Expo Go) — 조용히 무시
    }
  }

  if (loading) {
    return (
      <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
        <SafeAreaView style={styles.safe}>
          <LoadingSpinner message="리포트를 불러오고 있어요..." />
        </SafeAreaView>
      </LinearGradient>
    );
  }

  const trend = report?.emotion_trend ?? [];
  const sleepTrend = report?.sleep_trend ?? [];
  const missionRate = Math.round((report?.mission_completion_rate ?? 0) * 100);

  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
    <SafeAreaView style={styles.safe}>
      {/* 헤더 */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} style={styles.headerBtn} activeOpacity={0.7}>
          <Text style={styles.headerBack}>← 뒤로</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>회복 리포트</Text>
        <View style={styles.headerRight}>
          <TouchableOpacity onPress={doLogout} style={styles.headerBtn} activeOpacity={0.7}>
            <Text style={styles.headerLogout}>로그아웃</Text>
          </TouchableOpacity>
        </View>
      </View>

      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>회복 리포트</Text>
        <Text style={styles.subtitle}>{petName}{eulreul(petName)} 기억하며 함께한 시간이에요.</Text>

        {/* 앱 사용 기록 — 권한 없으면 안내 카드 */}
        {permissionGranted === false ? (
          <Card style={styles.card}>
            <Text style={styles.sectionTitle}>📱 스마트폰 사용 패턴</Text>
            <Text style={styles.noData}>일상 복귀 분석을 위해 앱 사용 기록 권한이 필요해요.</Text>
            <TouchableOpacity style={styles.permBtn} onPress={openPermissionSettings} activeOpacity={0.7}>
              <Text style={styles.permBtnText}>권한 허용하기</Text>
            </TouchableOpacity>
          </Card>
        ) : usageReport ? (
          <>
            {/* 오늘 행동 신호 */}
            {usageReport.signals.length > 0 ? (
              <Card style={styles.card}>
                <Text style={styles.sectionTitle}>📱 오늘 행동 신호</Text>
                {usageReport.signals.map((s, i) => (
                  <View key={i} style={styles.signalRow}>
                    <Text style={styles.signalIcon}>{s.icon}</Text>
                    <View style={styles.signalInfo}>
                      <Text style={styles.signalTitle}>{s.title}</Text>
                      <Text style={styles.signalDetail}>오늘 {s.todayMinutes}분</Text>
                    </View>
                  </View>
                ))}
                {usageReport.estimatedSleepTime ? (
                  <Text style={styles.sleepHint}>🌙 {usageReport.estimatedSleepTime}</Text>
                ) : null}
              </Card>
            ) : (
              <Card style={styles.card}>
                <Text style={styles.sectionTitle}>📱 오늘 행동 신호</Text>
                <Text style={styles.noData}>오늘은 특이 패턴이 없어요. 건강한 하루예요! 🌿</Text>
                {usageReport.estimatedSleepTime ? (
                  <Text style={styles.sleepHint}>🌙 {usageReport.estimatedSleepTime}</Text>
                ) : null}
              </Card>
            )}

            {/* 앱 사용 현황 상위 5개 */}
            <Card style={styles.card}>
              <Text style={styles.sectionTitle}>⏱ 오늘 앱 사용 현황</Text>
              <Text style={styles.chartHint}>총 {usageReport.totalMinutes}분 · 새벽 {usageReport.lateNightMinutes}분</Text>
              {usageReport.daily.slice(0, 5).map((app, i) => (
                <View key={i} style={styles.appRow}>
                  <Text style={styles.appLabel} numberOfLines={1}>{app.appLabel}</Text>
                  <View style={styles.appBarWrap}>
                    <View style={[styles.appBar, { width: `${Math.min((app.usageMinutes / Math.max(usageReport.totalMinutes, 1)) * 100, 100)}%` }]} />
                  </View>
                  <Text style={styles.appMin}>{app.usageMinutes}분</Text>
                </View>
              ))}
            </Card>
          </>
        ) : null}

        {/* 서비스 이용 현황 */}
        <Card style={styles.card}>
          <Text style={styles.sectionTitle}>📊 이용 현황</Text>
          <View style={styles.statsRow}>
            <View style={styles.statBox}>
              <Text style={styles.statNumber}>{report?.usage?.emotions ?? 0}</Text>
              <Text style={styles.statLabel}>감정 기록</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statBox}>
              <Text style={styles.statNumber}>{report?.usage?.messages ?? 0}</Text>
              <Text style={styles.statLabel}>추모 메시지</Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statBox}>
              <Text style={styles.statNumber}>{report?.usage?.missions ?? 0}</Text>
              <Text style={styles.statLabel}>미션 완료</Text>
            </View>
          </View>
        </Card>

        {/* 감정 변화 */}
        {trend.length > 0 ? (
          <Card style={styles.card}>
            <Text style={styles.sectionTitle}>💭 감정 변화</Text>
            <Text style={styles.chartHint}>막대: 강도  ·  선: 추세</Text>
            <ComboChart data={trend} valueKey="score" color="#C4A8D8" maxOverride={10} />
          </Card>
        ) : null}

        {/* 미션 완료율 */}
        <Card style={styles.card}>
          <Text style={styles.sectionTitle}>🌱 미션 완료율</Text>
          <View style={styles.completionRow}>
            <View style={styles.completionTrack}>
              <View style={[styles.completionFill, { width: `${missionRate}%` }]} />
            </View>
            <Text style={styles.completionPct}>{missionRate}%</Text>
          </View>
        </Card>

        {/* 수면 변화 */}
        <Card style={styles.card}>
          <Text style={styles.sectionTitle}>🌙 수면 변화</Text>
          <Text style={styles.chartHint}>막대: 수면 시간  ·  선: 추세 (단위: 시간)</Text>
          {sleepTrend.length > 0 ? (
            <ComboChart data={sleepTrend} valueKey="hours" color="#7BC8A4" maxOverride={12} />
          ) : (
            <Text style={styles.noData}>수면 데이터가 아직 없어요.</Text>
          )}
        </Card>
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
  },
  headerBtn: { paddingHorizontal: 4, paddingVertical: 4 },
  headerBack: { fontSize: 14, color: '#8A7D9E' },
  headerTitle: { fontSize: 16, fontWeight: '700', color: '#5B4E75' },
  headerRight: { flexDirection: 'row', gap: 12 },
  headerHome: { fontSize: 14, fontWeight: '700', color: '#C4A8D8' },
  headerLogout: { fontSize: 14, fontWeight: '700', color: '#E57373' },
  scroll: { paddingHorizontal: 20, paddingVertical: 24 },
  title: { fontSize: 22, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center', marginBottom: 6 },
  subtitle: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginBottom: 28 },
  card: { marginBottom: 16 },
  sectionTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 6 },
  chartHint: { fontSize: 11, color: COLORS.textSecondary, marginBottom: 14 },
  statsRow: { flexDirection: 'row', alignItems: 'center' },
  statBox: { flex: 1, alignItems: 'center' },
  statNumber: { fontSize: 26, fontWeight: '700', color: COLORS.cta },
  statLabel: { fontSize: 12, color: COLORS.textSecondary, marginTop: 4 },
  statDivider: { width: 1, height: 40, backgroundColor: COLORS.divider },
  barLabel: { fontSize: 9, color: COLORS.textLight, textAlign: 'center' },
  completionRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  completionTrack: { flex: 1, height: 10, backgroundColor: '#EDE5DF', borderRadius: 5, overflow: 'hidden' },
  completionFill: { height: '100%', backgroundColor: COLORS.primary, borderRadius: 5 },
  completionPct: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, minWidth: 40, textAlign: 'right' },
  noData: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', paddingVertical: 20 },
  permBtn: { marginTop: 12, backgroundColor: COLORS.primary, borderRadius: 8, paddingVertical: 10, alignItems: 'center' },
  permBtnText: { color: '#fff', fontWeight: '700', fontSize: 14 },
  signalRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: '#F0EAF5' },
  signalIcon: { fontSize: 20 },
  signalInfo: { flex: 1 },
  signalTitle: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary },
  signalDetail: { fontSize: 12, color: COLORS.textSecondary, marginTop: 2 },
  sleepHint: { fontSize: 12, color: COLORS.textSecondary, marginTop: 10 },
  appRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 5 },
  appLabel: { fontSize: 12, color: COLORS.textPrimary, width: 80 },
  appBarWrap: { flex: 1, height: 6, backgroundColor: '#EDE5DF', borderRadius: 3, overflow: 'hidden' },
  appBar: { height: '100%', backgroundColor: '#C4A8D8', borderRadius: 3 },
  appMin: { fontSize: 12, color: COLORS.textSecondary, minWidth: 32, textAlign: 'right' },
});
