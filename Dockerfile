FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf TOKENIZERS_PARALLELISM=false
WORKDIR /srv

# CPU-only torch keeps the image small; everything else from requirements.txt
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# Bake models + deeplink index into the image, then fill the plan cache (rules mode unless a key is passed at build)
RUN python scripts/build_index.py && python scripts/prewarm.py --reset
ENV HF_HUB_OFFLINE=1

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
