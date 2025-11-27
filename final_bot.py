import tweepy
import os
import datetime
from flask import Flask
from google import genai
from google.genai.errors import APIError

# --- V2 İstemcisini Oluşturma Fonksiyonu (X API Bağlantısı) ---
def get_v2_client():
    """X V2 API istemcisini oluşturur ve anahtarları ortam değişkenlerinden çeker."""
    try:
        # Anahtarlar, Koyeb'deki Ortam Değişkenlerinden çekilir.
        client = tweepy.Client(
            consumer_key=os.environ.get('CONSUMER_KEY'),
            consumer_secret=os.environ.get('CONSUMER_SECRET'),
            access_token=os.environ.get('ACCESS_TOKEN'),
            access_token_secret=os.environ.get('ACCESS_TOKEN_SECRET')
        )
        client.get_me() 
        print("✅ X V2 İstemcisi Başarıyla Oluşturuldu!")
        return client
    except Exception as e:
        print(f"❌ X V2 İstemci Hatası: Lütfen anahtarlarınızı ve izinleri kontrol edin. Hata: {e}")
        return None

# --- Gemini'dan Güncel İçerik İsteme Fonksiyonu (Arama Entegre) ---
def generate_gemini_tweet():
    """Gemini'dan Google Search aracılığıyla güncel bir trend hakkında içerik ister."""
    fallback_text = "Yapay zeka güncel içerik alamadı, genel bir tweet atılıyor. #Gündem"
    
    try:
        # 1. Gemini İstemcisini Oluşturma
        # GEMINI_API_KEY değişkenini Koyeb'e eklediğinizden emin olun!
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        
        # 2. Gemini'ya Gönderilecek İstek (Prompt)
        prompt = (
            "Şu anki **Türkiye gündeminde en çok konuşulan konulardan** biri hakkında, "
            "insanların dikkatini çekecek, pozitif ve bilgilendirici bir Twitter (X) gönderisi "
            "(maksimum 250 karakter) hazırla. "
            "Konunun **güncel ve ilgi çekici** olduğunu belirt. Sonuna alakalı bir emoji ve bir hashtag ekle. "
            "Sadece tweet metnini döndür."
        )
        
        # 3. İçerik Oluşturma ve Arama Aracını Ekleme (Grounding)
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            # GOOGLE ARAMA yeteneği ekleniyor
            config={"tools": [{"google_search": {}}]} 
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
        saat = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M")
        final_tweet_text = f"[{saat} UTC] {tweet_text}"
        
        # 280 karakter limitini aşmaması için kontrol
        if len(final_tweet_text) > 280:
             final_tweet_text = final_tweet_text[:277] + "..."
        
        # V2 API ile tweet atma
        client.create_tweet(text=final_tweet_text)
        
        print(f"🚀 Gemini ile oluşturulan güncel tweet atıldı: {final_tweet_text}")

    except Exception as e:
        print(f"❌ V2 Tweet Atma Hatası: {e}")
        raise # Hatanın Flask'a iletilmesini sağlar

# --- Sunucu Yapısı (Dış Tetikleyici İçin Flask) ---
app = Flask(__name__)

@app.route('/')
def trigger_tweet():
    """Dışarıdan (Cron-Job) çağrıldığında botu çalıştırır."""
    print("📢 Dış Tetikleyici Algılandı. Bot Çalıştırılıyor...")
    
    try:
        run_bot() # Tek bir tweet atma işlemini başlat
        return "Tweet Tetikleme Başarılı!", 200
    except Exception as e:
        print(f"🔴 Ana Tetikleyici Hatası: {e}")
        return f"Tweet Atılırken Hata Oluştu: {e}", 500

# --- Botun Başlatılması ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
