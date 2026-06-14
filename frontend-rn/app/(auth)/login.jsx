import { useState } from 'react';
import {
  StyleSheet, Text, View, TextInput, TouchableOpacity,
  Image, KeyboardAvoidingView, Platform, ActivityIndicator, ScrollView,
} from 'react-native';
import { useRouter, Link } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { LinearGradient } from 'expo-linear-gradient';
import { login } from '@/api/auth';
import { getMyPets } from '@/api/pets';

export default function LoginScreen() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (!email.trim() || !password.trim()) {
      setError('이메일과 비밀번호를 입력해주세요.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const { access_token } = await login({ email: email.trim(), password });
      await AsyncStorage.setItem('access_token', access_token);

      // 신규 가입자 플래그 확인 — 있으면 기존 데이터 무시하고 프로필 등록으로
      const isNewRegistration = await AsyncStorage.getItem('new_registration');
      if (isNewRegistration === 'true') {
        await AsyncStorage.multiRemove([
          'new_registration',
          'pet_id', 'pet_name', 'pet_species', 'caller_name',
          'bucketlist_items', 'diary_entries', 'pet_photos',
          'recovery_cache', 'pet_farewell_date', 'memorial_mode',
          'pet_guardian_title', 'pet_gender', 'pet_start_date',
        ]);
        router.replace('/(app)/profile');
        return;
      }

      // 재방문자: 이 계정의 펫이 이미 있는지 API로 확인
      await AsyncStorage.multiRemove(['pet_id', 'pet_name', 'pet_species', 'bucketlist_items', 'diary_entries']);
      let hasPet = false;
      try {
        const raw = await getMyPets();
        // 배열 직접 or { pets: [...] } or { data: [...] } 형식 모두 처리
        const petList = Array.isArray(raw) ? raw : (raw?.pets ?? raw?.data ?? []);
        if (petList.length > 0) {
          const pet = petList[0];
          await AsyncStorage.setItem('pet_id', String(pet.id || pet._id || ''));
          await AsyncStorage.setItem('pet_name', pet.name || '');
          await AsyncStorage.setItem('pet_species', pet.species || '');
          // 호칭·이별날짜도 복원 — 재방문자가 다시 프로필 입력 안 해도 되게
          if (pet.caller_name) {
            await AsyncStorage.setItem('caller_name', pet.caller_name);
          }
          if (pet.gender) {
            await AsyncStorage.setItem('pet_gender', pet.gender);
          }
          if (pet.period) {
            const parts = pet.period.split('~');
            const startPart = parts[0]?.trim();
            const endPart = parts[1]?.trim();
            if (startPart) await AsyncStorage.setItem('pet_start_date', startPart);
            if (endPart) await AsyncStorage.setItem('pet_farewell_date', endPart);
          }
          hasPet = true;
        }
      } catch { /* 펫 없음 → 프로필 등록으로 */ }

      router.replace(hasPet ? '/(app)/home' : '/(app)/profile');
    } catch (err) {
      setError(err.response?.data?.detail || '이메일 또는 비밀번호를 확인해주세요.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <LinearGradient
      colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']}
      locations={[0, 0.35, 0.6, 1]}
      style={styles.container}
    >
      <SafeAreaView style={styles.safeArea}>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          style={styles.innerContainer}
        >
          <ScrollView
            contentContainerStyle={styles.scrollContent}
            keyboardShouldPersistTaps="handled"
            showsVerticalScrollIndicator={false}
          >
          {/* 상단 이미지 영역 */}
          <View style={styles.imageWrapper}>
            <Image
              source={require('../../assets/last-photo.jpeg')}
              style={styles.mainImage}
            />
          </View>

          {/* 하단 폼 영역 */}
          <View style={styles.bottomFormWrapper}>
            <View style={styles.textContainer}>
              <Text style={styles.koreanTitle}>레인보우 브릿지</Text>
              <Text style={styles.koreanSubtitle}>소중한 기억을 간직해요</Text>
            </View>

            <TextInput
              style={styles.input}
              value={email}
              onChangeText={setEmail}
              placeholder="이메일"
              placeholderTextColor="#A89FBC"
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
            />
            <TextInput
              style={styles.input}
              value={password}
              onChangeText={setPassword}
              placeholder="비밀번호"
              placeholderTextColor="#A89FBC"
              secureTextEntry
            />

            {error ? <Text style={styles.error}>{error}</Text> : null}

            <TouchableOpacity
              activeOpacity={0.8}
              style={styles.buttonShadow}
              onPress={handleLogin}
              disabled={loading}
            >
              <LinearGradient
                colors={['#DDEDEA', '#DAEAF6']}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 0 }}
                style={styles.loginButton}
              >
                {loading
                  ? <ActivityIndicator color="#5B4E75" />
                  : <Text style={styles.loginButtonText}>로그인</Text>
                }
              </LinearGradient>
            </TouchableOpacity>

            <View style={styles.footerContainer}>
              <Text style={styles.footerText}>아직 계정이 없으신가요? </Text>
              <Link href="/(auth)/register" asChild>
                <TouchableOpacity activeOpacity={0.6}>
                  <Text style={styles.signupText}>회원가입</Text>
                </TouchableOpacity>
              </Link>
            </View>
          </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  safeArea: { flex: 1 },
  innerContainer: { flex: 1 },
  scrollContent: { flexGrow: 1 },

  imageWrapper: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 40,
    paddingBottom: 20,
  },
  mainImage: {
    width: 260,
    height: 260,
    borderRadius: 40,
    resizeMode: 'cover',
    shadowColor: '#C4D4E8',
    shadowOffset: { width: 0, height: 12 },
    shadowOpacity: 0.4,
    shadowRadius: 20,
    elevation: 8,
  },

  bottomFormWrapper: {
    paddingHorizontal: 28,
    paddingBottom: 40,
    alignItems: 'center',
  },
  textContainer: {
    alignItems: 'center',
    marginBottom: 32,
  },
  koreanTitle: {
    fontSize: 26,
    fontWeight: '800',
    color: '#5B4E75',
    marginBottom: 6,
  },
  koreanSubtitle: {
    fontSize: 14,
    fontWeight: '500',
    color: '#8A7D9E',
  },
  input: {
    backgroundColor: '#FFFFFF',
    width: '100%',
    height: 56,
    borderRadius: 16,
    paddingHorizontal: 22,
    fontSize: 16,
    color: '#4A4A4A',
    marginBottom: 14,
    shadowColor: '#8A7D9E',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 5,
    elevation: 1,
  },
  error: {
    color: '#E57373',
    fontSize: 13,
    textAlign: 'center',
    marginBottom: 8,
  },
  buttonShadow: {
    width: '100%',
    marginTop: 8,
    shadowColor: '#DAEAF6',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.5,
    shadowRadius: 10,
    elevation: 4,
  },
  loginButton: {
    width: '100%',
    height: 56,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loginButtonText: {
    color: '#5B4E75',
    fontSize: 18,
    fontWeight: 'bold',
    letterSpacing: 0.5,
  },
  footerContainer: {
    flexDirection: 'row',
    marginTop: 12,
    alignItems: 'center',
  },
  footerText: { fontSize: 14, color: '#8A7D9E' },
  signupText: { fontSize: 14, fontWeight: 'bold', color: '#5B4E75' },
});
