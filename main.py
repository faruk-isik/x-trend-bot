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
    return datetime.now(TR_TZ)

def get_tr_time_str():
    return get_tr_time().strftime("%Y-%m-%d %H:%M:%S")

# --- LOGLAMA AYARLARI ---
class TurkeyTimeFormatter(logging.Formatter):
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
VERSION = "14.1 - Resim Fix"
logger.info(f"VERSION: {VERSION}")

# --- AYARLAR ---
X_API_KEY = os.getenv("X_API_KEY")
X_API_SECRET = os.getenv("X_API_SECRET")
X_ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
X_ACCESS_SECRET = os.getenv("X_ACCESS_SECRET")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SECRET_TOKEN = os.getenv("SECRET_TOKEN", "default_secret_change_this")
CRON_SECRET = os.getenv("CRON_SECRET", SECRET_TOKEN)

# MYNET Son Dakika RSS
MYNET_SON_DAKIKA_RSS = "https://www.mynet.com/haber/rss/sondakika"

SIMILARITY_THRESHOLD = 0.75

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
    
    tweet_log_html = ""
    if tweet_log:
        for log_entry in reversed(tweet_log):
            tweet_log_html += f"""
            <div class="tweet-log-item">
                <div class="tweet-time">🕐 {log_entry['time']}</div>
                <div class="tweet-text">{log_entry['tweet']}</div>
                <div class="tweet-text" style="font-size:12px; color: #666;">{'📷 Resimli' if log_entry.get('has_image') else '📄 Metin'}</div>
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
            body {{ font-family: 'Segoe UI', sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }}
            .container {{ max-width: 900px; margin: 0 auto; background: white; border-radius: 20px; padding: 40px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }}
            h1 {{ color: #667eea; margin-bottom: 10px; font-size: 28px; }}
            .status-badge {{ display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: bold; background: {'#ff4444' if is_busy else '#00C851'}; color: white; }}
            .info-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }}
            .info-card {{ background: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #667eea; }}
            .trigger-button {{ display: block; width: 100%; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-align: center; text-decoration: none; border-radius: 10px; font-size: 20px; font-weight: bold; margin: 20px 0; }}
            .tweet-log {{ background: #f8f9fa; padding: 25px; border-radius: 10px; margin-top: 30px; }}
            .tweet-log-item {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 12px; border-left: 4px solid #667eea; }}
            .tweet-time {{ color: #999; font-size: 13px; margin-bottom: 6px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🇹🇷 Türkiye Gündemi Botu</h1>
            <span class="status-badge">{status_emoji}</span>
            
            <div class="info-grid">
                <div class="info-card"><h3>📌 Versiyon</h3><p>{VERSION}</p></div>
                <div class="info-card"><h3>🕐 Son Tweet</h3><p>{last_tweet_time}</p></div>
                <div class="info-card"><h3>📊 İşlenmiş Haber</h3><p>{len(tweeted_news_hashes)} adet</p></div>
            </div>

            <a href="{trigger_url}" class="trigger-button">🚀 ŞİMDİ TWEET AT</a>

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
    return jsonify({"status": "healthy", "version": VERSION, "uptime": "running"})

@app.route('/cron', methods=['GET', 'POST'])
def cron_trigger():
    global is_busy, last_cron_trigger
    secret = request.args.get('secret') or request.headers.get('X-Cron-Secret')
    
    if secret != CRON_SECRET:
        return jsonify({"success": False, "error": "Invalid secret"}), 401
    
    if is_busy:
        return jsonify({"success": False, "message": "Bot busy"}), 200
    
    last_cron_trigger = get_tr_time_str()
    thread = threading.Thread(target=job, kwargs={"source": "CRON"})
    thread.start()
    return jsonify({"success": True, "message": "Job started"}), 202

@app.route('/trigger', methods=['POST', 'GET'])
def trigger_tweet():
    global is_busy
    if request.method == 'GET':
        token = request.args.get('token')
    else:
        token = request.headers.get('X-Secret-Token')
    
    if SECRET_TOKEN != "default_secret_change_this" and token != SECRET_TOKEN:
        return "Unauthorized", 401
    
    if is_busy:
        return "Bot Busy", 429
    
    thread = threading.Thread(target=job, kwargs={"source": "MANUEL"})
    thread.start()
    return jsonify({"success": True}), 202

# --- CLIENTS ---
client_ai = Groq(api_key=GROQ_API_KEY)

def get_twitter_conn():
    try:
        return tweepy.Client(consumer_key=X_API_KEY, consumer_secret=X_API_SECRET, access_token=X_ACCESS_TOKEN, access_token_secret=X_ACCESS_SECRET)
    except Exception as e:
        logger.error(f"Twitter V2 Error: {e}")
        return None

def get_twitter_api_v1():
    try:
        auth = tweepy.OAuth1UserHandler(X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET)
        return tweepy.API(auth)
    except Exception as e:
        logger.error(f"Twitter V1 Error: {e}")
        return None

# --- RESİM İŞLEME ---
def download_and_process_image(image_url):
    try:
        logger.info(f"📷 Resim indiriliyor: {image_url[:60]}...")
        response = requests.get(image_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code != 200: return None
        
        img = Image.open(BytesIO(response.content))
        if len(response.content) > 4 * 1024 * 1024:
            img.thumbnail((1200, 1200), Image.Resampling.LANCZOS)
        
        output = BytesIO()
        if img.mode in ('RGBA', 'LA', 'P'): img = img.convert('RGB')
        img.save(output, format='JPEG', quality=85)
        output.seek(0)
        return output
    except Exception as e:
        logger.error(f"Resim işleme hatası: {e}")
        return None

def upload_media_to_twitter(image_data):
    try:
        api_v1 = get_twitter_api_v1()
        if not api_v1: return None
        media = api_v1.media_upload(filename="image.jpg", file=image_data)
        logger.info(f"✅ Media ID alındı: {media.media_id}")
        return media.media_id
    except Exception as e:
        logger.error(f"Resim upload hatası: {e}")
        return None

def create_news_hash(title, description):
    content = f"{title}|{description}".lower()
    return hashlib.md5(content.encode()).hexdigest()

def is_duplicate_tweet(new_tweet_text, threshold=0.80):
    if not tweet_log: return False
    for log_entry in tweet_log:
        ratio = SequenceMatcher(None, new_tweet_text.lower(), log_entry['tweet'].lower()).ratio()
        if ratio > threshold: return True
    return False

def clean_html_content(html_text):
    import re
    text = re.sub(r'<[^>]+>', '', html_text)
    text = text.replace('&nbsp;', ' ').replace('&quot;', '"').replace('&amp;', '&').replace('&#39;', "'")
    return re.sub(r'\s+', ' ', text).strip()

# --- HABER ÇEKME (V4 - 640x360 FORMATI) ---
def fetch_ntv_breaking_news():
    logger.info("📺 RSS taranıyor (img640x360 öncelikli)...")
    try:
        # User-agent önemli, bazen botları engelliyorlar
        feed = feedparser.parse(MYNET_SON_DAKIKA_RSS, agent="Mozilla/5.0")
        
        if not feed.entries:
            logger.error("❌ RSS içeriği boş geldi!")
            return []
        
        news_list = []
        for entry in feed.entries[:15]:
            title = entry.get('title', '').strip()
            
            # İçerik temizleme
            raw_summary = entry.get('summary', '')
            raw_desc = entry.get('description', '')
            full_html = raw_summary + " " + raw_desc
            content = clean_html_content(full_html)
            
            # --- RESİM ARAMA STRATEJİSİ ---
            image_url = None
            
            # 1. EN İYİ SEÇENEK: Sizin bulduğunuz 640x360 etiketi
            # Bu, Twitter için mükemmel bir 16:9 orandır.
            if 'img640x360' in entry:
                image_url = entry.img640x360
                logger.info(f"🎯 640x360 Resim Bulundu: {title[:15]}...")

            # 2. YEDEK SEÇENEK: Eğer 640x360 yoksa 300x300'e bak
            elif 'img300x300' in entry:
                image_url = entry.img300x300
                # Yine de şansımızı deneyip bunu büyütmeyi deneyebiliriz
                if image_url and "300x300" in image_url:
                    image_url = image_url.replace("300x300", "640xauto")
                logger.info(f"🔎 300x300 Resim Bulundu (Yedek): {title[:15

def select_untweeted_news(news_list):
    suitable = [n for n in news_list if n['hash'] not in tweeted_news_hashes]
    return suitable[0] if suitable else None

def create_tweet_with_groq(news):
    try:
        prompt = f"Haber: {news['title']}\nDetay: {news['full_content']}\nBu haberi 240 karakteri geçmeyecek şekilde, ciddi bir dille, hashtag kullanmadan özetle."
        completion = client_ai.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "Sen bir haber editörüsün. Sadece özeti yaz."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=200
        )
        return completion.choices[0].message.content.strip().replace('"', '')
    except Exception as e:
        logger.error(f"Groq hatası: {e}")
        return None

# --- ANA GÖREV (DÜZELTİLDİ) ---
def job(source="MANUEL"):
    global last_news_summary, last_tweet_time, is_busy, tweeted_news_hashes, tweet_log
    
    if is_busy: return
    is_busy = True
    
    try:
        logger.info(f"{source} İşlem Başladı...")
        news_list = fetch_ntv_breaking_news()
        
        # 5 deneme hakkı
        for _ in range(5):
            selected_news = select_untweeted_news(news_list)
            if not selected_news:
                logger.warning("Yeni haber yok.")
                break
                
            tweet_text = create_tweet_with_groq(selected_news)
            if not tweet_text: continue
            
            if is_duplicate_tweet(tweet_text):
                tweeted_news_hashes.add(selected_news['hash'])
                continue
            
            # --- RESİM İŞLEMLERİ (YENİ EKLENDİ) ---
            media_id = None
            if selected_news.get('image_url'):
                img_data = download_and_process_image(selected_news['image_url'])
                if img_data:
                    media_id = upload_media_to_twitter(img_data)
            
            # --- TWEET GÖNDERME ---
            client = get_twitter_conn()
            if not client: break
            
            if media_id:
                client.create_tweet(text=tweet_text, media_ids=[media_id])
                logger.info("✅ Resimli Tweet atıldı!")
            else:
                client.create_tweet(text=tweet_text)
                logger.info("✅ Yazılı Tweet atıldı (Resim yoktu veya hata oluştu).")
            
            # Kayıtları güncelle
            tweeted_news_hashes.add(selected_news['hash'])
            last_news_summary = tweet_text
            last_tweet_time = get_tr_time_str()
            tweet_log.append({
                'time': last_tweet_time,
                'tweet': tweet_text,
                'has_image': media_id is not None
            })
            if len(tweet_log) > 10: tweet_log.pop(0)
            
            break # Başarılı olduysa döngüden çık
            
    except Exception as e:
        logger.error(f"Job hatası: {e}")
    finally:
        is_busy = False

if __name__ == "__main__":
    if not all([X_API_KEY, GROQ_API_KEY]):
        logger.critical("API Key eksik!")
    else:
        app.run(host='0.0.0.0', port=8000)
