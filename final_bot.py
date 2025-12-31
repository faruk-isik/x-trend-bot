import tweepy
import os
import textwrap
from flask import Flask
from google import genai
from google.genai import types

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

# --- 2. Gemini 3 İçerik Üretimi ---
def generate_gemini_tweet():
    fallback_text = "Türkiye gündemindeki gelişmeleri takip ediyoruz."
    
    try:
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        
        # SİSTEM TALİMATI: Modelin temel görev tanımı burasıdır.
        system_rules = (
            "Sen tarafsız bir haber aktarıcısısın. Önceki tüm etkileşimleri ve tarzları unut. "
            "Görevin: Sadece güncel haber verisi sunmak. "
            "KESİN KURALLAR: Türkçe yaz, ASLA hashtag kullanma, ASLA emoji kullanma, "
            "tarafsız bir dil kullan ve metin 280 karakteri asla geçmesin."
        )
        
        # KULLANICI İSTEMİ: Spesifik görev.
        user_prompt = (
            "Google Search kullanarak şu an Türkiye gündemindeki en önemli haberi bul. "
            "Bulduğun haberi, daha önce bahsettiğin konulardan farklı olacak şekilde, "
            "bilgilendirici bir tweet metnine dönüştür."
        )
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', # En güncel kararlı sürümü kullanmanızı öneririm
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_rules, # Talimatları buraya taşıdık
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.7, # 0.7 daha güncel ve çeşitli sonuçlar sağlar
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_ONLY_HIGH"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_ONLY_HIGH")
                ]
            )
        )
        
        if not response.text:
            return fallback_text
            
        tweet_text = response.text.strip()
        
        # Kelime bölmeden akıllı kısaltma
        return textwrap.shorten(tweet_text, width=280, placeholder="...") if len(tweet_text) > 280 else tweet_text

    except Exception as e:
        print(f"❌ Gemini 3 Hatası: {e}")
        return fallback_text

# --- 3. Flask ve Bot Çalıştırma ---
def run_bot():
    x_client = get_v2_client()
    if not x_client: return
    
    content = generate_gemini_tweet()
    try:
        x_client.create_tweet(text=content)
        print(f"🚀 Gemini 3 ile Tweet Atıldı: {content}")
    except Exception as e:
        print(f"❌ Tweet Hatası: {e}")

app = Flask(__name__)

@app.route('/trigger')
def trigger():
    run_bot()
    return "Tetiklendi", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)


