import { useState } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import {
  initialize,
  requestPermission,
  getGrantedPermissions,
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

  // 권한이 안 잡힐 때 수동으로 열어보는 보조 버튼
  async function handleOpenSettings() {
    try {
      await initialize();
    } catch {}
    try {
      openHealthConnectSettings();
    } catch (e) {
      setError('Health Connect 설정을 열 수 없어요: ' + (e?.message ?? e));
    }
  }

  // 메인 흐름: SDK 확인 → 권한 요청 → 데이터 읽기 → 서버 전송
  async function handleSync() {
    setLoading(true);
    setError('');
    setResult(null);

    try {
      setStatusMsg('Health Connect 확인 중...');
      const sdk = await getSdkStatus();
      if (sdk !== SdkAvailabilityStatus.SDK_AVAILABLE) {
        setError(
          'Health Connect 앱이 필요해요. Play 스토어에서 "Health Connect"를 설치하고, ' +
            '삼성헬스 → 설정 → Health Connect 연결을 켠 뒤 다시 시도해주세요.'
        );
        setLoading(false);
        return;
      }

      await initialize();

      // 이미 허용돼 있으면 권한창을 다시 띄우지 않는다
      setStatusMsg('권한 확인 중...');
      let granted = await getGrantedPermissions();
      const hasAll = (list) =>
        list.some((p) => p.recordType === 'Steps' && p.accessType === 'read') &&
        list.some((p) => p.recordType === 'SleepSession' && p.accessType === 'read');

      if (!hasAll(granted)) {
        setStatusMsg('걸음·수면 권한 요청 중...');
        granted = await requestPermission(PERMISSIONS);
      }

      if (!hasAll(granted)) {
        setError(
          '걸음·수면 권한이 허용되지 않았어요. 권한창에서 두 항목을 모두 허용해주세요. ' +
            '(허용해도 안 되면 아래 "Health Connect 설정 열기"에서 직접 켜주세요.)'
        );
        setLoading(false);
        return;
      }

      setStatusMsg('걸음·수면 기록 읽는 중...');
      const now = new Date();
      const start = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      const timeRangeFilter = {
        operator: 'between',
        startTime: start.toISOString(),
        endTime: now.toISOString(),
      };

      let steps_result = null;
      let sleep_result = null;
      try { steps_result = await readRecords('Steps', { timeRangeFilter }); } catch {}
      try { sleep_result = await readRecords('SleepSession', { timeRangeFilter }); } catch {}

      setStatusMsg('서버로 전송 중...');
      const petId = await AsyncStorage.getItem('pet_id');
      const res = await syncHealth({ pet_id: petId, steps_result, sleep_result });
      setResult(res);
    } catch (e) {
      setError('오류: ' + (e?.message ?? String(e)));
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
              아래 <Text style={styles.bold}>삼성헬스 연동하기</Text>를 누르면{'\n'}
              걸음·수면 권한창이 떠요. 두 항목을 모두 허용하면{'\n'}
              자동으로 데이터를 읽어 회복 분석에 반영해요.{'\n\n'}
              <Text style={styles.bold}>처음 한 번</Text> 삼성헬스 → 설정 →{'\n'}
              Health Connect 연결을 켜둬야 데이터가 들어와요.
            </Text>
          </View>

          {error ? <Text style={styles.error}>{error}</Text> : null}

          {loading ? (
            <LoadingSpinner message={statusMsg || '잠시만 기다려주세요...'} />
          ) : (
            <>
              <Button onPress={handleSync} variant="primary" style={styles.btn}>
                삼성헬스 연동하기
              </Button>
              <Button onPress={handleOpenSettings} variant="ghost" style={styles.btn}>
                권한이 안 잡힐 때: Health Connect 설정 열기
              </Button>
            </>
          )}

          {result ? (
            <Card style={styles.resultCard}>
              <Text style={styles.resultTitle}>💜 연동 완료</Text>
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
  resultCard: { backgroundColor: '#F0EBF8', borderColor: '#C9B8E8', borderWidth: 1 },
  resultTitle: { fontSize: 15, fontWeight: '700', color: '#5B4E75', marginBottom: 12 },
  resultRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6 },
  resultLabel: { fontSize: 13, color: '#8A7D9E' },
  resultValue: { fontSize: 14, fontWeight: '700', color: '#5B4E75' },
  resultHint: { fontSize: 12, color: '#8A7D9E', marginTop: 10, lineHeight: 18 },
});
