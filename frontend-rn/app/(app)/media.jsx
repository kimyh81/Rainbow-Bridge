import { useState, useRef, useEffect } from 'react';
import { Text, StyleSheet, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { Video, ResizeMode } from 'expo-av';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Card from '../../components/Card';
import Button from '../../components/Button';
import LoadingSpinner from '../../components/LoadingSpinner';
import { generateMedia, getMediaStatus } from '../../api/media';
import { API_URL } from '../../api/axiosInstance';
import { COLORS } from '../../constants/colors';

const POLL_INTERVAL = 5000;
const POLL_MAX = 60;

export default function MediaScreen() {
  const [videoUrl, setVideoUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');
  const pollRef = useRef(null);

  useEffect(() => () => clearTimeout(pollRef.current), []);

  async function handleGenerate() {
    clearTimeout(pollRef.current);
    setLoading(true);
    setError('');
    setVideoUrl(null);
    setStatusMsg('최적의 사진을 고르고 있어요...');
    try {
      const petId = await AsyncStorage.getItem('pet_id');
      if (!petId) {
        setError('반려동물 정보가 없어요. 먼저 프로필을 등록해주세요.');
        setLoading(false);
        return;
      }
      const { asset_id, selected_photo } = await generateMedia(petId);
      setStatusMsg(`${selected_photo ? `"${selected_photo}" 사진으로 ` : ''}추모 영상을 만들고 있어요... (최대 1~2분)`);
      pollStatus(asset_id, 0);
    } catch {
      setError('영상 생성에 실패했어요. 사진을 먼저 등록했는지 확인해주세요.');
      setLoading(false);
    }
  }

  function pollStatus(assetId, attempt) {
    pollRef.current = setTimeout(async () => {
      try {
        const res = await getMediaStatus(assetId);
        const url = res.video_url;
        if (res.status === 'done' && url) {
          const fullUrl = url.startsWith('http') ? url : `${API_URL}${url}`;
          setVideoUrl(fullUrl);
          await AsyncStorage.setItem('pet_video_url', fullUrl);
          await AsyncStorage.setItem('pet_video_asset_id', assetId);
          setLoading(false);
        } else if (res.status === 'error') {
          setError('영상 생성 중 문제가 생겼어요. 잠시 후 다시 시도해주세요.');
          setLoading(false);
        } else if (attempt >= POLL_MAX) {
          setError('영상 생성이 오래 걸리고 있어요. 잠시 후 다시 시도해주세요.');
          setLoading(false);
        } else {
          pollStatus(assetId, attempt + 1);
        }
      } catch {
        setError('상태 확인에 실패했어요. 다시 시도해주세요.');
        setLoading(false);
      }
    }, POLL_INTERVAL);
  }

  return (
    <LinearGradient colors={['#F9DFE6', '#EBDDF5', '#F0F4F8', '#E4DAF5']} locations={[0, 0.35, 0.6, 1]} style={styles.gradient}>
      <SafeAreaView style={styles.safe}>
        <ScrollView contentContainerStyle={styles.scroll}>
          <Text style={styles.title}>추모 영상 만들기</Text>
          <Text style={styles.subtitle}>
            등록된 사진 중 가장 잘 나온 사진으로{'\n'}소중한 기억을 영상으로 담아드려요.
          </Text>

          <View style={styles.infoCard}>
            <Text style={styles.infoText}>
              📸 사진 화면에서 사진을 먼저 등록해두면{'\n'}AI가 자동으로 가장 잘 나온 사진을 골라드려요.
            </Text>
          </View>

          {error ? <Text style={styles.error}>{error}</Text> : null}

          {loading ? (
            <LoadingSpinner message={statusMsg || '잠시만 기다려주세요...'} />
          ) : (
            <Button onPress={handleGenerate} variant="primary" style={styles.btn}>
              추모 영상 만들기
            </Button>
          )}

          {videoUrl ? (
            <Card style={styles.resultCard}>
              <Text style={styles.resultTitle}>🎞️ 추모 영상이 준비됐어요</Text>
              <Video
                source={{ uri: videoUrl }}
                style={styles.video}
                useNativeControls
                resizeMode={ResizeMode.CONTAIN}
                isLooping
                shouldPlay
              />
              <Text style={styles.disclaimer}>
                AI가 보호자가 전해준 기억을 바탕으로 재해석한 추모 영상이에요.
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
  infoText: { fontSize: 13, color: '#6B5B8A', lineHeight: 20, textAlign: 'center' },
  error: { color: COLORS.danger, fontSize: 13, textAlign: 'center', marginBottom: 12 },
  btn: { marginBottom: 16 },
  resultCard: { backgroundColor: '#F0F8F6', borderColor: COLORS.secondary, borderWidth: 1 },
  resultTitle: { fontSize: 15, fontWeight: '700', color: COLORS.textPrimary, marginBottom: 12 },
  video: { width: '100%', aspectRatio: 1, borderRadius: 12, backgroundColor: '#000' },
  disclaimer: { fontSize: 12, color: COLORS.textSecondary, marginTop: 10, lineHeight: 18 },
});
