#!/bin/bash

if ! docker exec rainbow_mongo mongosh --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; then
    echo "[$(date)] rainbow_mongo 응답 없음 — 재시작 시도"
    docker restart rainbow_mongo

    for i in $(seq 1 30); do
        sleep 1
        if docker exec rainbow_mongo mongosh --eval "db.adminCommand('ping')" --quiet > /dev/null 2>&1; then
            echo "[$(date)] rainbow_mongo 재시작 성공 — rainbow_backend도 재시작"
            docker restart rainbow_backend
            exit 0
        fi
    done

    echo "[$(date)] rainbow_mongo 재시작 실패"
    exit 1
else
    echo "[$(date)] rainbow_mongo 정상"
fi
