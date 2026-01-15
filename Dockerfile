FROM python:3.11-slim

# Çalışma dizini oluştur
WORKDIR /app

# Gereksinimleri kopyala ve yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kodları kopyala
COPY main.py .

# Uygulamayı başlat
CMD ["python", "-u", "main.py"]
