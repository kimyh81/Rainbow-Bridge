import { useState, useEffect } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  Image, Alert, ActivityIndicator, Dimensions, ScrollView,
} from 'react-native';
import * as ImagePicker from 'expo-image-picker';
import { SafeAreaView } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { uploadMedia, deleteMedia } from '@/api/media';
import { COLORS } from '@/constants/colors';

const { width: SCREEN_W } = Dimensions.get('window');
// 좌우 패딩 40 + 셀 사이 간격 8(4*2) = 48
const CELL = Math.floor((SCREEN_W - 48) / 3);

export default function PhotosScreen() {
  const [photos, setPhotos] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [petName, setPetName] = useState('');

  useEffect(() => {
    AsyncStorage.getItem('pet_name').then(v => v && setPetName(v));
    loadPhotos();
  }, []);

  async function loadPhotos() {
    try {
      const raw = await AsyncStorage.getItem('pet_photos');
      if (raw) setPhotos(JSON.parse(raw));
    } catch {}
  }

  async function persist(list) {
    setPhotos(list);
    try { await AsyncStorage.setItem('pet_photos', JSON.stringify(list)); } catch {}
  }

  async function pickImage() {
    const perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (perm.status !== 'granted') {
      Alert.alert('권한 필요', '갤러리 접근 권한이 필요해요. 설정에서 허용해주세요.');
      return;
    }

    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ['images'],
      allowsMultipleSelection: true,
      quality: 0.85,
    });
    if (result.canceled) return;

    setUploading(true);

    const petId = await AsyncStorage.getItem('pet_id');
    const newPhotos = result.assets.map((asset) => ({
      id: `${Date.now()}_${asset.uri.slice(-8)}`,
      uri: asset.uri,
      uploadedAt: new Date().toISOString(),
      uploaded: false,
    }));

    const updated = [...newPhotos, ...photos];
    await persist(updated);

    // 각 사진 백엔드 업로드 (LivePortrait 파이프라인용)
    const uploadResults = await Promise.allSettled(
      newPhotos.map(async (photo) => {
        const formData = new FormData();
        formData.append('file', {
          uri: photo.uri,
          name: `pet_${Date.now()}.jpg`,
          type: 'image/jpeg',
        });
        if (petId) formData.append('pet_id', petId);
        formData.append('usage', 'liveportrait');
        const res = await uploadMedia(formData);
        return { id: photo.id, asset_id: res.asset_id };
      })
    );

    const succeededIds = new Map(
      uploadResults
        .filter((r) => r.status === 'fulfilled')
        .map((r) => [r.value.id, r.value.asset_id])
    );

    const final = updated.map((p) =>
      succeededIds.has(p.id)
        ? { ...p, asset_id: succeededIds.get(p.id), uploaded: true }
        : p
    );
    await persist(final);
    setUploading(false);

    const failCount = uploadResults.filter((r) => r.status === 'rejected').length;
    if (failCount > 0) {
      Alert.alert(
        '업로드 실패',
        `${failCount}장 업로드에 실패했어요.\n서버 연결 상태를 확인하고 다시 시도해주세요.`
      );
    }
  }

  function confirmDelete(photo) {
    Alert.alert('사진 삭제', '이 사진을 삭제할까요?', [
      { text: '취소', style: 'cancel' },
      {
        text: '삭제', style: 'destructive',
        onPress: async () => {
          if (photo.asset_id) {
            try { await deleteMedia(photo.asset_id); } catch {}
          }
          const updated = photos.filter(p => p.id !== photo.id);
          await persist(updated);
        },
      },
    ]);
  }

  function renderPhoto({ item }) {
    return (
      <TouchableOpacity
        style={[styles.cell, { width: CELL, height: CELL }]}
        onLongPress={() => confirmDelete(item)}
        activeOpacity={0.85}
        accessible
        accessibilityLabel={`사진 ${item.uploadedAt?.slice(0, 10) ?? ''}, 길게 눌러 삭제`}
      >
        <Image source={{ uri: item.uri }} style={styles.cellImg} />
        {!item.uploaded && (
          <View style={styles.uploadingOverlay}>
            <ActivityIndicator size="small" color="#fff" />
          </View>
        )}
        {item.uploaded && (
          <View style={styles.uploadedBadge}>
            <Text style={styles.uploadedBadgeText}>✓</Text>
          </View>
        )}
      </TouchableOpacity>
    );
  }

  const uploadedCount = photos.filter(p => p.uploaded).length;

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
          {/* 안내 카드 */}
          <View style={styles.tipCard}>
            <Text style={styles.tipIcon}>📸</Text>
            <View style={styles.tipBody}>
              <Text style={styles.tipTitle}>
                {petName ? `${petName}의 사진을 남겨요` : '사진을 남겨요'}
              </Text>
              <Text style={styles.tipDesc}>
                얼굴이 잘 나온 사진을 여러 장 올리면 나중에 더 자연스러운 추모 영상을 만들 수 있어요.
              </Text>
            </View>
          </View>

          {/* 업로드 현황 */}
          {photos.length > 0 && (
            <View style={styles.statsRow}>
              <Text style={styles.statsText}>
                총 {photos.length}장 · 서버 저장 {uploadedCount}장
              </Text>
            </View>
          )}

          {/* 사진 추가 버튼 */}
          <TouchableOpacity
            style={[styles.addBtn, uploading && { opacity: 0.6 }]}
            onPress={pickImage}
            disabled={uploading}
            activeOpacity={0.8}
          >
            {uploading ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Text style={styles.addBtnPlus}>＋</Text>
                <Text style={styles.addBtnText}>사진 추가</Text>
              </>
            )}
          </TouchableOpacity>

          {/* 갤러리 그리드 */}
          {photos.length > 0 ? (
            <FlatList
              data={photos}
              keyExtractor={item => item.id}
              renderItem={renderPhoto}
              numColumns={3}
              scrollEnabled={false}
              columnWrapperStyle={styles.gridRow}
              style={styles.grid}
            />
          ) : (
            <View style={styles.empty}>
              <Text style={styles.emptyIcon}>🖼️</Text>
              <Text style={styles.emptyText}>아직 사진이 없어요</Text>
              <Text style={styles.emptyHint}>위 버튼을 눌러 추가해보세요</Text>
            </View>
          )}

          {/* 촬영 팁 */}
          <View style={styles.guideCard}>
            <Text style={styles.guideTitle}>💡 좋은 사진 조건</Text>
            {[
              '눈·코·입이 정면으로 잘 보이는 사진',
              '밝고 선명한 사진 (흔들림 없이)',
              '3장 이상 올리면 더 자연스러운 영상이 돼요',
              '사진을 꾹 누르면 삭제할 수 있어요',
            ].map((t, i) => (
              <Text key={i} style={styles.guideItem}>• {t}</Text>
            ))}
          </View>
        </ScrollView>
      </SafeAreaView>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  gradient: { flex: 1 },
  safe: { flex: 1 },
  scroll: { padding: 20, paddingBottom: 48 },

  tipCard: {
    flexDirection: 'row', alignItems: 'flex-start', gap: 12,
    backgroundColor: '#FFFFFF',
    borderRadius: 18, padding: 16,
    borderWidth: 1.5, borderColor: '#E5DCF0',
    marginBottom: 14,
    shadowColor: '#8A7D9E', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08, shadowRadius: 6, elevation: 1,
  },
  tipIcon: { fontSize: 26, marginTop: 2 },
  tipBody: { flex: 1, gap: 4 },
  tipTitle: { fontSize: 14, fontWeight: '700', color: '#5B4E75' },
  tipDesc: { fontSize: 12, color: '#8A7D9E', lineHeight: 18 },

  statsRow: { marginBottom: 10 },
  statsText: { fontSize: 12, color: '#8A7D9E', textAlign: 'right' },

  addBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: '#E8DFF5',
    borderRadius: 14, paddingVertical: 14,
    marginBottom: 16,
    borderWidth: 3, borderColor: '#FFFFFF',
    shadowColor: '#E8DFF5', shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35, shadowRadius: 8, elevation: 4,
  },
  addBtnPlus: { fontSize: 22, color: '#333333', fontWeight: '700' },
  addBtnText: { fontSize: 15, color: '#333333', fontWeight: '700' },

  grid: { marginBottom: 4 },
  gridRow: { gap: 4, marginBottom: 4 },

  cell: {
    borderRadius: 10, overflow: 'hidden',
    backgroundColor: '#E5DCF0',
  },
  cellImg: { width: '100%', height: '100%' },
  uploadingOverlay: {
    position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'center', alignItems: 'center',
  },
  uploadedBadge: {
    position: 'absolute', top: 4, right: 4,
    backgroundColor: 'rgba(91,78,117,0.75)',
    borderRadius: 999, width: 18, height: 18,
    justifyContent: 'center', alignItems: 'center',
  },
  uploadedBadgeText: { fontSize: 10, color: '#fff', fontWeight: '700' },

  empty: { alignItems: 'center', paddingVertical: 44, gap: 10 },
  emptyIcon: { fontSize: 52 },
  emptyText: { fontSize: 16, fontWeight: '700', color: '#5B4E75' },
  emptyHint: { fontSize: 13, color: '#8A7D9E' },

  guideCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16, padding: 16,
    borderWidth: 1.5, borderColor: '#E5DCF0',
    marginTop: 16, gap: 6,
    shadowColor: '#8A7D9E', shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07, shadowRadius: 6, elevation: 1,
  },
  guideTitle: { fontSize: 14, fontWeight: '700', color: '#5B4E75', marginBottom: 4 },
  guideItem: { fontSize: 12, color: '#8A7D9E', lineHeight: 18 },
});
