import tweepy
import schedule
import time
import os
import threading
import requests
import json
from duckduckgo_search import DDGS
from datetime import datetime
from flask import Flask

# --- VERSİYON KONTROL ---
print("VERSION: AUTO-MODEL SELECTOR (V7.0)")

# --- AYARLAR ---
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- WEB SUNUCUSU ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot Calisiyor (Multi-Model Modu)"

def run_web_server():
    app.run(host='0.0.0.0', port=8000)

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
            # Son 1 gün
            results = ddgs.text("Türkiye son dakika haberleri -magazin -spor", region='tr-tr', timelimit='d', max_results=10)
            if not results: return None
            for r in results:
                title = r.get('title', 'Basliksiz')
                body = r.get('body', 'Detaysiz')
                news_results.append(f"Başlık: {title} - Detay: {body}")
    except Exception as e:
        print(f"Arama hatası: {e}")
        return None
    return "\n".join(news_results)

# --- GEMINI (AKILLI MODEL SEÇİCİ) ---
def ask_gemini_manual(prompt):
    # Denenecek Modeller Listesi (Sırayla dener)
    models_to_try = [
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-1.0-pro",
        "gemini-pro"
    ]
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    # Döngü: Modelleri tek tek dener
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
        
        try:
            # print(f"Deneniyor: {model_name}...") 
            response = requests.post(url, headers=headers, data=json.dumps(data))
            
            if response.status_code == 200:
                result = response.json()
                print(f"BAŞARILI! Çalışan Model: {model_name}")
                return result['candidates'][0]['content']['parts'][0]['text'].strip()
            
            elif response.status_code == 404:
                # 404 hatası model bulunamadı demektir, bir sonrakine geç
                print(f"Model bulunamadı ({model_name}), bir sonrakine geçiliyor...")
                continue
            else:
                # Başka bir hata varsa (örn: Yetki hatası) yazdır ama devam et
                print(f"Hata ({model_name}): {response.status_code} - {response.text}")
                continue
                
        except Exception as e:
            print(f"Bağlantı hatası ({model_name}): {e}")
            continue
    
    # Döngü bitti ve hiçbiri çalışmadıysa
    return "YOK"

def analyze_and_write_tweet(raw_data):
    if not raw_data: return "YOK"

    prompt = f"""
    Sen Türkiye'nin en güvenilir haber muhabirisin.
    Aşağıdaki son dakika haberlerinden EN ÖNEMLİ, ulusal gündemi etkileyen TEK BİR olayı seç.
    Seçtiğin haberi tarafsız, net ve ciddi bir dille, yorum katmadan 270 karakteri geçmeyecek şekilde yaz.
    Haber değeri yoksa "YOK" yaz.
    VERİLER: {raw_data}
    """
    
    return ask_gemini_manual(prompt)

last_news_summary = ""

def job():
    global last_news_summary
    print(f"[{datetime.now()}] Haber taraması başladı...")
    
    raw_news = search_latest_news()
    if not raw_news:
        print("Haber bulunamadı.")
        return

    tweet_content = analyze_and_write_tweet(raw_news)
    
    if tweet_content == "YOK" or not tweet_content:
        print("Kayda değer haber yok veya Gemini yanıt veremedi.")
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
    t = threading.Thread(target=run_web_server)
    t.daemon = True
    t.start()
    
    job()
    schedule.every(30).minutes.do(job)
    
    while True:
        schedule.run_pending()
        time.sleep(1)
