import { useState } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  initialize,
  requestPermission,
  readRecords,
  getSdkStatus,
  openHealthConnectSettings,
  SdkAvailabilityStatus,
} from 'react-native-health-connect';
import Card from '@/components/Card';
import Button from '@/components/Button';
import LoadingSpinner from '@/components/LoadingSpinner';
import { COLORS } from '@/constants/colors';
import { syncHealth } from '@/api/health';

// 읽을 데이터: 걸음 + 수면. (권한명은 app.json: READ_STEPS / READ_SLEEP)
const PERMISSIONS = [
  { accessType: 'read', recordType: 'Steps' },
  { accessType: 'read', recordType: 'SleepSession' },
];

export default function HealthScreen() {
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [needsSetup, setNeedsSetup] = useState(false);

  async function handleSync() {
    setLoading(true);
    setError('');
    setResult(null);
    setNeedsSetup(false);
    try {
      // 1) Health Connect 사용 가능 여부 확인
      setStatusMsg('Health Connect 확인 중...');
      const sdk = await getSdkStatus();
      if (sdk !== SdkAvailabilityStatus.SDK_AVAILABLE) {
        setNeedsSetup(true);
        setError('Health Connect를 사용할 수 없어요. 삼성헬스 설정에서 Health Connect 동기화를 켜주세요.');
        setLoading(false);
        return;
      }

      // 2) 초기화
      const ok = await initialize();
      if (!ok) throw new Error('Health Connect 초기화 실패');

      // 3) 권한 요청 (걸음·수면 읽기)
      setStatusMsg('권한을 확인하고 있어요...');
      const granted = await requestPermission(PERMISSIONS);
      const can = (type) =>
        granted.some((p) => p.recordType === type && p.accessType === 'read');

      // 4) 최근 24시간 데이터 읽기 (가공하지 않고 응답 그대로 전송)
      setStatusMsg('걸음·수면 기록을 읽고 있어요...');
      const now = new Date();
      const start = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      const timeRangeFilter = {
        operator: 'between',
        startTime: start.toISOString(),
        endTime: now.toISOString(),
      };

      let steps_result = null;
      let sleep_result = null;
      if (can('Steps')) {
        try { steps_result = await readRecords('Steps', { timeRangeFilter }); } catch {}
      }
      if (can('SleepSession')) {
        try { sleep_result = await readRecords('SleepSession', { timeRangeFilter }); } catch {}
      }

      if (!steps_result && !sleep_result) {
        setError('읽을 수 있는 데이터가 없어요. 권한을 허용했는지, 삼성헬스에 기록이 있는지 확인해주세요.');
        setLoading(false);
        return;
      }

      // 5) 백엔드로 전송 → 회복 점수에 반영
      setStatusMsg('서버로 전송하고 있어요...');
      const petId = await AsyncStorage.getItem('pet_id');
      const res = await syncHealth({ pet_id: petId, steps_result, sleep_result });
      setResult(res);
    } catch (e) {
      console.warn('[Health] 동기화 실패:', e?.message ?? e);
      setError('동기화 중 문제가 생겼어요. 잠시 후 다시 시도해주세요.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
      <SafeAreaView style={styles.safe}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <Text style={styles.title}>삼성헬스 연동</Text>
          <Text style={styles.subtitle}>
            걸음 수와 수면 기록을 불러와{'\n'}회복 흐름 분석에 반영해요.
          </Text>

          <View style={styles.infoCard}>
            <Text style={styles.infoText}>
              📱 먼저 <Text style={styles.bold}>삼성헬스 설정 → Health Connect 동기화</Text>를 켜주세요.{'\n'}
              연동 버튼을 누르면 걸음·수면 읽기 권한을 요청해요.
            </Text>
          </View>

          {error ? <Text style={styles.error}>{error}</Text> : null}

          {loading ? (
            <LoadingSpinner message={statusMsg || '잠시만 기다려주세요...'} />
          ) : (
            <Button onPress={handleSync} variant="primary" style={styles.btn}>
              삼성헬스 연동하기
            </Button>
          )}

          {needsSetup ? (
            <Button onPress={openHealthConnectSettings} variant="ghost" style={styles.btn}>
              Health Connect 설정 열기
            </Button>
          ) : null}

          {result ? (
            <Card style={styles.resultCard}>
              <Text style={styles.resultTitle}>✅ 연동 완료</Text>
              <View style={styles.resultRow}>
                <Text style={styles.resultLabel}>기준 날짜</Text>
                <Text style={styles.resultValue}>{result.date ?? '-'}</Text>
              </View>
              <View style={styles.resultRow}>
                <Text style={styles.resultLabel}>걸음 수</Text>
                <Text style={styles.resultValue}>{result.steps ?? 0} 걸음</Text>
              </View>
              <View style={styles.resultRow}>
                <Text style={styles.resultLabel}>수면 시간</Text>
                <Text style={styles.resultValue}>{result.sleep_hours ?? 0} 시간</Text>
              </View>
              <Text style={styles.resultHint}>
                회복 리포트에 반영됐어요. 회복 리포트 화면에서 확인해보세요.
              </Text>
            </Card>
          ) : null}
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  scroll: { paddingHorizontal: 20, paddingVertical: 32 },
  title: { fontSize: 22, fontWeight: '700', color: COLORS.textPrimary, textAlign: 'center', marginBottom: 6 },
  subtitle: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginBottom: 20, lineHeight: 22 },
  infoCard: {
    backgroundColor: '#F0EBF8', borderRadius: 14, padding: 14,
    borderWidth: 1, borderColor: '#E0D5F0', marginBottom: 20,
  },
  infoText: { fontSize: 13, color: '#6B5B8A', lineHeight: 20 },
  bold: { fontWeight: '700', color: '#5B4E75' },
  error: { color: COLORS.danger, fontSize: 13, textAlign: 'center', marginBottom: 12 },
  btn: { marginBottom: 12 },
  resultCard: { backgroundColor: '#F0F8F6', borderColor: COLORS.success, borderWidth: 1 },
  resultTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  resultRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6 },
  resultLabel: { fontSize: 13, color: COLORS.textSecondary },
  resultValue: { fontSize: 14, fontWeight: '700', color: COLORS.textPrimary },
  resultHint: { fontSize: 12, color: COLORS.textSecondary, marginTop: 10, lineHeight: 18 },
});
