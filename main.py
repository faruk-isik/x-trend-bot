import tweepy
import schedule
import time
import os
import threading
from groq import Groq
from ddgs import DDGS
from datetime import datetime
from flask import Flask

# --- VERSİYON KONTROL ---
print("VERSION: GROQ LLAMA 3 MODU (V9.0)")

# --- AYARLAR ---
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- WEB SUNUCUSU (KOYEB İÇİN) ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Calisiyor (Groq Llama 3 Modu)"

def run_web_server():
    app.run(host='0.0.0.0', port=8000)

# --- GROQ CLIENT ---
client_ai = Groq(api_key=GROQ_API_KEY)

# --- TWITTER BAĞLANTISI ---
def get_twitter_conn():
    return tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET
    )

# --- HABER ARAMA ---
def search_latest_news():
    print("İnternet taranıyor...")
    news_results = []
    try:
        with DDGS() as ddgs:
            # Gündemi yakalamak için aramayı biraz genişlettik
            results = ddgs.text("Türkiye gündemi son dakika haberler", region='tr-tr', timelimit='d', max_results=10)
            if not results: return None
            for r in results:
                news_results.append(f"Haber: {r.get('title','')} - Detay: {r.get('body','')}")
    except Exception as e:
        print(f"Arama hatası: {e}")
        return None
    return "\n".join(news_results)

# --- GROQ İLE ANALİZ ---
def analyze_and_write_tweet(raw_data):
    if not raw_data: return "YOK"

    try:
        completion = client_ai.chat.completions.create(
            model="llama-3.3-70b-versatile", # Groq'un en güçlü modellerinden biri
            messages=[
                {"role": "system", "content": "Sen tarafsız bir muhabirsin. Haberleri analiz eder ve en önemlisini 270 karakterlik ciddi bir tweet olarak yazarsın. Haber yoksa sadece 'YOK' yaz."},
                {"role": "user", "content": f"Şu verileri analiz et:\n{raw_data}"}
            ]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Groq Hatası: {e}")
        return "YOK"

last_news_summary = ""

def job():
    global last_news_summary
    print(f"[{datetime.now()}] Görev tetiklendi...")
    
    raw_news = search_latest_news()
    if not raw_news: return

    tweet_content = analyze_and_write_tweet(raw_news)
    
    if tweet_content == "YOK" or not tweet_content:
        print("Paylaşılacak önemli bir haber bulunamadı.")
        return

    if tweet_content == last_news_summary:
        print("Bu haber zaten son paylaşılan haberle aynı.")
        return

    try:
        client = get_twitter_conn()
        client.create_tweet(text=tweet_content)
        print(f"Tweet Gönderildi: {tweet_content}")
        last_news_summary = tweet_content
    except Exception as e:
        print(f"Twitter API Hatası (Muhtemelen 429 Limit): {e}")

if __name__ == "__main__":
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()
    
     job() # X limitlerini zorlamamak için başlangıçta çalıştırmayı opsiyonel olarak kapatabilirsin
    schedule.every(30).minutes.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)
