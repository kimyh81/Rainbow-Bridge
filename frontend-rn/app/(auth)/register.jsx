import { useState } from 'react';
import {
  StyleSheet, Text, View, TextInput, TouchableOpacity,
  Image, ScrollView, Platform, ActivityIndicator,
} from 'react-native';
import { useRouter, Link } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { register } from '@/api/auth';

export default function RegisterScreen() {
  const router = useRouter();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleRegister() {
    if (!name.trim() || !email.trim() || !password.trim()) {
      setError('모든 항목을 입력해주세요.');
      return;
    }
    if (password.length < 6) {
      setError('비밀번호는 6자 이상 입력해주세요.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      await register({ name: name.trim(), email: email.trim(), password });
      // 신규 가입자 플래그 — login.jsx에서 profile.jsx로 강제 이동할 때 사용
      await AsyncStorage.setItem('new_registration', 'true');
      router.replace('/(auth)/login');
    } catch (err) {
      setError(err.response?.data?.detail || '회원가입 중 오류가 발생했어요.');
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
        <ScrollView
          contentContainerStyle={styles.innerContainer}
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
              <Text style={styles.koreanTitle}>회원가입</Text>
              <Text style={styles.koreanSubtitle}>레인보우 브릿지와 함께해요</Text>
            </View>

            <TextInput
              style={styles.input}
              value={name}
              onChangeText={setName}
              placeholder="이름"
              placeholderTextColor="#A89FBC"
              autoCorrect={false}
            />
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
              placeholder="비밀번호 (6자 이상)"
              placeholderTextColor="#A89FBC"
              secureTextEntry
            />

            {error ? <Text style={styles.error}>{error}</Text> : null}

            <TouchableOpacity
              activeOpacity={0.8}
              style={styles.buttonShadow}
              onPress={handleRegister}
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
                  : <Text style={styles.loginButtonText}>회원가입</Text>
                }
              </LinearGradient>
            </TouchableOpacity>

            <View style={styles.footerContainer}>
              <Text style={styles.footerText}>이미 계정이 있으신가요? </Text>
              <Link href="/(auth)/login" asChild>
                <TouchableOpacity activeOpacity={0.6}>
                  <Text style={styles.signupText}>로그인</Text>
                </TouchableOpacity>
              </Link>
            </View>
          </View>
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  safeArea: { flex: 1 },
  innerContainer: { flexGrow: 1 },

  imageWrapper: {
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 30,
    paddingBottom: 20,
  },
  mainImage: {
    width: 220,
    height: 220,
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
    marginBottom: 20,
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
    height: 54,
    borderRadius: 16,
    paddingHorizontal: 22,
    fontSize: 16,
    color: '#4A4A4A',
    marginBottom: 12,
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
    marginTop: 4,
    shadowColor: '#DAEAF6',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.5,
    shadowRadius: 10,
    elevation: 4,
  },
  loginButton: {
    width: '100%',
    height: 54,
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loginButtonText: {
    color: '#5B4E75',
    fontSize: 17,
    fontWeight: 'bold',
    letterSpacing: 0.5,
  },
  footerContainer: {
    flexDirection: 'row',
    marginTop: 14,
    alignItems: 'center',
  },
  footerText: { fontSize: 14, color: '#8A7D9E' },
  signupText: { fontSize: 14, fontWeight: 'bold', color: '#5B4E75' },
});
