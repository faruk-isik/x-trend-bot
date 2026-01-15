import tweepy
import schedule
import time
import os
import threading
from openai import OpenAI
from duckduckgo_search import DDGS
from datetime import datetime
from flask import Flask

# --- VERSİYON KONTROL ---
print("VERSION: CHATGPT MODU (V8.0)")

# --- AYARLAR ---
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- WEB SUNUCUSU ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Calisiyor (ChatGPT Modu)"

def run_web_server():
    app.run(host='0.0.0.0', port=8000)

# --- OPENAI CLIENT ---
client_ai = OpenAI(api_key=OPENAI_API_KEY)

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
            results = ddgs.text("Türkiye son dakika haberleri -magazin -spor", region='tr-tr', timelimit='d', max_results=10)
            if not results: return None
            for r in results:
                news_results.append(f"Başlık: {r.get('title','')} - Detay: {r.get('body','')}")
    except Exception as e:
        print(f"Arama hatası: {e}")
        return None
    return "\n".join(news_results)

# --- CHATGPT İLE ANALİZ ---
def analyze_and_write_tweet(raw_data):
    if not raw_data: return "YOK"

    try:
        response = client_ai.chat.completions.create(
            model="gpt-4o-mini", # En hızlı ve ekonomik model
            messages=[
                {"role": "system", "content": "Sen tarafsız ve ciddi bir haber muhabirisin. Sana verilen haberlerden en önemli olanı seçip 270 karakterlik bir tweet oluşturursun. Haber değeri yoksa sadece 'YOK' yazarsın."},
                {"role": "user", "content": f"Aşağıdaki verileri analiz et ve tek bir haber paylaş:\n{raw_data}"}
            ],
            max_tokens=150
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"ChatGPT Hatası: {e}")
        return "YOK"

last_news_summary = ""

def job():
    global last_news_summary
    print(f"[{datetime.now()}] Haber taraması başladı...")
    
    raw_news = search_latest_news()
    if not raw_news: return

    tweet_content = analyze_and_write_tweet(raw_news)
    
    if tweet_content == "YOK" or not tweet_content:
        print("Kayda değer haber yok.")
        return

    if tweet_content == last_news_summary:
        print("Bu haber zaten atıldı.")
        return

    try:
        client = get_twitter_conn()
        client.create_tweet(text=tweet_content)
        print(f"Tweet Gönderildi: {tweet_content}")
        last_news_summary = tweet_content
    except Exception as e:
        print(f"Tweet Hatası: {e}")

if __name__ == "__main__":
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()
    
    job()
    schedule.every(30).minutes.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)
