# iOS EAS Build 가이드 — 레인보우 브릿지

> 처음 하는 분도 따라할 수 있도록 단계별로 작성했습니다.  
> 막히는 부분 있으면 세종님한테 물어보세요!

---

## 준비물

- [ ] Apple Developer 계정 ID/PW (세종님한테 받기)
- [ ] Node.js 설치 확인 (`node --version`)
- [ ] 이 레포 클론 + `frontend-rn` 폴더

---

## 1단계. EAS CLI 설치

터미널에서 아래 명령어 실행:

```bash
npm install -g eas-cli
```

설치 확인:
```bash
eas --version
# eas-cli/x.x.x 이런 식으로 나오면 성공
```

---

## 2단계. Expo 계정 로그인

```bash
eas login
```

- Email, Password 입력하면 됩니다
- expo.dev 계정이 없으면 → https://expo.dev/signup 에서 무료 가입 후 진행

로그인 확인:
```bash
eas whoami
# 본인 expo 계정 이메일이 나오면 성공
```

---

## 3단계. 프로젝트 폴더로 이동

```bash
cd frontend-rn
```

---

## 4단계. EAS 프로젝트 연결

```bash
eas init
```

- "Which account should own this project?" → 본인 expo 계정 선택
- "Would you like to create a project?" → Y
- 완료되면 `app.json`에 `projectId`가 자동으로 추가됩니다

---

## 5단계. eas.json 생성

```bash
eas build:configure
```

`frontend-rn/eas.json` 파일이 생성됩니다. 내용 확인:

```json
{
  "cli": {
    "version": ">= 12.0.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal"
    },
    "production": {}
  }
}
```

---

## 6단계. iOS 빌드 실행

```bash
eas build --platform ios --profile preview
```

처음 실행하면 Apple Developer 계정 연결을 물어봅니다:

```
? What would you like to do?
❯ Use my Apple Developer account   ← 이거 선택
  Skip for now

? Enter your Apple ID: [Apple ID 입력]
? Enter your password: [비밀번호 입력]
```

이후 자동으로:
- 인증서(Certificate) 생성
- 프로비저닝 프로파일(Provisioning Profile) 생성
- 빌드 시작 (EAS 클라우드에서 진행, 약 10~20분 소요)

---

## 7단계. 빌드 완료 확인

빌드가 시작되면 링크가 나옵니다:

```
Build details: https://expo.dev/accounts/.../builds/...
```

해당 링크에서 진행 상황 확인 가능. 완료되면 이메일로도 알림 옵니다.

---

## 8단계. TestFlight 배포

빌드 완료 후 아래 명령어로 TestFlight에 업로드:

```bash
eas submit --platform ios
```

- Apple Developer 계정으로 자동 업로드
- App Store Connect → TestFlight 탭에서 확인
- 테스터 초대하면 아이폰에서 설치 가능

---

## 자주 나오는 오류

### "expo-modules-core" 오류
```bash
npx expo install expo-modules-core
```

### Apple ID 2단계 인증 오류
- Apple ID → 설정 → 앱 암호 생성 → 거기서 생성한 암호로 로그인

### 빌드 중 "No bundle identifier" 오류
`app.json`에 아래 항목 확인:
```json
"ios": {
  "bundleIdentifier": "com.rainbowbridge.app"
}
```

### eas.json 없다는 오류
5단계 `eas build:configure` 다시 실행

---

## 참고

- EAS Build 대시보드: https://expo.dev
- 공식 문서: https://docs.expo.dev/build/setup/
- 막히면 세종님한테 연락!
