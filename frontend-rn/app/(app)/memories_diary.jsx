import { useState } from 'react';
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

export default function MemoriesDiaryScreen() {
  const router = useRouter();
  const { profile: profileStr } = useLocalSearchParams();
  const profile = profileStr ? JSON.parse(profileStr) : null;

  const [bucketlist, setBucketlist] = useState('');
  const [diaryMemo, setDiaryMemo] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit() {
    if (!bucketlist.trim() && !diaryMemo.trim()) {
      setError('버킷리스트 또는 추억 메모를 하나 이상 입력해주세요.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const payload = {
        name: profile.name.trim(),
        species: profile.species,
        period: `${profile.start_date} ~ ${profile.end_date}`,
        caller_name: profile.guardian_title?.trim() || '보호자',
        bucket_list: bucketlist.trim()
          ? bucketlist.trim().split(/[,\/\n]+/).map(s => s.trim()).filter(Boolean)
          : [],
        memories: diaryMemo.trim()
          ? [{ keyword: '추억 메모', detail: diaryMemo.trim() }]
          : [],
      };
      const pet = await createPet(payload);
      await AsyncStorage.setItem('pet_id', pet.id || pet._id);
      await AsyncStorage.setItem('pet_name', pet.name);
      await AsyncStorage.setItem('pet_species', profile.species || '');
      router.replace('/(app)/home');
    } catch {
      setError('저장 중 오류가 발생했어요. 다시 시도해주세요.');
    } finally {
      setLoading(false);
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

            <Text style={styles.cardTitle}>추억 기록</Text>
            <Text style={styles.cardDesc}>
              {profile.name}와(과) 나눈 소중한 기억을 알려주세요.
            </Text>

            <View style={styles.field}>
              <Text style={styles.label}>버킷리스트</Text>
              <Text style={styles.hint}>함께 하고 싶었거나 해주고 싶은 것들을 적어주세요</Text>
              <TextInput
                style={[styles.input, styles.multiline]}
                value={bucketlist}
                onChangeText={setBucketlist}
                placeholder={'예) 같이 해 뜨는 거 보기 / 바다 보여주기'}
                placeholderTextColor="#A89FBC"
                multiline
                numberOfLines={4}
                textAlignVertical="top"
              />
            </View>

            <View style={styles.field}>
              <Text style={styles.label}>일기·추억 메모</Text>
              <Text style={styles.hint}>함께했던 소중한 순간을 자유롭게 적어주세요</Text>
              <TextInput
                style={[styles.input, styles.multiline]}
                value={diaryMemo}
                onChangeText={setDiaryMemo}
                placeholder={'예) 엄마가 새벽에 물 갈아주던 것 / 퇴근하면 현관에서 기다림'}
                placeholderTextColor="#A89FBC"
                multiline
                numberOfLines={4}
                textAlignVertical="top"
              />
            </View>

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
                  <Text style={styles.btnText}>홈으로</Text>
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
  field: { marginBottom: 20 },
  label: { fontSize: 14, fontWeight: '600', color: '#5B4E75', marginBottom: 4 },
  hint: { fontSize: 12, color: '#A89FBC', marginBottom: 8 },
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
  multiline: { minHeight: 100, paddingTop: 14 },
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
