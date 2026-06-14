import { useState, useEffect } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
} from 'react-native';
import { useRouter } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import SafetyModal from '@/components/SafetyModal';

function SectionCard({ emoji, title, accentColor, items }) {
  return (
    <View style={[styles.sectionCard, { borderLeftColor: accentColor }]}>
      <View style={styles.sectionHead}>
        <Text style={styles.sectionEmoji}>{emoji}</Text>
        <Text style={styles.sectionTitle}>{title}</Text>
      </View>
      <View style={styles.itemList}>
        {items.map((item, i) => (
          <View key={i} style={styles.itemRow}>
            <Text style={styles.itemIcon}>{item.icon}</Text>
            <View style={styles.itemTextWrap}>
              <Text style={styles.itemMain}>{item.main}</Text>
              {item.sub ? <Text style={styles.itemSub}>{item.sub}</Text> : null}
            </View>
          </View>
        ))}
      </View>
    </View>
  );
}

export default function FarewellScreen() {
  const router = useRouter();
  const [safetyOpen, setSafetyOpen] = useState(false);
  const [petName, setPetName] = useState('소중한 친구');

  useEffect(() => {
    AsyncStorage.getItem('pet_name').then(v => v && setPetName(v));
  }, []);

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
          <Text style={styles.logo}>🌈 레인보우 브릿지</Text>
          <Text style={styles.logoSub}>소중한 가족을 기억해요</Text>

          {/* 상단 인트로 */}
          <View style={styles.introCard}>
            <Text style={styles.introEmoji}>🕊️</Text>
            <Text style={styles.introTitle}>{petName}와(과)의 이별 안내</Text>
            <Text style={styles.introText}>
              지금 이 순간, 많이 힘드실 거예요.{'\n'}
              차분하게 한 단계씩 함께 해드릴게요.
            </Text>
          </View>

          {/* Section 1: 지금 해줘야 할 것들 */}
          <SectionCard
            emoji="🤲"
            title="지금 해줘야 할 것들"
            accentColor="#F0C8D8"
            items={[
              {
                icon: '🧸',
                main: '담요나 부드러운 천으로 감싸주세요',
                sub: '체온이 내려가면서 몸이 굳을 수 있어요',
              },
              {
                icon: '🫧',
                main: '눈과 항문 부위를 부드럽게 정리해 주세요',
                sub: '이완으로 분비물이 나올 수 있어요 — 자연스러운 현상이에요',
              },
              {
                icon: '❄️',
                main: '조용하고 서늘한 곳에 뉘어주세요',
                sub: '직사광선을 피하고 통풍이 잘 되는 곳이 좋아요',
              },
            ]}
          />

          {/* Section 2: 놀라지 마세요 */}
          <SectionCard
            emoji="🌿"
            title="놀라지 마세요"
            accentColor="#C4A8D8"
            items={[
              {
                icon: '⏱️',
                main: '몸이 굳어요',
                sub: '2~6시간 후 사후 경직이 옵니다. 자연스러운 현상이에요',
              },
              {
                icon: '🌡️',
                main: '체온이 빠르게 내려가요',
                sub: '방치된 게 아니에요. 정상적인 과정이에요',
              },
              {
                icon: '💧',
                main: '분비물이 나올 수 있어요',
                sub: '방광·장 이완으로 소변이나 분변이 나올 수 있어요',
              },
              {
                icon: '✨',
                main: '몸이 약간 움직일 수 있어요',
                sub: '신경 반사로 인한 움직임이에요. 통증이 있는 게 아니에요',
              },
            ]}
          />

          {/* Section 3: 장례 준비 */}
          <SectionCard
            emoji="🕊️"
            title="장례 준비"
            accentColor="#B8D0E8"
            items={[
              {
                icon: '⏰',
                main: '보통 24~48시간 이내를 권장해요',
                sub: '여름철이라면 더 빨리 진행하는 게 좋아요',
              },
              {
                icon: '🎀',
                main: '좋아하던 담요나 장난감을 함께 넣어줄 수 있어요',
                sub: '마지막 여행길에 소중한 것들을 함께 보내주세요',
              },
              {
                icon: '✅',
                main: '농림축산식품부 등록 업체인지 확인하세요',
                sub: '미등록 업체는 불법이며 분쟁이 생길 수 있어요',
              },
            ]}
          />

          {/* Section 4: 주변 장례식장 CTA */}
          <TouchableOpacity
            style={styles.funeralBtnWrap}
            onPress={() => router.push('/(app)/funeral')}
            activeOpacity={0.8}
          >
            <LinearGradient
              colors={['#E8DFF5', '#FCE1E4']}
              start={{ x: 0, y: 0 }}
              end={{ x: 1, y: 0 }}
              style={styles.funeralBtn}
            >
              <Text style={styles.funeralBtnEmoji}>📍</Text>
              <View style={styles.funeralBtnBody}>
                <Text style={styles.funeralBtnText}>주변 동물 장례식장 찾기</Text>
                <Text style={styles.funeralBtnSub}>거리순으로 안내해드려요</Text>
              </View>
              <Text style={styles.funeralBtnArrow}>›</Text>
            </LinearGradient>
          </TouchableOpacity>

          {/* Section 5: 보호자에게 */}
          <View style={styles.guardianCard}>
            <Text style={styles.guardianEmoji}>💜</Text>
            <Text style={styles.guardianTitle}>보호자님께</Text>
            <Text style={styles.guardianText}>
              충분히 슬퍼해도 됩니다.{'\n'}
              혼자 있지 마세요.{'\n\n'}
              {petName}와(과) 함께했던 시간은{'\n'}
              무엇과도 바꿀 수 없는 소중한 기억이에요.
            </Text>
            <TouchableOpacity
              style={styles.safetyBtnWrap}
              onPress={() => setSafetyOpen(true)}
              activeOpacity={0.8}
            >
              <Text style={styles.safetyBtnText}>💙 감정이 너무 힘드신가요?</Text>
              <Text style={styles.safetyBtnSub}>전문 상담사와 연결해드려요</Text>
            </TouchableOpacity>
          </View>
        </ScrollView>
      </SafeAreaView>
      <SafetyModal isOpen={safetyOpen} onClose={() => setSafetyOpen(false)} />
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  scroll: { paddingHorizontal: 20, paddingVertical: 32, paddingBottom: 48 },

  logo: { fontSize: 22, fontWeight: '700', color: '#5B4E75', textAlign: 'center', marginBottom: 4 },
  logoSub: { fontSize: 13, color: '#8A7D9E', textAlign: 'center', marginBottom: 24 },

  introCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 24,
    alignItems: 'center',
    marginBottom: 20,
    borderWidth: 1.5,
    borderColor: '#E5DCF0',
    shadowColor: '#8A7D9E',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 2,
  },
  introEmoji: { fontSize: 40, marginBottom: 12 },
  introTitle: {
    fontSize: 17, fontWeight: '800', color: '#5B4E75',
    marginBottom: 10, textAlign: 'center',
  },
  introText: { fontSize: 14, color: '#8A7D9E', textAlign: 'center', lineHeight: 22 },

  sectionCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 18,
    padding: 20,
    marginBottom: 14,
    borderWidth: 1.5,
    borderColor: '#E5DCF0',
    borderLeftWidth: 4,
    shadowColor: '#8A7D9E',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  sectionHead: {
    flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 16,
  },
  sectionEmoji: { fontSize: 20 },
  sectionTitle: { fontSize: 15, fontWeight: '800', color: '#5B4E75' },
  itemList: { gap: 14 },
  itemRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  itemIcon: { fontSize: 18, marginTop: 1, width: 24, textAlign: 'center' },
  itemTextWrap: { flex: 1 },
  itemMain: { fontSize: 14, fontWeight: '600', color: '#4A4A4A', lineHeight: 20 },
  itemSub: { fontSize: 12, color: '#8A7D9E', marginTop: 3, lineHeight: 17 },

  funeralBtnWrap: {
    shadowColor: '#B8D0E8',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.4,
    shadowRadius: 10,
    elevation: 3,
    marginBottom: 20,
  },
  funeralBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    borderRadius: 18,
    paddingVertical: 18,
    paddingHorizontal: 20,
    gap: 12,
  },
  funeralBtnEmoji: { fontSize: 24 },
  funeralBtnBody: { flex: 1 },
  funeralBtnText: { fontSize: 15, fontWeight: '700', color: '#5B4E75' },
  funeralBtnSub: { fontSize: 12, color: '#8A7D9E', marginTop: 2 },
  funeralBtnArrow: { fontSize: 22, color: '#C4A8D8' },

  guardianCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 20,
    padding: 24,
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: '#D4C0E0',
    shadowColor: '#C4A8D8',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.10,
    shadowRadius: 8,
    elevation: 2,
    marginBottom: 16,
  },
  guardianEmoji: { fontSize: 36, marginBottom: 12 },
  guardianTitle: { fontSize: 16, fontWeight: '800', color: '#5B4E75', marginBottom: 14 },
  guardianText: {
    fontSize: 14, color: '#5B4E75', textAlign: 'center',
    lineHeight: 24, marginBottom: 20,
  },
  safetyBtnWrap: {
    backgroundColor: 'rgba(196,168,216,0.12)',
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: '#D4C0E0',
    paddingVertical: 14,
    paddingHorizontal: 24,
    alignItems: 'center',
    gap: 4,
    width: '100%',
  },
  safetyBtnText: { fontSize: 14, fontWeight: '700', color: '#5B4E75' },
  safetyBtnSub: { fontSize: 12, color: '#8A7D9E' },
});
