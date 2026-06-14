import { Modal, View, Text, TouchableOpacity, Linking, StyleSheet } from 'react-native';
import { COLORS } from '@/constants/colors';

// 1393 위기상담 모달 — 번호 절대 변경 금지
export default function SafetyModal({ isOpen, onClose }) {
  function handleCall() {
    Linking.openURL('tel:1393');
  }

  return (
    <Modal
      visible={isOpen}
      transparent
      animationType="fade"
      onRequestClose={onClose}
    >
      <View style={styles.overlay}>
        <View style={styles.box}>
          <Text style={styles.icon}>⚠️</Text>
          <Text style={styles.title}>힘드신가요?</Text>
          <Text style={styles.body}>
            지금 많이 힘드시다면{'\n'}
            전문가와 이야기해보세요.
          </Text>

          <TouchableOpacity style={styles.callButton} onPress={handleCall} activeOpacity={0.85}>
            <Text style={styles.callText}>📞 정신건강 위기상담 1393</Text>
          </TouchableOpacity>

          <TouchableOpacity onPress={onClose} style={styles.closeArea}>
            <Text style={styles.closeText}>닫기</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 24,
  },
  box: {
    backgroundColor: COLORS.white,
    borderRadius: 24,
    padding: 28,
    width: '100%',
    maxWidth: 340,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.2,
    shadowRadius: 24,
    elevation: 10,
  },
  icon: {
    fontSize: 48,
    marginBottom: 12,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    color: COLORS.danger,
    marginBottom: 8,
  },
  body: {
    fontSize: 15,
    color: COLORS.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 24,
  },
  callButton: {
    backgroundColor: COLORS.danger,
    borderRadius: 14,
    paddingVertical: 14,
    paddingHorizontal: 24,
    width: '100%',
    alignItems: 'center',
    marginBottom: 12,
    shadowColor: COLORS.danger,
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 4,
  },
  callText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
  closeArea: {
    paddingVertical: 8,
  },
  closeText: {
    color: COLORS.textLight,
    fontSize: 14,
  },
});
