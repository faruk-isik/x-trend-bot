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
        
        system_rules = (
            "Sen tarafsız bir haber aktarıcısısın. Önceki tüm tarzları unut. "
            "Görevin: Sadece güncel haber verisi sunmak. "
            "KESİN KURALLAR: Türkçe yaz, ASLA hashtag kullanma, ASLA emoji kullanma, "
            "tarafsız bir dil kullan ve metin 280 karakteri asla geçmesin."
        )
        
        user_prompt = "Türkiye gündemindeki en güncel ve önemli haberi Google'dan ara ve özetle."
        
        logging.info("--- Gemini Süreci Başladı ---")
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_rules,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.7
            )
        )

        # 1. Ham Yanıt Logu (Model ne üretti?)
        if response.text:
            logging.info(f"📝 Üretilen Tweet: {response.text.strip()}")
        else:
            logging.warning("⚠️ Model bir metin üretemedi.")

        # 2. Google Search Logu (Hangi kaynaklara baktı?)
        # Not: response.candidates[0].grounding_metadata üzerinden arama sorgularını görebiliriz.
        try:
            if response.candidates[0].grounding_metadata.search_entry_point:
                queries = response.candidates[0].grounding_metadata.grounding_chunks
                logging.info(f"🔍 Google Search Kaynak Sayısı: {len(queries)} kaynak tarandı.")
        except Exception:
            logging.info("ℹ️ Arama verisi detayları alınamadı (Model doğrudan bilgiyi kullanmış olabilir).")

        return response.text.strip() if response.text else fallback_text

    except Exception as e:
        logging.error(f"❌ Gemini Hatası: {str(e)}")
        return fallback_text

def run_bot():
    logging.info("🤖 Bot tetiklendi, tweet hazırlanıyor...")
    x_client = get_v2_client()
    if not x_client: 
        logging.error("❌ X Client başlatılamadı.")
        return
    
    content = generate_gemini_tweet()
    try:
        x_client.create_tweet(text=content)
        logging.info(f"✅ Tweet başarıyla gönderildi: {content}")
    except Exception as e:
        logging.error(f"❌ Tweet gönderim hatası: {e}")

app = Flask(__name__)

@app.route('/trigger')
def trigger():
    run_bot()
    return "Tetiklendi", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)



