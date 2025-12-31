import tweepy
import os
import re
import logging
import textwrap
from flask import Flask
from google import genai
from google.genai import types

# --- Log Ayarları ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. X (Twitter) API Bağlantısı ---
def get_v2_client():
    try:
        client = tweepy.Client(
            consumer_key=os.environ.get('CONSUMER_KEY'),
            consumer_secret=os.environ.get('CONSUMER_SECRET'),
            access_token=os.environ.get('ACCESS_TOKEN'),
            access_token_secret=os.environ.get('ACCESS_TOKEN_SECRET')
        )
        logging.info("✅ X V2 İstemcisi Başarıyla Oluşturuldu!")
        return client
    except Exception as e:
        logging.error(f"❌ X API Bağlantı Hatası: {e}")
        return None

# --- 2. Metin Temizleme Mekanizması ---
def absolute_cleaner(text):
    """Hashtag, emoji ve gereksiz etiketleri temizleyen kesin çözüm."""
    if not text:
        return ""

    # 1. Tüm Hashtagleri (#Kelime) siler
    text = re.sub(r'#\S+', '', text)

    # 2. Satırlara böl ve 'Başlık:', 'Kategori:' veya çok kısa son satırları temizle
    lines = []
    for line in text.split('\n'):
        line = line.strip()
        # Boş satırları veya sadece etiket olan kısa satırları (örn: 'Ekonomi') atla
        if not line or len(line.split()) <= 2:
            continue
        lines.append(line)
    
    clean_text = " ".join(lines)

    # 3. Emojileri ve ASCII dışı özel karakterleri kazı
    clean_text = clean_text.encode('ascii', 'ignore').decode('ascii')

    # 4. Çift boşlukları temizle
    clean_text = " ".join(clean_text.split()).strip()

    return clean_text

# --- 3. Gemini 2.0 İçerik Üretimi ---
def generate_gemini_tweet():
    fallback_text = "Türkiye gündemindeki gelişmeleri takip ediyoruz."
    
    try:
        client = genai.Client(api_key=os.environ.get('GEMINI_API_KEY'))
        
        # Modelin 'sosyal medya' alışkanlıklarını kırmak için sert talimatlar
        system_rules = (
            "Sen tarafsız bir haber ajansı muhabirisin. Sadece ham haber metni yazarsın. "
            "Görevin: Google Search kullanarak bulduğun bir haberi 2 veya 3 cümleyle anlatmak. "
            "KESİN YASAKLAR: Hashtag (#) kullanma, emoji kullanma, başlık atma, sonuna kategori ekleme. "
            "Sadece düz metin gönder."
        )
        
        user_prompt = (
            "Türkiye gündeminden en güncel ve somut haberi bul. "
            "Bu haber hakkında 250 karakteri geçmeyen tarafsız bir bilgi notu yaz."
        )
        
        logging.info("--- Gemini İçerik Üretimi Başladı ---")
        
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_rules,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.0 # Talimatlara maksimum sadakat
            )
        )
        
        raw_text = response.text.strip() if response.text else fallback_text
        
        # Kod seviyesinde filtreleme
        final_text = absolute_cleaner(raw_text)
        
        # Eğer temizlikten sonra metin boş kalırsa fallback kullan
        return final_text if final_text else fallback_text

    except Exception as e:
        logging.error(f"❌ Gemini Hatası: {e}")
        return fallback_text

# --- 4. Bot Çalıştırma ---
def run_bot():
    x_client = get_v2_client()
    if not x_client: return
    
    content = generate_gemini_tweet()
    
    try:
        # X'in karakter sınırına karşı son güvenlik önlemi
        content = textwrap.shorten(content, width=275, placeholder="...")
        
        x_client.create_tweet(text=content)
        logging.info(f"🚀 Tweet Başarıyla Atıldı: {content}")
    except Exception as e:
        logging.error(f"❌ Tweet Gönderim Hatası: {e}")

# --- 5. Flask Sunucu ---
app = Flask(__name__)

@app.route('/trigger')
def trigger():
    run_bot()
    return "Bot tetiklendi ve süreç tamamlandı.", 200

@app.route('/')
def home():
    return "Haber Botu Çalışıyor...", 200

if __name__ == "__main__":
    # Render veya diğer cloud platformları için port ayarı
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
