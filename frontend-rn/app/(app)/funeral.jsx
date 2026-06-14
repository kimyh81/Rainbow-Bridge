import { useState, useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, TouchableOpacity } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import Card from '@/components/Card';
import LoadingSpinner from '@/components/LoadingSpinner';
import { getFunerals } from '@/api/funerals';
import { COLORS } from '@/constants/colors';

const FAQ = [
  {
    q: '반려동물 장례는 어떻게 진행되나요?',
    a: '전문 장례사가 방문하거나 장례식장을 이용할 수 있어요. 화장 후 유골함을 받거나 수목장, 해양장 등 다양한 방법을 선택할 수 있습니다.',
  },
  {
    q: '비용은 얼마나 드나요?',
    a: '반려동물 크기와 장례 방식에 따라 다르며, 보통 10~50만원 정도입니다. 정확한 금액은 각 업체에 문의하세요.',
  },
  {
    q: '유골은 어떻게 보관할 수 있나요?',
    a: '유골함으로 보관하거나, 수목장(나무에 묻기), 해양장(바다에 뿌리기) 등을 선택할 수 있습니다.',
  },
  {
    q: '장례식장 선택 시 주의사항은?',
    a: '농림축산식품부 등록 업체인지 확인하세요. 미등록 업체는 불법이며 분쟁이 생길 수 있습니다.',
  },
];

export default function FuneralScreen() {
  const [funerals, setFunerals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [openFaq, setOpenFaq] = useState(null);

  useEffect(() => {
    getFunerals()
      .then(setFunerals)
      .catch(() => setFunerals([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
        <SafeAreaView style={styles.safe}>
          <LoadingSpinner message="장례 정보를 불러오고 있어요..." />
        </SafeAreaView>
      </LinearGradient>
    );
  }

  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
    <SafeAreaView style={styles.safe}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <Text style={styles.title}>장례 안내</Text>
        <Text style={styles.subtitle}>소중한 가족을 정성스럽게 보내드려요.</Text>

        {/* FAQ */}
        <Text style={styles.sectionTitle}>자주 묻는 질문</Text>
        <View style={styles.faqList}>
          {FAQ.map((item, idx) => (
            <Card key={idx} style={styles.faqCard}>
              <TouchableOpacity
                onPress={() => setOpenFaq(openFaq === idx ? null : idx)}
                activeOpacity={0.8}
                style={styles.faqQ}
              >
                <Text style={styles.faqQText}>Q. {item.q}</Text>
                <Text style={styles.faqToggle}>{openFaq === idx ? '▲' : '▼'}</Text>
              </TouchableOpacity>
              {openFaq === idx ? (
                <Text style={styles.faqA}>{item.a}</Text>
              ) : null}
            </Card>
          ))}
        </View>

        {/* 장례식장 목록 */}
        {funerals.length > 0 ? (
          <>
            <Text style={styles.sectionTitle}>주변 장례식장</Text>
            {funerals.map((f, idx) => (
              <Card key={idx} style={styles.funeralCard}>
                <Text style={styles.funeralName}>{f.name}</Text>
                {f.address ? <Text style={styles.funeralAddr}>{f.address}</Text> : null}
                {f.phone ? <Text style={styles.funeralPhone}>📞 {f.phone}</Text> : null}
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
  subtitle: { fontSize: 14, color: COLORS.textSecondary, textAlign: 'center', marginBottom: 28 },
  sectionTitle: { fontSize: 16, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12, marginTop: 8 },
  faqList: { gap: 10, marginBottom: 24 },
  faqCard: { paddingVertical: 14 },
  faqQ: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  faqQText: { fontSize: 14, fontWeight: '600', color: COLORS.textPrimary, flex: 1, paddingRight: 8 },
  faqToggle: { fontSize: 12, color: COLORS.textSecondary },
  faqA: { fontSize: 13, color: COLORS.textSecondary, marginTop: 10, lineHeight: 20 },
  funeralCard: { marginBottom: 10 },
  funeralName: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 4 },
  funeralAddr: { fontSize: 13, color: COLORS.textSecondary, marginBottom: 2 },
  funeralPhone: { fontSize: 13, color: COLORS.cta, marginTop: 4 },
});
