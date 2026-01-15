import tweepy
import schedule
import time
import os
import google.generativeai as genai
from duckduckgo_search import DDGS
from datetime import datetime

# --- AYARLAR ---
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini Ayarları
genai.configure(api_key=GEMINI_API_KEY)
# MODEL DEĞİŞİKLİĞİ: "gemini-pro" en stabil ve hatasız çalışan modeldir.
model = genai.GenerativeModel('gemini-pro')

last_news_summary = ""

def get_twitter_conn():
    return tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET
    )

def search_latest_news():
    """DuckDuckGo üzerinden son 24 saatteki Türkiye haberlerini tarar."""
    print("İnternet taranıyor...")
    news_results = []
    try:
        # DDGS kütüphanesinin güncel kullanımı
        with DDGS() as ddgs:
            # 'd' = son 1 gün (day)
            results = ddgs.text("Türkiye son dakika haberleri -magazin -spor", region='tr-tr', timelimit='d', max_results=10)
            
            if not results:
                print("DuckDuckGo sonuç döndürmedi.")
                return None

            for r in results:
                body_text = r.get('body', '')
                title_text = r.get('title', '')
                news_results.append(f"Başlık: {title_text} - Detay: {body_text}")
                
    except Exception as e:
        print(f"Arama hatası: {e}")
        return None
    
    return "\n".join(news_results)

def analyze_and_write_tweet(raw_data):
    if not raw_data:
        return "YOK"

    prompt = f"""
    Sen Türkiye'nin en güvenilir, en tarafsız ve soğukkanlı haber muhabirisin.
    Aşağıda sana internetten taranmış son 24 saatin haber verileri sunuyorum.
    
    GÖREVLERİN:
    1. Bu veriler içindeki EN ÖNEMLİ, ulusal gündemi ilgilendiren tek bir olayı seç.
    2. Seçtiğin bu haberi "tarafsız" bir dille, yorum katmadan, sadece gerçeği aktararak yeniden yaz.
    3. Asla "iddia edildi", "söyleniyor" gibi güvensiz ifadeler kullanma, net olguları yaz.
    4. Maksimum 270 karakter olsun.
    5. Hashtag kullanma.
    6. Eğer kayda değer haber yoksa "YOK" yaz.
    
    TARANAN VERİLER:
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
    print(f"[{datetime.now()}] Görev başladı...")
    
    raw_news = search_latest_news()
    
    if not raw_news:
        print("Haber bulunamadı.")
        return

    tweet_content = analyze_and_write_tweet(raw_news)
    
    if tweet_content == "YOK" or not tweet_content:
        print("Gemini kayda değer bir haber bulamadı.")
        return

    if tweet_content == last_news_summary:
        print("Bu haber zaten paylaşıldı.")
        return

    print(f"Oluşturulan Tweet: {tweet_content}")

    try:
        client = get_twitter_conn()
        client.create_tweet(text=tweet_content)
        print("Tweet başarıyla gönderildi!")
        last_news_summary = tweet_content
    except Exception as e:
        print(f"Tweet atma hatası: {e}")

# İlk açılışta çalıştır
job()

# Her 30 dakikada bir çalıştır
schedule.every(30).minutes.do(job)

if __name__ == "__main__":
    print("Yapay Zeka Muhabiri (Gemini Pro) Başlatıldı...")
    while True:
        schedule.run_pending()
        time.sleep(1)
