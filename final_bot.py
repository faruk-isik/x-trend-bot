import tweepy
import random
import os
import datetime
from flask import Flask

# ... (GÜNDEM_KONULARI listesi aynı kalır)

# --- V2 İstemcisini Oluşturma Fonksiyonu --- (Aynı Kalır)
# ... get_v2_client() fonksiyonu buraya kopyalanır.

# --- Ana Tweet Atma Fonksiyonu (Sadece Tek İşlem) ---
def run_bot():
    """Rastgele bir konu seçer ve V2 ile tweet atar."""
    client = get_v2_client()
    if not client:
        return
    # (Tweet atma mantığı aynı kalır)
    # ...
    
# --- Sunucu Yapısı (Dış Tetikleyici İçin Gerekli) ---

app = Flask(__name__)

@app.route('/')
def trigger_tweet():
    """Dışarıdan çağrıldığında botu çalıştırır."""
    print("📢 Dış Tetikleyici Algılandı. Bot Çalıştırılıyor...")
    run_bot() # Tek bir tweet at
    return "Tweet Tetikleme Başarılı!", 200

# --- Botun Çalıştırılması ---
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)