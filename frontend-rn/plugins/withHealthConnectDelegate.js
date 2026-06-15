// Health Connect 권한 요청(requestPermission)이 동작하려면
// MainActivity.onCreate 안에서 HealthConnectPermissionDelegate.setPermissionDelegate(this)를
// 호출해 ActivityResultLauncher를 미리 등록해야 한다.
// (react-native-health-connect README 'MainActivity 설정' 참고)
//
// Expo managed 워크플로에서는 MainActivity가 prebuild로 자동 생성되므로,
// 이 config plugin이 prebuild 시점에 필요한 import와 delegate 등록 코드를 끼워넣는다.
// 이 한 줄이 없으면 requestPermission() 호출 시 네이티브 크래시(앱 강제 종료)가 난다.

const { withMainActivity } = require('@expo/config-plugins');

const IMPORT_LINE =
  'import dev.matinzd.healthconnect.permissions.HealthConnectPermissionDelegate';
const DELEGATE_CALL =
  '    HealthConnectPermissionDelegate.setPermissionDelegate(this)';

module.exports = function withHealthConnectDelegate(config) {
  return withMainActivity(config, (config) => {
    const { language } = config.modResults;
    if (language !== 'kt') {
      throw new Error(
        `withHealthConnectDelegate: MainActivity가 Kotlin(.kt)이 아니라 ${language}예요. ` +
          'Expo 버전이 바뀌었을 수 있으니 plugin을 점검하세요.'
      );
    }

    let src = config.modResults.contents;

    // 1) import 추가 (package 선언 바로 다음 줄, 중복 방지)
    if (!src.includes(IMPORT_LINE)) {
      src = src.replace(/^(package .*)$/m, `$1\n${IMPORT_LINE}`);
    }

    // 2) super.onCreate(...) 직후 delegate 등록 (중복 방지)
    if (!src.includes('HealthConnectPermissionDelegate.setPermissionDelegate(this)')) {
      src = src.replace(
        /(\n[ \t]*super\.onCreate\([^)]*\))/,
        `$1\n${DELEGATE_CALL}`
      );
    }

    config.modResults.contents = src;
    return config;
  });
};
