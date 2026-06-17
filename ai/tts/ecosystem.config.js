// pm2 로 Qwen3 TTS 서버(8002)를 관리하기 위한 설정.
// 세종님이 요청한 `pm2 restart qwen3` / `pm2 restart 0` 를 이 PC에서 쓰려면 먼저 설치·등록 필요.
//
// [최초 1회 셋업]  (※ 살아있는 서버 안 띄운 상태에서, 라이브 수업 없을 때)
//   1) npm i -g pm2
//   2) 기존 start_tts.bat 로 떠 있는 8002 는 콘솔 닫아서 종료(직접). 포트 비운 뒤 진행.
//   3) cd C:\Rainbow_Bridge\Rainbow-Bridge\ai\tts
//   4) pm2 start ecosystem.config.js
//   5) pm2 save   (재부팅 자동복구 원하면: npm i -g pm2-windows-startup && pm2-startup install)
//
// [이후 운영]
//   pm2 restart qwen3   (또는 pm2 restart 0)  ← 세종님 명령
//   pm2 logs qwen3       로그
//   pm2 stop qwen3       정지
//
// ⚠️ 주의 (이 설정 쓰기 전 반드시 확인)
//   - Windows+conda 조합에선 pm2 가 .bat 만 추적하고 그 안의 python(손주 프로세스)을
//     stop 시 못 죽여 VRAM(8GB) 점유한 채 남는 사례 있음. 첫 pm2 stop/restart 후
//     `nvidia-smi` 로 python 잔류 없는지 1회 검증할 것.
//   - autorestart=크래시 시 자동 재기동. 예전 8003 워치독이 2번째 서버 띄워 VRAM
//     이중점유로 영구제거된 이력(TTS_8003_워치독_해결_260616.md) 있음.
//     pm2 는 8002 단일 인스턴스만 띄우므로 그 케이스와 다르지만, 자동재시작 도입은
//     팀(세종) 합의 후 적용 권장.
//   - 이 설정은 start_tts.bat 을 "대체"함. 둘 다 동시에 띄우면 8002 충돌.

module.exports = {
  apps: [
    {
      name: "qwen3",
      // Windows: pm2 가 .bat 직접 spawn 시 EINVAL → cmd.exe /c 로 감싼다.
      script: "cmd.exe",
      args: "/c C:\\Rainbow_Bridge\\Rainbow-Bridge\\ai\\tts\\pm2_qwen3.bat",
      cwd: "C:/Rainbow_Bridge/Rainbow-Bridge/ai/tts",
      interpreter: "none",
      autorestart: true,
      max_restarts: 3, // 크래시 무한루프 방지(VRAM 미회수 상태 반복로드 차단)
      min_uptime: 30000, // 30s 못 버티면 비정상으로 간주
      restart_delay: 5000, // 재시작 전 5s 대기(VRAM 회수 여유)
      kill_timeout: 15000, // 종료 신호 후 15s 기다렸다 강제(모델 정리 시간)
      windowsHide: true,
      out_file: "C:/Rainbow_Bridge/Rainbow-Bridge/ai/tts/pm2_qwen3.out.log",
      error_file: "C:/Rainbow_Bridge/Rainbow-Bridge/ai/tts/pm2_qwen3.err.log",
    },
  ],
};
