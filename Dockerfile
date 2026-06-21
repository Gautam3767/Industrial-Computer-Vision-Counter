# Headless CV Object Counter API (Roadmap Phase 9).
#
#   docker build -t cv-counter-api .
#   docker run -p 8000:8000 \
#     -e CVCOUNTER_SOURCE="rtsp://user:pass@camera/stream" \
#     -e CVCOUNTER_ENGINE=mog \
#     cv-counter-api
#
# The GUI (PyQt5) is NOT installed here — this image runs the core only.
FROM python:3.11-slim

# OpenCV runtime needs a few system libs even in headless mode.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install API + core deps, but swap opencv-python for the headless build to
# avoid pulling GUI libraries into the container.
COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir \
        numpy==2.0.2 openpyxl==3.1.5 \
        opencv-python-headless==4.13.0 \
        fastapi==0.128.8 "uvicorn[standard]==0.39.0" pydantic==2.13.4

COPY *.py conveyor_tracker.yaml ./

EXPOSE 8000
ENV CVCOUNTER_SOURCE=0 \
    CVCOUNTER_ENGINE=mog

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
