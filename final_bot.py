import tweepy
import os
import textwrap
from flask import Flask
from google import genai
from google.genai import types
import logging
import re

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

def clean_tweet_text(text):
    """Model hata yapsa bile hashtag ve emojileri temizler."""
    # 1. Hashtagleri temizle (#Kelime -> Kelime veya tamamen sil)
    # Eğer sadece hashtag'i silmek istersen:
    text = re.sub(r'#\w+', '', text)
    
    # 2. Emojileri temizle
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # 3. Gereksiz boşlukları ve satır sonlarını temizle
    text = " ".join(text.split())
    
    return text.strip()

def generate_gemini_tweet():
    fallback_text = "Türkiye gündemindeki gelişmeler takip ediliyor."
    
    try:
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        
        # Talimatı 'Haber Botu' yerine 'Metin Yazarı' olarak değiştirdik ki tweet kalıplarına girmesin
        system_rules = (
            "Sen bir metin yazarıısın. Sadece düz yazı yazarsın. "
            "Görevin: Verilen haberi tek bir paragraf olarak, hiçbir süsleme yapmadan yazmak. "
            "YASAKLAR: # karakteri kullanmak yasak, emoji kullanmak yasak, başlık atmak yasak. "
            "Sadece haberin kendisini yaz ve bitir."
        )
        
        user_prompt = "Google Search ile Türkiye'den son dakika bir haber bul ve sadece haber metnini yaz."
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_rules,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.1 # En düşük yaratıcılık: Talimata maksimum sadakat
            )
        )
        
        raw_text = response.text.strip() if response.text else fallback_text
        
        # --- ZORUNLU TEMİZLİK ---
        # Model ne kadar hata yaparsa yapsın, biz burada temizliyoruz.
        final_tweet = clean_tweet_text(raw_text)
        
        return final_tweet

    except Exception as e:
        print(f"❌ Hata: {e}")
        return fallback_text

app = Flask(__name__)

@app.route('/trigger')
def trigger():
    run_bot()
    return "Tetiklendi", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)





