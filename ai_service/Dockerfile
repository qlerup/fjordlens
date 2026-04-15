FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# System dependencies for OpenCV/InsightFace (headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install torch with GPU-first fallback:
# - Try CUDA wheel index first (enables GPU where available)
# - Fall back to CPU wheel index on unsupported platforms
ARG TORCH_VERSION=2.1.2
ARG TORCH_GPU_INDEX_URL=https://download.pytorch.org/whl/cu121
ARG TORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu
RUN set -eux; \
    if pip install --no-cache-dir --index-url "${TORCH_GPU_INDEX_URL}" "torch==${TORCH_VERSION}"; then \
      echo "Installed CUDA-capable torch build"; \
    else \
      echo "CUDA torch build unavailable, using CPU torch build"; \
      pip install --no-cache-dir --index-url "${TORCH_CPU_INDEX_URL}" "torch==${TORCH_VERSION}"; \
    fi

# Install ONNX Runtime with GPU-first fallback:
# - Prefer onnxruntime-gpu when available
# - Fall back to CPU package if GPU wheel is unavailable
ARG ONNXRUNTIME_GPU_SPEC=onnxruntime-gpu>=1.16,<2.0
ARG ONNXRUNTIME_CPU_SPEC=onnxruntime>=1.16,<2.0
RUN set -eux; \
    if pip install --no-cache-dir "${ONNXRUNTIME_GPU_SPEC}"; then \
      echo "Installed onnxruntime-gpu"; \
    else \
      echo "onnxruntime-gpu unavailable, using onnxruntime (CPU)"; \
      pip install --no-cache-dir "${ONNXRUNTIME_CPU_SPEC}"; \
    fi

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 8000
CMD ["python", "app.py"]
