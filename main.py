import tweepy
import schedule
import time
import os
import threading
import google.generativeai as genai
from duckduckgo_search import DDGS
from datetime import datetime
from flask import Flask

# --- AYARLAR ---
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- KOYEB'İ AYAKTA TUTACAK WEB SUNUCUSU ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Aktif ve Calisiyor!"

def run_web_server():
    # Koyeb 8000 portunu dinler
    app.run(host='0.0.0.0', port=8000)

# --- GEMINI VE BOT AYARLARI ---
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

last_news_summary = ""

def get_twitter_conn():
    return tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET
    )

def search_latest_news():
    print("İnternet taranıyor...")
    news_results = []
    try:
        with DDGS() as ddgs:
            # 'd' = son 1 gün. Hata almamak için en güvenli aralık.
            results = ddgs.text("Türkiye son dakika haberleri -magazin -spor", region='tr-tr', timelimit='d', max_results=10)
            
            if not results:
                return None

            for r in results:
                title = r.get('title', '')
                body = r.get('body', '')
                news_results.append(f"Başlık: {title} - Detay: {body}")
                
    except Exception as e:
        print(f"Arama hatası: {e}")
        return None
    
    return "\n".join(news_results)

def analyze_and_write_tweet(raw_data):
    if not raw_data: return "YOK"

    prompt = f"""
    Sen Türkiye'nin en güvenilir haber muhabirisin.
    Aşağıdaki son dakika haberlerinden EN ÖNEMLİ, ulusal gündemi etkileyen TEK BİR olayı seç.
    Magazin ve 3. sayfa haberlerini görmezden gel.
    
    Seçtiğin haberi tarafsız, net ve ciddi bir dille 270 karakteri geçmeyecek şekilde yaz.
    Yorum katma, sadece olguyu aktar. Hashtag kullanma.
    Haber değeri taşıyan ciddi bir şey yoksa sadece "YOK" yaz.
    
    VERİLER:
    {raw_data}
    """
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini hatası: {e}")
        return "YOK"

def job():
    global last_news_summary
    print(f"[{datetime.now()}] Haber taraması başladı...")
    
    raw_news = search_latest_news()
    if not raw_news:
        print("Haber bulunamadı.")
        return

    tweet_content = analyze_and_write_tweet(raw_news)
    
    if tweet_content == "YOK" or not tweet_content:
        print("Kayda değer haber yok.")
        return

    if tweet_content == last_news_summary:
        print("Bu haber zaten atıldı.")
        return

    print(f"Tweet Hazır: {tweet_content}")

    try:
        client = get_twitter_conn()
        client.create_tweet(text=tweet_content)
        print("Tweet Gönderildi!")
        last_news_summary = tweet_content
    except Exception as e:
        print(f"Tweet Hatası: {e}")

# --- ANA ÇALIŞMA BLOĞU ---
if __name__ == "__main__":
    print("Sistem Başlatılıyor...")
    
    # 1. Web sunucusunu ayrı bir kanalda (thread) başlat
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()
    
    # 2. Botu başlat
    # İlk açılışta hemen bir kontrol et
    job()
    
    # Sonra her 30 dakikada bir devam et
    schedule.every(30).minutes.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)
