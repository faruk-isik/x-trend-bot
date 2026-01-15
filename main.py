import tweepy
import schedule
import time
import os
import threading
from google import genai
from duckduckgo_search import DDGS
from datetime import datetime
from flask import Flask

# --- VERSİYON KONTROL ---
print("VERSION: YENI KOD CALISTI (Google GenAI v1)")

# --- AYARLAR ---
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- KOYEB WEB SUNUCUSU ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Aktif! (v4.0 Final)"

def run_web_server():
    app.run(host='0.0.0.0', port=8000)

# --- GEMINI (YENI NESIL CLIENT) ---
client_gemini = genai.Client(api_key=GEMINI_API_KEY)

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
            # 'd' = Son 1 gün
            results = ddgs.text("Türkiye son dakika haberleri -magazin -spor", region='tr-tr', timelimit='d', max_results=10)
            
            if not results: return None

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
    
    Seçtiğin haberi tarafsız, net ve ciddi bir dille, bir haber ajansı diliyle yaz.
    Yorum katma, sadece olguyu aktar.
    Uzunluk: Maksimum 270 karakter.
    Hashtag: Kullanma.
    Haber değeri yoksa sadece "YOK" yaz.
    
    VERİLER:
    {raw_data}
    """
    
    try:
        # YENİ KOD YAPISI BURASI
        response = client_gemini.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt
        )
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

if __name__ == "__main__":
    print("Sistem Başlatılıyor...")
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()
    
    job() # İlk test
    schedule.every(30).minutes.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)
