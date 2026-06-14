import { useState, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, ScrollView, ActivityIndicator,
} from 'react-native';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { LinearGradient } from 'expo-linear-gradient';
import Card from '@/components/Card';
import { createPet } from '@/api/pets';
import { COLORS } from '@/constants/colors';
import { gwa } from '@/utils/josa';

const INITIAL_ENTRIES = [
  { keyword: '', detail: '' },
  { keyword: '', detail: '' },
  { keyword: '', detail: '' },
];

export default function MemoriesScreen() {
  const router = useRouter();
  const { profile: profileStr } = useLocalSearchParams();
  const profile = profileStr ? JSON.parse(profileStr) : null;

  const [entries, setEntries] = useState(INITIAL_ENTRIES);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  function updateEntry(index, field, value) {
    setEntries(prev => prev.map((e, i) => i === index ? { ...e, [field]: value } : e));
  }

  async function handleSubmit() {
    const filled = entries.filter(e => e.keyword.trim() || e.detail.trim());
    if (filled.length === 0) {
      setError('추억 키워드를 하나 이상 입력해주세요.');
      return;
    }
    setError('');
    setLoading(true);

    const memories = filled.map(e => ({
      keyword: e.keyword.trim(),
      detail: e.detail.trim(),
    }));
    const callerName = profile.guardian_title?.trim() || '보호자';

    try {
      const payload = {
        name: profile.name.trim(),
        species: profile.species,
        gender: profile.gender,
        period: `${profile.start_date} ~ ${profile.end_date}`,
        caller_name: callerName,
        bucket_list: [],
        memories,
      };
      const pet = await createPet(payload);
      await AsyncStorage.setItem('pet_id', String(pet.id || pet._id || ''));
      await AsyncStorage.setItem('pet_name', pet.name || profile.name.trim());
      await AsyncStorage.setItem('pet_species', profile.species || '');
    } catch {
      // 백엔드 연결 실패 시 로컬에만 저장하고 진행
      await AsyncStorage.setItem('pet_name', profile.name.trim());
      await AsyncStorage.setItem('pet_species', profile.species || '');
    } finally {
      // 호칭·이름·성별·기간 항상 저장
      await AsyncStorage.setItem('caller_name', callerName);
      if (profile.caller_name?.trim()) {
        await AsyncStorage.setItem('caller_name', profile.caller_name.trim());
      }
      await AsyncStorage.setItem('pet_guardian_title', profile.guardian_title?.trim() || '');
      await AsyncStorage.setItem('pet_gender', profile.gender || '');
      if (profile.start_date) await AsyncStorage.setItem('pet_start_date', profile.start_date);
      if (profile.end_date) await AsyncStorage.setItem('pet_farewell_date', profile.end_date);
      setLoading(false);
      router.replace('/(app)/home');
    }
  }

  useEffect(() => {
    if (!profile) router.replace('/(app)/profile');
  }, []);

  if (!profile) return null;

  return (
    <LinearGradient
      colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']}
      locations={[0, 0.35, 0.6, 1]}
      style={styles.gradient}
    >
      <SafeAreaView style={styles.safe}>
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
        >
          <Text style={styles.logo}>🌈 레인보우 브릿지</Text>
          <Text style={styles.subtitle}>소중한 가족을 기억해요</Text>

          <Card style={styles.card}>
            <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
              <Text style={styles.backText}>← 이전</Text>
            </TouchableOpacity>

            <Text style={styles.cardTitle}>추억 키워드 입력</Text>
            <Text style={styles.cardDesc}>
              {profile.name}{gwa(profile.name)} 나눈 소중한 기억을 알려주세요. (최대 3개)
            </Text>

            {entries.map((entry, i) => (
              <View key={i} style={styles.entryGroup}>
                <TextInput
                  style={styles.input}
                  value={entry.keyword}
                  onChangeText={v => updateEntry(i, 'keyword', v)}
                  placeholder={`추억 키워드 ${i + 1} (예: 공원 산책)`}
                  placeholderTextColor="#A89FBC"
                />
                <TextInput
                  style={[styles.input, styles.detailInput]}
                  value={entry.detail}
                  onChangeText={v => updateEntry(i, 'detail', v)}
                  placeholder="상세 내용 (예: 저녁마다 한강공원 같이 걸었어요)"
                  placeholderTextColor="#A89FBC"
                  multiline
                  numberOfLines={2}
                  textAlignVertical="top"
                />
              </View>
            ))}

            {error ? <Text style={styles.error}>{error}</Text> : null}

            {loading ? (
              <View style={styles.loadingRow}>
                <ActivityIndicator color={COLORS.cta} />
                <Text style={styles.loadingText}>저장 중이에요...</Text>
              </View>
            ) : (
              <TouchableOpacity activeOpacity={0.8} style={styles.btnShadow} onPress={handleSubmit}>
                <LinearGradient
                  colors={['#E8DFF5', '#FCE1E4']}
                  start={{ x: 0, y: 0 }}
                  end={{ x: 1, y: 0 }}
                  style={styles.btn}
                >
                  <Text style={styles.btnText}>시작하기</Text>
                </LinearGradient>
              </TouchableOpacity>
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
  scroll: { paddingHorizontal: 20, paddingVertical: 32 },
  logo: { fontSize: 22, fontWeight: '700', color: '#5B4E75', textAlign: 'center', marginBottom: 4 },
  subtitle: { fontSize: 13, color: '#8A7D9E', textAlign: 'center', marginBottom: 24 },
  card: { marginTop: 4 },
  backBtn: { marginBottom: 16 },
  backText: { fontSize: 14, color: '#8A7D9E' },
  cardTitle: { fontSize: 17, fontWeight: '700', color: '#5B4E75', marginBottom: 6 },
  cardDesc: { fontSize: 13, color: '#8A7D9E', marginBottom: 20, lineHeight: 20 },
  entryGroup: {
    marginBottom: 16,
    gap: 8,
  },
  input: {
    backgroundColor: '#FFFFFF',
    borderRadius: 14,
    borderWidth: 1.5,
    borderColor: '#E5DCF0',
    paddingHorizontal: 16,
    paddingVertical: 14,
    fontSize: 14,
    color: '#4A4A4A',
    shadowColor: '#8A7D9E',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 6,
    elevation: 1,
  },
  detailInput: {
    minHeight: 64,
    paddingTop: 12,
  },
  error: { color: COLORS.danger, fontSize: 13, textAlign: 'center', marginBottom: 12 },
  loadingRow: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 10, paddingVertical: 12 },
  loadingText: { fontSize: 14, color: '#8A7D9E' },
  btnShadow: {
    marginTop: 8,
    shadowColor: '#DAEAF6',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.5,
    shadowRadius: 10,
    elevation: 4,
  },
  btn: {
    height: 54,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  btnText: {
    color: '#5B4E75',
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 0.3,
  },
});
