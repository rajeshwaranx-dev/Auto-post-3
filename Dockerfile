FROM python:3.11-slim

# System fonts + build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    fonts-dejavu-core \
    wget \
    bzip2 \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create required dirs
RUN mkdir -p posters assets/fonts

# Download DejaVu fonts (good Unicode coverage — free & pre-licensed)
RUN wget -q https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2 \
    && tar -xjf dejavu-fonts-ttf-2.37.tar.bz2 \
    && cp dejavu-fonts-ttf-2.37/ttf/DejaVuSans-Bold.ttf assets/fonts/bold.ttf \
    && cp dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf      assets/fonts/regular.ttf \
    && rm -rf dejavu-fonts-ttf-2.37*

CMD ["python", "main.py"]
