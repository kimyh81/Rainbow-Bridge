import { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import Card from '@/components/Card';
import LoadingSpinner from '@/components/LoadingSpinner';
import { getHospitals } from '@/api/hospitals';
import { COLORS } from '@/constants/colors';

const BASIC_INFO = [
  { icon: '🐾', title: '구토·설사', desc: '물을 충분히 공급하고, 12시간 이상 지속되면 내원해 주세요.' },
  { icon: '😮‍💨', title: '호흡 이상', desc: '빠른 호흡이나 입을 벌려 숨 쉰다면 즉시 내원이 필요합니다.' },
  { icon: '🤕', title: '외상·출혈', desc: '깨끗한 천으로 압박하고 즉시 동물병원에 가주세요.' },
  { icon: '🚫', title: '음식 거부', desc: '24시간 이상 사료를 안 먹으면 수의사 상담을 권장합니다.' },
];

export default function SymptomsScreen() {
  const [hospitals, setHospitals] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // x=경도, y=위도 필수 파라미터 (기본값: 서울 시청 기준)
    getHospitals({ x: 126.9784, y: 37.5665 })
      .then(setHospitals)
      .catch(() => setHospitals([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
        <SafeAreaView style={styles.safe}>
          <LoadingSpinner message="병원 정보를 불러오고 있어요..." />
        </SafeAreaView>
      </LinearGradient>
    );
  }

  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>기본 대처 안내</Text>
        <Text style={styles.subtitle}>
          기본 대처법만 안내해드려요.{'\n'}
          정확한 진단과 처방은 반드시 수의사에게 문의하세요.
        </Text>

        <View style={styles.list}>
          {BASIC_INFO.map((item, idx) => (
            <Card key={idx} style={styles.infoCard}>
              <Text style={styles.infoIcon}>{item.icon}</Text>
              <View style={styles.infoContent}>
                <Text style={styles.infoTitle}>{item.title}</Text>
                <Text style={styles.infoDesc}>{item.desc}</Text>
              </View>
            </Card>
          ))}
        </View>

        <Card style={styles.warningCard}>
          <Text style={styles.warningText}>
            ⚠️ 이 정보는 참고용이며 의료 조언을 대체하지 않습니다.
            증상이 심각하면 즉시 동물병원에 방문하세요.
          </Text>
        </Card>

        {hospitals.length > 0 ? (
          <>
            <Text style={styles.sectionTitle}>주변 동물병원</Text>
            {hospitals.map((h, idx) => (
              <Card key={idx} style={styles.hospitalCard}>
                <Text style={styles.hospitalName}>{h.name}</Text>
                {h.address ? <Text style={styles.hospitalAddr}>{h.address}</Text> : null}
                {h.phone ? <Text style={styles.hospitalPhone}>📞 {h.phone}</Text> : null}
              </Card>
            ))}
          </>
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
  subtitle: { fontSize: 13, color: COLORS.textSecondary, textAlign: 'center', marginBottom: 24, lineHeight: 20 },
  list: { gap: 12, marginBottom: 16 },
  infoCard: { flexDirection: 'row', alignItems: 'flex-start', gap: 14, paddingVertical: 14 },
  infoIcon: { fontSize: 28, width: 36, textAlign: 'center' },
  infoContent: { flex: 1 },
  infoTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  infoDesc: { fontSize: 13, color: COLORS.textSecondary, lineHeight: 20 },
  warningCard: { backgroundColor: '#FFF8E8', borderColor: COLORS.warning, borderWidth: 1, marginBottom: 24 },
  warningText: { fontSize: 13, color: '#7A6020', lineHeight: 20 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  hospitalCard: { marginBottom: 10 },
  hospitalName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  hospitalAddr: { fontSize: 13, color: COLORS.textSecondary, marginBottom: 2 },
  hospitalPhone: { fontSize: 13, color: COLORS.cta, marginTop: 4 },
});
