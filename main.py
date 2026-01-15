import tweepy
import schedule
import time
import os
import threading
import logging
from groq import Groq
from ddgs import DDGS
from datetime import datetime
from flask import Flask, jsonify, request
from difflib import SequenceMatcher
import hashlib

# --- LOGLAMA AYARLARI ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- VERSİYON ---
VERSION = "11.0 - Manuel Tetikleme Desteği"
logger.info(f"VERSION: {VERSION}")

# --- AYARLAR ---
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SECRET_TOKEN = os.getenv("SECRET_TOKEN", "default_secret_change_this")  # Güvenlik için

SIMILARITY_THRESHOLD = 0.85
MAX_RETRIES = 3
RETRY_DELAY = 60

# --- GLOBAL DEĞİŞKENLER ---
last_news_summary = ""
last_tweet_time = "Henüz tweet atılmadı"
tweet_history = []
is_busy = False  # İşlem kilitlemesi için

# --- WEB SUNUCUSU ---
app = Flask(__name__)

@app.route('/')
def home():
    status_emoji = '🔴 Meşgul' if is_busy else '🟢 Hazır'
    trigger_url = f"/trigger?token={SECRET_TOKEN}"
    
    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Türkiye Haber Botu</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            h1 {{
                color: #667eea;
                margin-bottom: 10px;
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .status-badge {{
                display: inline-block;
                padding: 8px 16px;
                border-radius: 20px;
                font-size: 14px;
                font-weight: bold;
                background: {'#ff4444' if is_busy else '#00C851'};
                color: white;
            }}
            .info-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }}
            .info-card {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                border-left: 4px solid #667eea;
            }}
            .info-card h3 {{
                color: #667eea;
                font-size: 14px;
                margin-bottom: 8px;
            }}
            .info-card p {{
                color: #333;
                font-size: 16px;
                font-weight: bold;
            }}
            .trigger-button {{
                display: block;
                width: 100%;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                text-align: center;
                text-decoration: none;
                border-radius: 10px;
                font-size: 20px;
                font-weight: bold;
                transition: all 0.3s;
                border: none;
                cursor: pointer;
                margin: 20px 0;
            }}
            .trigger-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 10px 30px rgba(102, 126, 234, 0.4);
            }}
            .trigger-button:disabled {{
                background: #ccc;
                cursor: not-allowed;
            }}
            .endpoints {{
                background: #f8f9fa;
                padding: 20px;
                border-radius: 10px;
                margin-top: 20px;
            }}
            .endpoints h3 {{
                color: #667eea;
                margin-bottom: 15px;
            }}
            .endpoint {{
                background: white;
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
                font-family: 'Courier New', monospace;
            }}
            .link-box {{
                background: #fff3cd;
                border: 2px solid #ffc107;
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
            }}
            .link-box strong {{
                color: #856404;
            }}
            .link-box code {{
                display: block;
                background: white;
                padding: 10px;
                border-radius: 5px;
                margin-top: 10px;
                word-break: break-all;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 Türkiye Haber Botu</h1>
            <span class="status-badge">{status_emoji}</span>
            
            <div class="info-grid">
                <div class="info-card">
                    <h3>📌 Versiyon</h3>
                    <p>{VERSION}</p>
                </div>
                <div class="info-card">
                    <h3>🕐 Son Tweet</h3>
                    <p>{last_tweet_time}</p>
                </div>
                <div class="info-card">
                    <h3>📊 Tweet Sayısı</h3>
                    <p>{len(tweet_history)} kayıt</p>
                </div>
            </div>

            <a href="{trigger_url}" class="trigger-button" {'disabled' if is_busy else ''}>
                🚀 ŞİMDİ TWEET AT
            </a>

            <div class="link-box">
                <strong>🔗 TEK TIKLA TWEET LINKI:</strong>
                <code id="triggerLink">https://your-app.koyeb.app{trigger_url}</code>
                <button onclick="copyLink()" style="margin-top: 10px; padding: 8px 16px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer;">
                    📋 Linki Kopyala
                </button>
            </div>

            <div class="endpoints">
                <h3>📡 API Endpoints</h3>
                <div class="endpoint">GET /health - Sağlık kontrolü</div>
                <div class="endpoint">GET /status - Detaylı durum</div>
                <div class="endpoint">GET /trigger?token=YOUR_TOKEN - Manuel tetikleme</div>
            </div>
        </div>

        <script>
            function copyLink() {{
                const link = document.getElementById('triggerLink').innerText;
                navigator.clipboard.writeText(link);
                alert('✅ Link kopyalandı!');
            }}
        </script>
    </body>
    </html>
    """

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "version": VERSION,
        "last_tweet": last_tweet_time,
        "is_busy": is_busy,
        "tweet_count": len(tweet_history)
    })

@app.route('/status')
def status():
    """Detaylı durum bilgisi"""
    return jsonify({
        "version": VERSION,
        "last_tweet_time": last_tweet_time,
        "last_tweet_content": last_news_summary[:100] + "..." if last_news_summary else "Yok",
        "is_busy": is_busy,
        "tweet_history_count": len(tweet_history),
        "uptime": "Bot çalışıyor"
    })

@app.route('/trigger', methods=['POST', 'GET'])
def trigger_tweet():
    """Manuel tweet tetikleme endpoint'i (POST veya GET)"""
    global is_busy
    
    # Güvenlik kontrolü - GET için URL parametresi, POST için header/body
    if request.method == 'GET':
        token = request.args.get('token')
    else:
        token = request.headers.get('X-Secret-Token') or request.json.get('secret_token') if request.json else None
    
    if token != SECRET_TOKEN:
        logger.warning(f"Yetkisiz tetikleme denemesi! IP: {request.remote_addr}")
        return """
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>❌ Yetkisiz Erişim</h1>
            <p>Geçersiz token!</p>
        </body>
        </html>
        """, 401
    
    # İşlem kilidi kontrolü
    if is_busy:
        return """
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>⏳ Bot Meşgul</h1>
            <p>Şu anda bir tweet işlemi devam ediyor, lütfen bekleyin...</p>
            <a href="javascript:location.reload()">🔄 Yenile</a>
        </body>
        </html>
        """, 429
    
    # Arka planda çalıştır
    thread = threading.Thread(target=job, kwargs={"manual": True})
    thread.start()
    
    logger.info(f"Manuel tetikleme başlatıldı! IP: {request.remote_addr}")
    
    # GET isteği için HTML yanıt
    if request.method == 'GET':
        return """
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }
                .container {
                    background: white;
                    padding: 40px;
                    border-radius: 20px;
                    box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                    text-align: center;
                    max-width: 500px;
                }
                .success-icon {
                    font-size: 80px;
                    animation: bounce 1s infinite;
                }
                @keyframes bounce {
                    0%, 100% { transform: translateY(0); }
                    50% { transform: translateY(-20px); }
                }
                h1 { color: #667eea; margin: 20px 0; }
                p { color: #666; font-size: 18px; }
                .info { 
                    background: #f0f0f0; 
                    padding: 15px; 
                    border-radius: 10px; 
                    margin-top: 20px;
                    font-size: 14px;
                }
                .btn {
                    display: inline-block;
                    margin-top: 20px;
                    padding: 12px 30px;
                    background: #667eea;
                    color: white;
                    text-decoration: none;
                    border-radius: 25px;
                    transition: all 0.3s;
                }
                .btn:hover {
                    background: #764ba2;
                    transform: scale(1.05);
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✅</div>
                <h1>Tweet İşlemi Başlatıldı!</h1>
                <p>Haber botunuz şu anda en güncel haberi arıyor ve tweet hazırlıyor.</p>
                <div class="info">
                    <strong>⏱ Süre:</strong> ~30-60 saniye<br>
                    <strong>🕐 Zaman:</strong> """ + datetime.now().strftime("%H:%M:%S") + """
                </div>
                <a href="/status" class="btn">📊 Durumu Kontrol Et</a>
            </div>
        </body>
        </html>
        """
    
    # POST isteği için JSON yanıt
    return jsonify({
        "success": True,
        "message": "Tweet işlemi başlatıldı",
        "timestamp": datetime.now().isoformat()
    }), 202

# --- GROQ CLIENT ---
client_ai = Groq(api_key=GROQ_API_KEY)

# --- TWITTER BAĞLANTISI ---
def get_twitter_conn():
    try:
        return tweepy.Client(
            consumer_key=X_API_KEY,
            consumer_secret=X_API_SECRET,
            access_token=X_ACCESS_TOKEN,
            access_token_secret=X_ACCESS_SECRET
        )
    except Exception as e:
        logger.error(f"Twitter bağlantı hatası: {e}")
        return None

# --- BENZERLİK KONTROLÜ ---
def is_similar(text1, text2, threshold=SIMILARITY_THRESHOLD):
    if not text1 or not text2:
        return False
    ratio = SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    return ratio > threshold

# --- HABER ARAMA ---
def search_latest_news(retry_count=0):
    logger.info("İnternet taranıyor...")
    news_results = []
    
    try:
        with DDGS() as ddgs:
            results = ddgs.text(
                "Türkiye gündemi son dakika haber", 
                region='tr-tr', 
                timelimit='d', 
                max_results=15
            )
            
            if not results:
                logger.warning("Arama sonucu bulunamadı")
                return None
                
            for r in results:
                title = r.get('title', '')
                body = r.get('body', '')
                source = r.get('href', '')
                news_results.append(f"Başlık: {title}\nDetay: {body}\nKaynak: {source}\n---")
                
    except Exception as e:
        logger.error(f"Arama hatası (deneme {retry_count + 1}): {e}")
        if retry_count < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return search_latest_news(retry_count + 1)
        return None
    
    return "\n".join(news_results)

# --- GROQ İLE ANALİZ ---
def analyze_and_write_tweet(raw_data, retry_count=0):
    if not raw_data:
        return None
    
    try:
        completion = client_ai.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system", 
                    "content": """Sen profesyonel bir haber editörüsün.

GÖREVİN:
1. Verilen haberlerden EN ÖNEMLİ ve GÜNCEL olanı seç
2. Objektif, tarafsız dille 270 karakter içinde özetle
3. Resmi haber ajansı tarzında yaz
4. Hashtag KULLANMA
5. Eğer hiçbir haber önemli değilse sadece "YOK" yaz

ÖRNEK: "Ekonomi Bakanı bugün açıkladığı yeni teşvik paketinde KOBİ'lere 5 milyar TL destek sağlanacağını bildirdi. Paket önümüzdeki ay yürürlüğe girecek."
"""
                },
                {
                    "role": "user", 
                    "content": f"Şu güncel verilerden bir haber bülteni oluştur:\n\n{raw_data}"
                }
            ],
            temperature=0.7,
            max_tokens=300
        )
        
        result = completion.choices[0].message.content.strip()
        
        if len(result) > 280:
            result = result[:277] + "..."
            
        return result
        
    except Exception as e:
        logger.error(f"Groq API hatası (deneme {retry_count + 1}): {e}")
        if retry_count < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
            return analyze_and_write_tweet(raw_data, retry_count + 1)
        return None

# --- ANA GÖREV FONKSİYONU ---
def job(manual=False):
    """Ana görev fonksiyonu"""
    global last_news_summary, last_tweet_time, tweet_history, is_busy
    
    # İşlem kilidi
    if is_busy:
        logger.warning("Bot meşgul, görev atlandı")
        return
    
    is_busy = True
    trigger_type = "MANUEL" if manual else "OTOMATİK"
    
    try:
        logger.info("=" * 50)
        logger.info(f"{trigger_type} GÖREV BAŞLATILDI: {datetime.now()}")
        
        # 1. Haberleri ara
        raw_news = search_latest_news()
        if not raw_news:
            logger.warning("Haber bulunamadı, görev sonlandı")
            return
        
        # 2. Tweet oluştur
        tweet_content = analyze_and_write_tweet(raw_news)
        
        if not tweet_content or tweet_content == "YOK":
            logger.info("Paylaşılacak önemli haber yok")
            return
        
        # 3. Benzerlik kontrolü
        for old_tweet in tweet_history:
            if is_similar(tweet_content, old_tweet):
                logger.info("Bu haber yakın zamanda paylaşılmış, atlanıyor")
                return
        
        # 4. Twitter'a gönder
        client = get_twitter_conn()
        if not client:
            logger.error("Twitter bağlantısı kurulamadı")
            return
            
        response = client.create_tweet(text=tweet_content)
        
        logger.info(f"✅ {trigger_type} TWEET GÖNDERİLDİ: {tweet_content}")
        
        # Geçmişi güncelle
        tweet_history.append(tweet_content)
        if len(tweet_history) > 10:
            tweet_history.pop(0)
            
        last_news_summary = tweet_content
        last_tweet_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    except tweepy.errors.TooManyRequests as e:
        logger.error(f"Rate limit aşıldı: {e}")
        
    except Exception as e:
        logger.error(f"Tweet gönderme hatası: {e}")
        
    finally:
        is_busy = False
        logger.info(f"{trigger_type} GÖREV TAMAMLANDI")

# --- WEB SUNUCUSU BAŞLATICI ---
def run_web_server():
    app.run(host='0.0.0.0', port=8000)

# --- ANA PROGRAM ---
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("SİSTEM BAŞLATILIYOR")
    logger.info("=" * 50)
    
    # API key kontrolü
    required_keys = [X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, GROQ_API_KEY]
    if not all(required_keys):
        logger.critical("Eksik API anahtarları! Lütfen environment variables kontrol edin.")
        exit(1)
    
    if SECRET_TOKEN == "default_secret_change_this":
        logger.warning("⚠️ SECRET_TOKEN varsayılan değerde! Lütfen güvenli bir token belirleyin.")
    
    # Web sunucusunu başlat
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info("Web sunucusu başlatıldı (port 8000)")
    
    # İlk çalıştırma
    logger.info("İlk görev çalıştırılıyor...")
    job()
    
    # Zamanlanmış görevler - 1 SAAT
    schedule.every(1).hour.do(job)
    logger.info("Bot 1 saatlik döngüye alındı")
    
    # Ana döngü
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Bot manuel olarak durduruldu")
    except Exception as e:
        logger.critical(f"Kritik hata: {e}")
        raise
