import tweepy
import os
import textwrap
from flask import Flask
from google import genai
from google.genai import types
import logging

# --- 1. X (Twitter) API Bağlantısı ---
def get_v2_client():
    try:
        client = tweepy.Client(
            consumer_key=os.environ.get('CONSUMER_KEY'),
            consumer_secret=os.environ.get('CONSUMER_SECRET'),
            access_token=os.environ.get('ACCESS_TOKEN'),
            access_token_secret=os.environ.get('ACCESS_TOKEN_SECRET')
        )
        return client
    except Exception as e:
        print(f"❌ X API Bağlantı Hatası: {e}")
        return None

# Log formatını ayarlayalım: Zaman - Mesaj Seviyesi - İçerik
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_gemini_tweet():
    fallback_text = "Türkiye gündemindeki gelişmeleri takip ediyoruz."
    
    try:
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        
        # SİSTEM TALİMATINI DAHA SERT VE ÖRNEKLİ HALE GETİRDİK
        system_rules = (
            "Sen bir haber botusun. Sadece tek bir paragraf metin yazarsın. "
            "ASLA başlık atma, ASLA kategori (Ekonomi, Haber vb.) ekleme. "
            "ASLA hashtag (#) ve emoji kullanma. "
            "Örnek Format: Türkiye Cumhuriyet Merkez Bankası bugün faiz kararını açıkladı. Politika faizi yüzde 50 seviyesinde sabit tutuldu. Karar metninde dezenflasyon vurgusu yapıldı."
        )
        
        # Arama sorgusunu biraz daha spesifikleştirdik
        user_prompt = (
            "Google Search kullanarak şu an Türkiye'de gerçekleşen, "
            "son 1 saat içindeki en güncel ve somut olayı bul. "
            "Genel yıllık değerlendirme yapma, spesifik bir haber seç ve tweetle."
        )
        
        logging.info("--- Gemini 2.0 Flash İşlemde ---")
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_rules,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3 # Yaratıcılığı düşürdük, kurallara daha sadık kalacak
            )
        )
        
        # Manuel Temizlik: Model hala inatla kategori eklerse onları temizleyelim
        if response.text:
            text = response.text.strip()
            # Eğer son satırda tek bir kelime kalmışsa (Ekonomi gibi), onu temizlemek için:
            lines = text.split('\n')
            if len(lines) > 1 and len(lines[-1].split()) == 1:
                text = "\n".join(lines[:-1]).strip()
            
            return text
        
        return fallback_text

    except Exception as e:
        logging.error(f"❌ Hata: {str(e)}")
        return fallback_text

app = Flask(__name__)

@app.route('/trigger')
def trigger():
    run_bot()
    return "Tetiklendi", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)




