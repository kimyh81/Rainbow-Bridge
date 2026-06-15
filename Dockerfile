FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# LivePortrait 음성 합치기(merge_audio)가 ffmpeg를 사용 — slim 이미지엔 없어 설치.
# 영상 추론은 GPU 서버(remote)에 위임하지만, TTS 음성 합성은 NCP 백엔드에서 직접 수행.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY ai/ ./ai/
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
