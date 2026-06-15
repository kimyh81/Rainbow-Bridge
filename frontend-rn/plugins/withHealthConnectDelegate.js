// Health Connect를 Expo managed 워크플로에서 제대로 동작시키기 위한 커스텀 config plugin.
//
// react-native-health-connect가 기본 제공하는 plugin이 빠뜨리는 두 가지를 채운다:
//
// (1) MainActivity delegate 등록
//     requestPermission()이 동작하려면 MainActivity.onCreate에서
//     HealthConnectPermissionDelegate.setPermissionDelegate(this)를 호출해
//     ActivityResultLauncher를 미리 등록해야 한다. 없으면 권한 요청 시 네이티브 크래시.
//
// (2) 안드로이드 14(API 34)+ 권한 사용 안내 액티비티(activity-alias)
//     안드 14부터 Health Connect가 OS에 내장되면서, 앱이 Health Connect 앱 목록에
//     "표시"되고 권한창이 뜨려면 ViewPermissionUsageActivity alias가 필요하다.
//     라이브러리 plugin은 안드 13 이하용 ACTION_SHOW_PERMISSIONS_RATIONALE만 넣어준다.
//     이 alias가 없으면 안드 14+ 폰에서 앱이 Health Connect 목록에 아예 안 뜬다.

const { withMainActivity, withAndroidManifest } = require('@expo/config-plugins');

const IMPORT_LINE =
  'import dev.matinzd.healthconnect.permissions.HealthConnectPermissionDelegate';
const DELEGATE_CALL =
  '    HealthConnectPermissionDelegate.setPermissionDelegate(this)';

// (1) MainActivity에 delegate 등록 코드 주입
function withDelegate(config) {
  return withMainActivity(config, (config) => {
    const { language } = config.modResults;
    if (language !== 'kt') {
      throw new Error(
        `withHealthConnectDelegate: MainActivity가 Kotlin(.kt)이 아니라 ${language}예요. ` +
          'Expo 버전이 바뀌었을 수 있으니 plugin을 점검하세요.'
      );
    }

    let src = config.modResults.contents;

    // import 추가 (package 선언 바로 다음 줄, 중복 방지)
    if (!src.includes(IMPORT_LINE)) {
      src = src.replace(/^(package .*)$/m, `$1\n${IMPORT_LINE}`);
    }

    // super.onCreate(...) 직후 delegate 등록 (중복 방지)
    if (!src.includes('HealthConnectPermissionDelegate.setPermissionDelegate(this)')) {
      src = src.replace(
        /(\n[ \t]*super\.onCreate\([^)]*\))/,
        `$1\n${DELEGATE_CALL}`
      );
    }

    config.modResults.contents = src;
    return config;
  });
}

// (2) 안드 14+용 ViewPermissionUsageActivity alias 추가
function withViewPermissionUsageAlias(config) {
  return withAndroidManifest(config, (config) => {
    const application = config.modResults.manifest.application[0];
    application['activity-alias'] = application['activity-alias'] || [];

    const ALIAS_NAME = 'ViewPermissionUsageActivity';
    const exists = application['activity-alias'].some(
      (a) => a?.$?.['android:name'] === ALIAS_NAME
    );
    if (exists) return config;

    application['activity-alias'].push({
      $: {
        'android:name': ALIAS_NAME,
        'android:exported': 'true',
        'android:targetActivity': '.MainActivity',
        'android:permission': 'android.permission.START_VIEW_PERMISSION_USAGE',
      },
      'intent-filter': [
        {
          action: [
            { $: { 'android:name': 'android.intent.action.VIEW_PERMISSION_USAGE' } },
          ],
          category: [
            { $: { 'android:name': 'android.intent.category.HEALTH_PERMISSIONS' } },
          ],
        },
      ],
    });

    return config;
  });
}

module.exports = function withHealthConnect(config) {
  config = withDelegate(config);
  config = withViewPermissionUsageAlias(config);
  return config;
};
