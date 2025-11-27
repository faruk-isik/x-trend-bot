import tweepy
import random
import os
import datetime
from flask import Flask

# Türkiye Gündemine Dair Konu Başlıkları (Bu listeyi güncelleyebilirsiniz)
GÜNDEM_KONULARI = [
    "Bot denemeleri başarılı oldu! Otomatik tweet servisi aktif. 🎉",
    "Günün ilk tweet'i geliyor! Sizin gündeminizde ne var? 🤔",
    "Tekrar merhaba! Belirlenen saatte otomatik tweet gönderiliyor. #bot",
    "Otomasyon dünyasından selamlar! Her şey yolunda görünüyor. 🤖",
    "Bu tweet, dışarıdan gelen bir sinyal ile atılmıştır. 📡"
]

# --- V2 İstemcisini Oluşturma Fonksiyonu (API Bağlantısı) ---
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
        print("✅ X V2 İstemcisi Başarıyla Oluşturuldu!")
        return client
    except Exception as e:
        print(f"❌ X V2 İstemci Hatası: {e}")
        return None

# --- Ana Tweet Atma Fonksiyonu ---
def run_bot():
    """Rastgele bir konu seçer ve V2 ile tweet atar."""
    client = get_v2_client()
    if not client:
        # Eğer istemci oluşmazsa, daha fazla devam etme
        return

    try:
        # Rastgele bir konu seçme
        konu = random.choice(GÜNDEM_KONULARI)
        saat = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M")
        
        tweet_text = f"[UTC: {saat}] {konu}"
        
        # V2 API ile tweet atma
        client.create_tweet(text=tweet_text)
        
        print(f"🚀 V2 ile başarıyla tweet atıldı: {tweet_text}")

    except Exception as e:
        # Bu hata, sunucuya 500 hatası döndürür
        print(f"❌ V2 Tweet Atma Hatası: {e}")
        raise # Hatanın Flask'a iletilmesini sağlar

# --- Sunucu Yapısı (Dış Tetikleyici İçin Flask) ---

# Flask uygulamasını tanımlıyoruz
app = Flask(__name__)

@app.route('/')
def trigger_tweet():
    """Dışarıdan (Cron-Job) çağrıldığında botu çalıştırır."""
    print("📢 Dış Tetikleyici Algılandı. Bot Çalıştırılıyor...")
    
    # Hata oluşursa 500 yerine 200 döndürmek için try/except kullanıyoruz
    try:
        run_bot() # Tek bir tweet atma işlemini başlat
        return "Tweet Tetikleme Başarılı!", 200
    except Exception as e:
        print(f"🔴 Ana Tetikleyici Hatası: {e}")
        # Hata olsa bile Cron-Job'a 200 döndürerek işlemi bitiriyoruz
        return f"Tweet Atılırken Hata Oluştu: {e}", 500


# --- Botun Başlatılması ---
if __name__ == "__main__":
    # Gunicorn, bu kısmı değil, 'gunicorn final_bot:app' komutunu kullanır.
    # Ancak yine de Flask'ı çalıştırmak için bir yapı bulundurmak iyidir.
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
