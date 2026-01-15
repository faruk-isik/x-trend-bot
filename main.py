import tweepy
import schedule
import time
import os
import google.generativeai as genai
from duckduckgo_search import DDGS
from datetime import datetime

# --- AYARLAR VE ANAHTARLAR ---
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Gemini Ayarları
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash') # Hız ve maliyet için Flash ideal

# Son paylaşılan haberin özeti hafızada kalsın (Tekrarı önlemek için)
last_news_summary = ""

def get_twitter_conn():
    return tweepy.Client(
        consumer_key=X_API_KEY,
        consumer_secret=X_API_SECRET,
        access_token=X_ACCESS_TOKEN,
        access_token_secret=X_ACCESS_SECRET
    )

def search_latest_news():
    """DuckDuckGo üzerinden son 1 saatteki Türkiye haberlerini tarar."""
    print("İnternet taranıyor...")
    news_results = []
    try:
        with DDGS() as ddgs:
            # "Türkiye haberleri", son 1 saat (h), Türkiye bölgesi (tr-tr)
            results = ddgs.text("Türkiye son dakika haberleri -magazin -spor", region='tr-tr', timelimit='h', max_results=10)
            for r in results:
                news_results.append(f"Kaynak: {r['title']} - Özet: {r['body']}")
    except Exception as e:
        print(f"Arama hatası: {e}")
    
    return "\n".join(news_results)

def analyze_and_write_tweet(raw_data):
    """Ham veriyi Gemini'ye gönderir ve tarafsız tweet ister."""
    
    prompt = f"""
    Sen Türkiye'nin en güvenilir, en tarafsız ve soğukkanlı haber muhabirisin.
    Aşağıda sana internetten taranmış son dakika haber verileri sunuyorum.
    
    GÖREVLERİN:
    1. Bu veriler içindeki EN ÖNEMLİ, ulusal gündemi ilgilendiren tek bir olayı seç. (Yerel 3. sayfa haberlerini veya magazini yoksay).
    2. Seçtiğin bu haberi "tarafsız" bir dille, yorum katmadan, sadece gerçeği aktararak yeniden yaz.
    3. Asla "iddia edildi", "söyleniyor" gibi güvensiz ifadeler kullanma, net olguları yaz.
    4. Maksimum 270 karakter olsun (X/Twitter sınırı).
    5. Hashtag kullanma.
    6. Eğer kayda değer, çok önemli bir haber yoksa veya veriler boşsa sadece "YOK" yaz.
    
    TARANAN VERİLER:
    {raw_data}
    """
    
    response = model.generate_content(prompt)
    return response.text.strip()

def job():
    global last_news_summary
    print(f"[{datetime.now()}] Görev başladı...")
    
    # 1. Haberleri Ara
    raw_news = search_latest_news()
    
    if not raw_news:
        print("Haber bulunamadı.")
        return

    # 2. Gemini ile Analiz Et
    try:
        tweet_content = analyze_and_write_tweet(raw_news)
        
        # Eğer Gemini haber değeri görmediyse
        if tweet_content == "YOK":
            print("Gemini kayda değer bir haber bulamadı.")
            return

        # 3. Tekrar Kontrolü (Basit benzerlik kontrolü)
        # Eğer yeni üretilen tweet, bir öncekiyle çok benzerse atlama.
        if tweet_content == last_news_summary:
            print("Bu haber zaten paylaşıldı (veya çok benzer).")
            return

        print(f"Oluşturulan Tweet: {tweet_content}")

        # 4. Tweet At
        client = get_twitter_conn()
        client.create_tweet(text=tweet_content)
        
        print("Tweet başarıyla gönderildi!")
        last_news_summary = tweet_content # Hafızayı güncelle

    except Exception as e:
        print(f"İşlem sırasında hata: {e}")

# --- ZAMANLAYICI ---
# Her 30 dakikada bir tarama yapsın
schedule.every(30).minutes.do(job)

if __name__ == "__main__":
    print("Yapay Zeka Muhabiri Başlatıldı (Koyeb)...")
    job() # İlk açılışta test et
    while True:
        schedule.run_pending()
        time.sleep(1)
