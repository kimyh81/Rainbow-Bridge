#!/bin/bash
# MongoDB 헬스체크 + 자동 재시작 watchdog
# 설치: crontab -e → */3 * * * * /root/Rainbow-Bridge/backend/scripts/watch_mongo.sh >> /var/log/watch_mongo.log 2>&1

CONTAINER="rainbow_mongo"
BACKEND_CONTAINER="rainbow_backend"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')] [watch_mongo]"

# MongoDB 응답 확인 (ping)
check_mongo() {
    docker exec "$CONTAINER" mongosh --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1
}

# 컨테이너 실행 중인지 확인
is_running() {
    [ "$(docker inspect -f '{{.State.Running}}' "$1" 2>/dev/null)" = "true" ]
}

# MongoDB 다운 여부 확인
if is_running "$CONTAINER" && check_mongo; then
    # 정상 — 아무것도 안 함 (로그 안 남겨 노이즈 방지)
    exit 0
fi

echo "$LOG_PREFIX MongoDB 응답 없음 — 재시작 시도"

# 컨테이너 재시작
docker restart "$CONTAINER"

# 최대 30초 대기 (MongoDB 기동 시간)
for i in $(seq 1 10); do
    sleep 3
    if check_mongo; then
        echo "$LOG_PREFIX MongoDB 재시작 성공 (${i}번째 시도)"

        # 백엔드도 재시작 (MongoDB 연결 끊긴 상태로 떠있을 수 있음)
        if is_running "$BACKEND_CONTAINER"; then
            docker restart "$BACKEND_CONTAINER"
            echo "$LOG_PREFIX 백엔드 재시작 완료"
        fi

        exit 0
    fi
done

echo "$LOG_PREFIX ❌ MongoDB 재시작 실패 — 수동 확인 필요"
echo "$LOG_PREFIX docker logs $CONTAINER 로 원인 확인하세요"
exit 1
