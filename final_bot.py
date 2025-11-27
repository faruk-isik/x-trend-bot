import tweepy
import random
import os
import datetime
from flask import Flask
from google import genai
from google.genai.errors import APIError

# --- V2 İstemcisini Oluşturma Fonksiyonu (X API Bağlantısı) ---
def get_v2_client():
    """X V2 API istemcisini oluşturur ve anahtarları ortam değişkenlerinden çeker."""
    try:
        # Anahtarlar, Koyeb'deki Ortam Değişkenlerinden (Environment Variables) çekilir.
        client = tweepy.Client(
            consumer_key=os.environ.get('CONSUMER_KEY'),
            consumer_secret=os.environ.get('CONSUMER_SECRET'),
            access_token=os.environ.get('ACCESS_TOKEN'),
            access_token_secret=os.environ.get('ACCESS_TOKEN_SECRET')
        )
        client.get_me() # Bağlantıyı kontrol etmek için basit bir çağrı
        print("✅ X V2 İstemcisi Başarıyla Oluşturuldu!")
        return client
    except Exception as e:
        print(f"❌ X V2 İstemci Hatası: Lütfen anahtarlarınızı ve izinleri kontrol edin. Hata: {e}")
        return None

# --- Gemini'dan İçerik İsteme Fonksiyonu ---
def generate_gemini_tweet():
    """Gemini'dan güncel bir trend hakkında ilgi çekici bir tweet metni ister."""
    # Varsayılan hata metni (AI'dan yanıt gelmezse bu kullanılır)
    fallback_text = "Yapay zeka içeriği alınamadı, standart bir kontrol tweeti atılıyor. #AIHata"
    
    try:
        # 1. Gemini İstemcisini Oluşturma (API anahtarını ortam değişkeninden çeker)
        # GEMINI_API_KEY değişkenini Koyeb'e eklediğinizden emin olun!
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        
        # 2. Gemini'ya Gönderilecek İstek (Prompt)
        prompt = (
            "Türkiye gündemine veya genel kültüre dair, ilgi çekici, pozitif ve düşündürücü "
            "bir Twitter (X) gönderisi (maksimum 250 karakter) hazırla. "
            "Sonuna mutlaka alakalı bir emoji ve bir hashtag ekle. Sadece tweet metnini döndür."
        )
        
        # 3. İçerik Oluşturma
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt
        )
        
        # 4. Yanıtı Temizleme ve Döndürme
        return response.text.strip()
        
    except APIError as e:
        print(f"❌ Gemini API Hatası: {e}")
        return fallback_text
    except Exception as e:
        print(f"❌ Beklenmedik Hata: {e}")
        return fallback_text

# --- Ana Tweet Atma Fonksiyonu ---
def run_bot():
    """Gemini'dan içerik çeker ve V2 ile tweet atar."""
    client = get_v2_client()
    if not client:
        return

    # Tweet metnini Gemini'dan al
    tweet_text = generate_gemini_tweet()
    
    try:
        # UTC saatini ekleme (tweet'in güncel olduğunu gösterir)
        saat = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M")
        final_tweet_text = f"[{saat} UTC] {tweet_text}"
        
        # X'in karakter
