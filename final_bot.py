import tweepy
import os
import re
import logging
import textwrap
from flask import Flask
from google import genai
from google.genai import types

# --- Log Ayarları ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. X (Twitter) API Bağlantısı ---
def get_v2_client():
    try:
        client = tweepy.Client(
            consumer_key=os.environ.get('CONSUMER_KEY'),
            consumer_secret=os.environ.get('CONSUMER_SECRET'),
            access_token=os.environ.get('ACCESS_TOKEN'),
            access_token_secret=os.environ.get('ACCESS_TOKEN_SECRET')
        )
        logging.info("✅ X V2 İstemcisi Başarıyla Oluşturuldu!")
        return client
    except Exception as e:
        logging.error(f"❌ X API Bağlantı Hatası: {e}")
        return None

# --- 2. Metin Temizleme Mekanizması ---
def absolute_cleaner(text):
    """Metnin hamlığını alır, tırnakları ve gereksiz etiketleri temizler."""
    if not text:
        return ""

    # Hashtag temizliği (Pro model bazen abartabilir, garantiye alalım)
    text = re.sub(r'#\S+', '', text)
    
    # Yıldız (*) gibi markdown işaretlerini temizle
    text = text.replace('*', '').replace('**', '')

    # Satır sonlarını düzenle
    text = " ".join(text.split()).strip()

    return text

# --- 3. Gemini 1.5 PRO İçerik Üretimi ---
def generate_gemini_tweet():
    fallback_text = "Gündem yoğun, gelişmeleri takipteyiz."
    
    try:
        # Yeni SDK yapısı
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        
        # --- PRO MODEL İÇİN GELİŞMİŞ KİMLİK AYARLARI ---
        system_rules = (
            "Sen Türkiye gündemini çok iyi okuyan, zeki ve hazırcevap bir sosyal medya fenomenisin. "
            "Görevin: Google Search aracıyla Türkiye'deki en son 'SON DAKİKA' veya 'TREND' haberi bulmak ve bunu tweetlemek. "
            "KURALLARIN ŞUNLAR:\n"
            "1. Asla 'Merhaba', 'İşte haber' gibi girişler yapma. Doğrudan konuya gir.\n"
            "2. Haberi kuru kuru verme; üzerine 1 cümlelik zekice, hafif iğneleyici veya şaşkınlık belirten yorumunu kat.\n"
            "3. Asla robotik konuşma (Örn: 'Gelişmeleri aktarıyoruz' DEME. 'Ortalık karıştı' DE).\n"
            "4. Asla hashtag (#) kullanma.\n"
            "5. Metnin toplam uzunluğu 260 karakteri geçmesin.\n"
            "6. Siyaset yapma, haberi ver ve yorumla."
        )
        
        user_prompt = "Türkiye gündemindeki en sıcak gelişme nedir? Bunu Twitter kitlesine uygun dille yaz."
        
        logging.info("--- Gemini 1.5 Pro Çalışıyor ---")
        
        response = client.models.generate_content(
            model='gemini-1.5-pro', # PRO MODEL: Daha zeki, daha iyi Türkçe.
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_rules,
                tools=[types.Tool(google_search=types.GoogleSearch())], # Güncel arama motoru
                temperature=0.7 # 0.7 yaratıcılık için idealdir (Pro modelde 0 yaparsak çok sıkıcı olur)
            )
        )
        
        # Arama sonucundan gelen metni al
        raw_text = response.text.strip() if response.text else fallback_text
        
        final_text = absolute_cleaner(raw_text)
        return final_text if final_text else fallback_text

    except Exception as e:
        logging.error(f"❌ Gemini Hatası: {e}")
        return fallback_text

# --- 4. Bot Çalıştırma ---
def run_bot():
    x_client = get_v2_client()
    if not x_client: return
    
    content = generate_gemini_tweet()
    
    try:
        # Güvenlik önlemi olarak kısaltma
        content = textwrap.shorten(content, width=275, placeholder="...")
        
        x_client.create_tweet(text=content)
        logging.info(f"🚀 Tweet Atıldı: {content}")
    except Exception as e:
        logging.error(f"❌ Tweet Gönderim Hatası: {e}")

# --- 5. Flask Sunucu ---
app = Flask(__name__)

@app.route('/trigger')
def trigger():
    run_bot()
    return "Bot başarıyla tetiklendi.", 200

@app.route('/')
def home():
    return "Gemini Pro Botu Aktif", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
