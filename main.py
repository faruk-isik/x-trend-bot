import tweepy
import time
import os
import threading
import logging
from groq import Groq
import feedparser
from datetime import datetime
import pytz
from flask import Flask, jsonify, request
from difflib import SequenceMatcher
import hashlib
import requests
from io import BytesIO
from PIL import Image

# --- TÜRKIYE SAAT DİLİMİ ---
TR_TZ = pytz.timezone('Europe/Istanbul')

def get_tr_time():
    """Türkiye saatini döndür"""
    return datetime.now(TR_TZ)

def get_tr_time_str():
    """Türkiye saatini string olarak döndür"""
    return get_tr_time().strftime("%Y-%m-%d %H:%M:%S")

# --- LOGLAMA AYARLARI ---
class TurkeyTimeFormatter(logging.Formatter):
    """Türkiye saati ile log formatter"""
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, TR_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

formatter = TurkeyTimeFormatter('%(asctime)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler('bot.log')
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)
logger = logging.getLogger(__name__)

# --- VERSİYON ---
VERSION = "14.0 - Resimli Tweet Desteği"
logger.info(f"VERSION: {VERSION}")

# --- AYARLAR ---
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SECRET_TOKEN = os.getenv("SECRET_TOKEN", "default_secret_change_this")
CRON_SECRET = os.getenv("CRON_SECRET", SECRET_TOKEN)  # Cron için ayrı token

# NTV Son Dakika RSS
MYNET_SON_DAKIKA_RSS = "https://www.mynet.com/haber/rss/sondakika"

SIMILARITY_THRESHOLD = 0.75
MAX_RETRIES = 3

# --- GLOBAL DEĞİŞKENLER ---
last_news_summary = ""
last_tweet_time = "Henüz tweet atılmadı"
tweeted_news_hashes = set()
recent_news_titles = []
tweet_log = []
is_busy = False
total_requests = 0
last_cron_trigger = "Henüz tetiklenmedi"

# --- WEB SUNUCUSU ---
app = Flask(__name__)

@app.route('/')
def home():
    status_emoji = '🔴 Meşgul' if is_busy else '🟢 Hazır'
    trigger_url = f"/trigger?token={SECRET_TOKEN}"
    
    # Tweet log'unu HTML'e çevir
    tweet_log_html = ""
    if tweet_log:
        for log_entry in reversed(tweet_log):
            tweet_log_html += f"""
            <div class="tweet-log-item">
                <div class="tweet-time">🕐 {log_entry['time']}</div>
                <div class="tweet-text">{log_entry['tweet']}</div>
            </div>
            """
    else:
        tweet_log_html = '<p style="color: #999; text-align: center; padding: 20px;">Henüz tweet atılmadı</p>'
    
    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Türkiye Gündemi Botu</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            .container {{
                max-width: 900px;
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
                font-size: 28px;
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
            .cron-info {{
                background: #e8f5e9;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                border-left: 4px solid #4caf50;
            }}
            .cron-info h3 {{
                color: #2e7d32;
                margin-bottom: 10px;
            }}
            .cron-info code {{
                background: white;
                padding: 10px;
                border-radius: 5px;
                display: block;
                margin: 10px 0;
                font-size: 13px;
                word-break: break-all;
            }}
            .tweet-log {{
                background: #f8f9fa;
                padding: 25px;
                border-radius: 10px;
                margin-top: 30px;
            }}
            .tweet-log h2 {{
                color: #667eea;
                margin-bottom: 20px;
                font-size: 20px;
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            .tweet-log-item {{
                background: white;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 12px;
                border-left: 4px solid #667eea;
                transition: all 0.2s;
            }}
            .tweet-log-item:hover {{
                transform: translateX(5px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }}
            .tweet-time {{
                color: #999;
                font-size: 13px;
                margin-bottom: 6px;
            }}
            .tweet-text {{
                color: #333;
                font-size: 15px;
                line-height: 1.5;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🇹🇷 Türkiye Gündemi Botu</h1>
            <span class="status-badge">{status_emoji}</span>
            
            <div class="info-grid">
                <div class="info-card">
                    <h3>📌 Versiyon</h3>
                    <p>14.0</p>
                </div>
                <div class="info-card">
                    <h3>🕐 Son Tweet</h3>
                    <p>{last_tweet_time}</p>
                </div>
                <div class="info-card">
                    <h3>📊 İşlenmiş Haber</h3>
                    <p>{len(tweeted_news_hashes)} adet</p>
                </div>
                <div class="info-card">
                    <h3>📷 Özellik</h3>
                    <p style="font-size: 13px;">Resimli</p>
                </div>
            </div>

            <a href="{trigger_url}" class="trigger-button">
                🚀 ŞİMDİ TWEET AT
            </a>

            <div class="cron-info">
                <h3>⏰ Cron-Job.org Kurulumu</h3>
                <p style="color: #555; margin-bottom: 10px;">
                    <strong>1.</strong> <a href="https://cron-job.org" target="_blank" style="color: #2e7d32;">cron-job.org</a> sitesine gidin ve ücretsiz kayıt olun<br>
                    <strong>2.</strong> "Create Cronjob" butonuna tıklayın<br>
                    <strong>3.</strong> Aşağıdaki ayarları girin:
                </p>
                <div style="background: white; padding: 15px; border-radius: 5px; margin: 10px 0;">
                    <strong>Title:</strong> Türkiye Gündemi Bot<br>
                    <strong>URL:</strong> <code style="display: inline; padding: 2px 6px; background: #f0f0f0;">https://your-app.koyeb.app/cron?secret={CRON_SECRET}</code><br>
                    <strong>Schedule:</strong> Every 1 hour (Her 1 saatte)<br>
                    <strong>Enabled:</strong> ✅ Aktif
                </div>
                <p style="color: #666; font-size: 13px; margin-top: 10px;">
                    💡 <strong>Kaynak:</strong> Mynet Son Dakika RSS<br>
                    💡 <strong>İpucu:</strong> URL'deki "your-app" kısmını Koyeb app adınızla değiştirin
                </p>
            </div>

            <div class="tweet-log">
                <h2>📜 Tweet Geçmişi</h2>
                {tweet_log_html}
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Health check endpoint - Koyeb için"""
    return jsonify({
        "status": "healthy",
        "version": VERSION,
        "uptime": "running",
        "total_requests": total_requests
    })

@app.route('/ping')
def ping():
    """Basit ping endpoint - keep alive için"""
    global total_requests
    total_requests += 1
    return jsonify({"status": "pong", "timestamp": get_tr_time_str()})

@app.route('/status')
def status():
    """Detaylı durum bilgisi"""
    return jsonify({
        "version": VERSION,
        "last_tweet_time": last_tweet_time,
        "last_tweet_content": last_news_summary[:100] + "..." if last_news_summary else "Yok",
        "is_busy": is_busy,
        "processed_news_count": len(tweeted_news_hashes),
        "recent_titles_count": len(recent_news_titles),
        "tweet_log": tweet_log,
        "last_cron_trigger": last_cron_trigger,
        "total_requests": total_requests
    })

@app.route('/cron', methods=['GET', 'POST'])
def cron_trigger():
    """Cron-job.org için özel endpoint"""
    global is_busy, last_cron_trigger
    
    # Secret kontrolü
    secret = request.args.get('secret') or request.headers.get('X-Cron-Secret')
    
    if secret != CRON_SECRET:
        logger.warning(f"❌ Yetkisiz cron denemesi! IP: {request.remote_addr}")
        return jsonify({
            "success": False,
            "error": "Invalid secret"
        }), 401
    
    if is_busy:
        logger.info("⏭️ Bot meşgul, cron atlandı")
        return jsonify({
            "success": False,
            "message": "Bot busy, skipped"
        }), 200
    
    # Tetikleme zamanını kaydet
    last_cron_trigger = get_tr_time_str()
    
    # Arka planda tweet işini başlat
    thread = threading.Thread(target=job, kwargs={"source": "CRON"})
    thread.start()
    
    logger.info(f"⏰ Cron-job tetiklendi! IP: {request.remote_addr}")
    
    return jsonify({
        "success": True,
        "message": "Tweet job started",
        "timestamp": last_cron_trigger
    }), 202

@app.route('/trigger', methods=['POST', 'GET'])
def trigger_tweet():
    """Manuel tetikleme endpoint'i"""
    global is_busy
    
    # Token kontrolü
    if request.method == 'GET':
        token = request.args.get('token')
    else:
        token = request.headers.get('X-Secret-Token') or request.json.get('secret_token') if request.json else None
    
    if SECRET_TOKEN and SECRET_TOKEN != "default_secret_change_this":
        if token != SECRET_TOKEN:
            logger.warning(f"❌ Yetkisiz tetikleme! IP: {request.remote_addr}")
            return """
            <html>
            <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>❌ Yetkisiz Erişim</h1>
                <p>Geçersiz token!</p>
            </body>
            </html>
            """, 401
    
    if is_busy:
        return """
        <html>
        <body style="font-family: Arial; text-align: center; padding: 50px;">
            <h1>⏳ Bot Meşgul</h1>
            <p>Şu anda bir tweet işlemi devam ediyor...</p>
        </body>
        </html>
        """, 429
    
    thread = threading.Thread(target=job, kwargs={"source": "MANUEL"})
    thread.start()
    
    logger.info(f"👤 Manuel tetikleme! IP: {request.remote_addr}")
    
    if request.method == 'GET':
        return """
        <html>
        <head>
            <meta charset="utf-8">
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
                }
                .success-icon { font-size: 80px; }
                h1 { color: #667eea; margin: 20px 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✅</div>
                <h1>Tweet İşlemi Başlatıldı!</h1>
                <p>Mynet Son Dakika haberi işleniyor...</p>
                <p style="color: #999;">~30-60 saniye</p>
                <a href="/" style="display: inline-block; margin-top: 20px; padding: 12px 30px; background: #667eea; color: white; text-decoration: none; border-radius: 25px;">🏠 Ana Sayfa</a>
            </div>
        </body>
        </html>
        """
    
    return jsonify({
        "success": True,
        "message": "Tweet işlemi başlatıldı",
        "timestamp": get_tr_time_str()
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

def get_twitter_api_v1():
    """Twitter API v1.1 - Medya yükleme için"""
    try:
        import tweepy
        auth = tweepy.OAuth1UserHandler(
            X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
        )
        return tweepy.API(auth)
    except Exception as e:
        logger.error(f"Twitter API v1 bağlantı hatası: {e}")
        return None

# --- RESİM İNDİRME VE İŞLEME ---
def download_and_process_image(image_url):
    """Resmi indir ve Twitter için hazırla"""
    try:
        logger.info(f"📷 Resim indiriliyor: {image_url[:60]}...")
        
        # Resmi indir
        response = requests.get(image_url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        if response.status_code != 200:
            logger.warning(f"Resim indirilemedi: HTTP {response.status_code}")
            return None
        
        # Resmi aç
        img = Image.open(BytesIO(response.content))
        
        # Twitter limitleri: Max 5MB, boyut kontrolü
        if len(response.content) > 5 * 1024 * 1024:  # 5MB
            logger.warning("Resim çok büyük (>5MB), boyutlandırılıyor...")
            # Resmi küçült
            img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        
        # JPEG formatına çevir (Twitter uyumluluğu)
        output = BytesIO()
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')
        img.save(output, format='JPEG', quality=85, optimize=True)
        output.seek(0)
        
        logger.info(f"✅ Resim hazırlandı ({len(output.getvalue()) / 1024:.1f} KB)")
        return output
        
    except Exception as e:
        logger.error(f"❌ Resim işleme hatası: {e}")
        return None

def upload_media_to_twitter(image_data):
    """Resmi Twitter'a yükle ve media_id döndür"""
    try:
        api_v1 = get_twitter_api_v1()
        if not api_v1:
            return None
        
        logger.info("📤 Resim Twitter'a yükleniyor...")
        media = api_v1.media_upload(filename="image.jpg", file=image_data)
        logger.info(f"✅ Resim yüklendi: media_id={media.media_id}")
        return media.media_id
        
    except Exception as e:
        logger.error(f"❌ Resim yükleme hatası: {e}")
        return None
def create_news_hash(title, description):
    content = f"{title}|{description}".lower()
    return hashlib.md5(content.encode()).hexdigest()

# --- BENZERLİK KONTROLÜ (GELİŞTİRİLMİŞ) ---
def is_similar_to_recent(title, threshold=SIMILARITY_THRESHOLD):
    """Son tweet'lenen haberlerle benzerlik kontrolü"""
    for recent_title in recent_news_titles:
        ratio = SequenceMatcher(None, title.lower(), recent_title.lower()).ratio()
        if ratio > threshold:
            logger.info(f"❌ Benzer başlık bulundu: {ratio:.2f} benzerlik")
            return True
    return False

def is_duplicate_tweet(new_tweet_text, threshold=0.80):
    """Tweet metninin daha önce atılıp atılmadığını kontrol et"""
    if not tweet_log:
        return False
    
    for log_entry in tweet_log:
        old_tweet = log_entry['tweet']
        ratio = SequenceMatcher(None, new_tweet_text.lower(), old_tweet.lower()).ratio()
        if ratio > threshold:
            logger.warning(f"⚠️ TEKRAR TWEET TESPİT EDİLDİ! Benzerlik: {ratio:.2f}")
            logger.warning(f"Eski: {old_tweet[:60]}...")
            logger.warning(f"Yeni: {new_tweet_text[:60]}...")
            return True
    
    return False

# --- HTML TEMİZLEME ---
def clean_html_content(html_text):
    import re
    text = re.sub(r'<[^>]+>', '', html_text)
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&quot;', '"')
    text = text.replace('&amp;', '&')
    text = text.replace('&#39;', "'")
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

# --- NTV SON DAKİKA HABERLER ---
def fetch_ntv_breaking_news():
    logger.info("📺 NTV Son Dakika haberleri çekiliyor...")
    
    try:
        feed = feedparser.parse(NTV_SON_DAKIKA_RSS)
        
        if not feed.entries:
            logger.error("NTV RSS'den haber alınamadı!")
            return []
        
        news_list = []
        for entry in feed.entries[:15]:
            title = entry.get('title', '').strip()
            
            content = ""
            if hasattr(entry, 'content') and entry.content:
                content = entry.content[0].get('value', '')
            if not content:
                content = entry.get('summary', entry.get('description', ''))
            
            full_content = clean_html_content(content)
            
            link = entry.get('link', '')
            pub_date = entry.get('published', '')
            
            if not title or len(title) < 15:
                continue
            
            news_hash = create_news_hash(title, full_content[:200])
            
            news_list.append({
                'title': title,
                'full_content': full_content,
                'link': link,
                'pub_date': pub_date,
                'hash': news_hash
            })
        
        logger.info(f"✅ {len(news_list)} adet NTV haberi bulundu")
        return news_list
        
    except Exception as e:
        logger.error(f"NTV RSS hatası: {e}")
        return []

# --- TWEET İÇİN HABER SEÇ (GELİŞTİRİLMİŞ) ---
def select_untweeted_news(news_list):
    """Daha önce tweet'lenmemiş ve benzersiz haberi seç"""
    
    suitable_news = []
    
    for news in news_list:
        # 1. Hash kontrolü (aynı haber mi?)
        if news['hash'] in tweeted_news_hashes:
            logger.info(f"⏭️ Atlandı (hash): {news['title'][:50]}...")
            continue
        
        # 2. Başlık benzerlik kontrolü
        if is_similar_to_recent(news['title']):
            logger.info(f"⏭️ Atlandı (benzer başlık): {news['title'][:50]}...")
            continue
        
        # Bu haber uygun, listeye ekle
        suitable_news.append(news)
    
    if not suitable_news:
        logger.warning("⚠️ Hiçbir yeni haber bulunamadı!")
        return None
    
    logger.info(f"✅ {len(suitable_news)} adet uygun haber bulundu")
    
    # En güncel haberi döndür
    selected = suitable_news[0]
    logger.info(f"✅ Seçildi: {selected['title'][:50]}...")
    return selected

# --- GROQ İLE TWEET OLUŞTUR ---
def create_tweet_with_groq(news):
    try:
        content_to_use = news.get('full_content', '')
        if not content_to_use or len(content_to_use) < 50:
            content_to_use = news['title']
        
        if len(content_to_use) > 2000:
            content_to_use = content_to_use[:2000] + "..."
        
        prompt = f"""
Haber Başlığı: {news['title']}

Haber İçeriği:
{content_to_use}

Yukarıdaki haberi TAM 280 karakter kullanarak özetle.

KURALLAR:
1. TAM 280 karaktere yakın kullan (270-280 arası ideal)
2. Haberin ÖNEMLİ detaylarını içer
3. Sayılar, isimler, yerler gibi somut bilgileri ekle
4. Gereksiz kelime kullanma
5. Hashtag KULLANMA
6. Sadece haber özeti yaz, başka hiçbir şey yazma
"""
        
        completion = client_ai.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": """Sen profesyonel bir haber editörüsün. 
Haberleri 280 karakterlik tweet formatında özetliyorsun.
Her karakteri verimli kullan, gereksiz kelime ekleme.
Somut bilgileri (sayı, isim, yer) mutlaka ekle."""
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=400
        )
        
        tweet_text = completion.choices[0].message.content.strip()
        tweet_text = tweet_text.strip('"').strip("'")
        
        if len(tweet_text) > 280:
            logger.warning(f"Tweet çok uzun ({len(tweet_text)} kar), kısaltılıyor...")
            tweet_text = tweet_text[:277].rsplit('.', 1)[0] + '...'
            if len(tweet_text) > 280:
                tweet_text = tweet_text[:277] + '...'
        
        char_count = len(tweet_text)
        logger.info(f"✅ Tweet oluşturuldu ({char_count} karakter)")
        
        return tweet_text
        
    except Exception as e:
        logger.error(f"Groq hatası: {e}")
        return None

# --- ANA GÖREV FONKSİYONU ---
def job(source="MANUEL"):
    global last_news_summary, last_tweet_time, is_busy, tweeted_news_hashes, recent_news_titles, tweet_log
    
    if is_busy:
        logger.warning("Bot meşgul, görev atlandı")
        return
    
    is_busy = True
    max_attempts = 5  # En fazla 5 farklı haber dene
    
    try:
        logger.info("=" * 60)
        logger.info(f"{source} GÖREV BAŞLATILDI: {get_tr_time_str()}")
        
        news_list = fetch_ntv_breaking_news()
        if not news_list:
            logger.error("❌ Haber alınamadı, görev iptal")
            return
        
        # Uygun haber bul ve tweet oluştur (tekrar kontrolü ile)
        for attempt in range(max_attempts):
            logger.info(f"--- Deneme {attempt + 1}/{max_attempts} ---")
            
            selected_news = select_untweeted_news(news_list)
            if not selected_news:
                logger.error("❌ Uygun haber bulunamadı")
                return
            
            # Tweet oluştur
            tweet_text = create_tweet_with_groq(selected_news)
            if not tweet_text:
                logger.error("❌ Tweet oluşturulamadı")
                # Bu haberi hash'e ekle ki bir daha denemesin
                tweeted_news_hashes.add(selected_news['hash'])
                continue
            
            # ÖNEMLİ: Tweet tekrar kontrolü
            if is_duplicate_tweet(tweet_text):
                logger.warning("🔄 Bu tweet daha önce atıldı, başka haber deneniyor...")
                # Bu haberi hash'e ekle
                tweeted_news_hashes.add(selected_news['hash'])
                recent_news_titles.append(selected_news['title'])
                if len(recent_news_titles) > 20:
                    recent_news_titles.pop(0)
                continue
            
            # Tweet benzersiz! Twitter'a gönder
            logger.info("✅ Tweet benzersiz, Twitter'a gönderiliyor...")
            
            client = get_twitter_conn()
            if not client:
                logger.error("❌ Twitter bağlantısı kurulamadı")
                return
            
            response = client.create_tweet(text=tweet_text)
            
            # Başarılı! Kayıtları güncelle
            tweeted_news_hashes.add(selected_news['hash'])
            recent_news_titles.append(selected_news['title'])
            
            if len(recent_news_titles) > 20:
                recent_news_titles.pop(0)
            
            tweet_log.append({
                'time': get_tr_time_str(),
                'tweet': tweet_text
            })
            
            if len(tweet_log) > 10:
                tweet_log.pop(0)
            
            last_news_summary = tweet_text
            last_tweet_time = get_tr_time_str()
            
            logger.info("=" * 60)
            logger.info(f"✅ {source} TWEET GÖNDERİLDİ!")
            logger.info(f"📰 Haber: {selected_news['title'][:60]}...")
            logger.info(f"🐦 Tweet ({len(tweet_text)} kar): {tweet_text}")
            if media_id:
                logger.info(f"📷 Resim: ✅ Eklendi")
            logger.info("=" * 60)
            
            # Başarılı, döngüden çık
            return
        
        # 5 deneme sonunda hala tweet atılamadıysa
        logger.error(f"❌ {max_attempts} deneme sonunda uygun haber bulunamadı!")
        
    except tweepy.errors.TooManyRequests:
        logger.error("❌ Twitter rate limit aşıldı!")
        
    except Exception as e:
        logger.error(f"❌ Hata: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
    finally:
        is_busy = False

# --- WEB SUNUCUSU ---
def run_web_server():
    app.run(host='0.0.0.0', port=8000)

# --- ANA PROGRAM ---
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("SİSTEM BAŞLATILIYOR - CRON MODE")
    logger.info("=" * 60)
    
    # API key kontrolü
    required_keys = [X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, GROQ_API_KEY]
    if not all(required_keys):
        logger.critical("Eksik API anahtarları!")
        exit(1)
    
    logger.info("✅ Bot Cron-Job modunda çalışıyor")
    logger.info(f"⏰ Cron endpoint: /cron?secret={CRON_SECRET}")
    logger.info("📍 Web sunucusu başlatılıyor...")
    
    # Sadece web sunucusu çalıştır (schedule yok!)
    run_web_server()
