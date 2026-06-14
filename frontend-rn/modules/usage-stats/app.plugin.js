const { withAndroidManifest } = require('@expo/config-plugins');

// PACKAGE_USAGE_STATS는 일반 권한이 아닌 특수 권한이라 AndroidManifest에 직접 추가 필요
module.exports = function withUsageStats(config) {
  return withAndroidManifest(config, (config) => {
    const manifest = config.modResults.manifest;
    if (!manifest['uses-permission']) manifest['uses-permission'] = [];

    const perms = manifest['uses-permission'];
    const perm = 'android.permission.PACKAGE_USAGE_STATS';
    if (!perms.some((p) => p.$?.['android:name'] === perm)) {
      perms.push({
        $: {
          'android:name': perm,
          'tools:ignore': 'ProtectedPermissions',
        },
      });
    }
    return config;
  });
};
