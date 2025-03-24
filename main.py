import os
import sqlite3
import time
import pandas as pd
import numpy as np
import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException
from binance.enums import *
from telebot import TeleBot, types
import threading
import schedule
from datetime import datetime
import matplotlib.pyplot as plt
import io
from dotenv import load_dotenv

# Ayarları yükle
load_dotenv()

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mikabot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Yapılandırma
config = {
    'TELEGRAM_TOKEN': os.getenv('TELEGRAM_TOKEN'),
    'BINANCE_API_KEY': os.getenv('BINANCE_API_KEY'),
    'BINANCE_API_SECRET': os.getenv('BINANCE_API_SECRET'),
    'ADMIN_USER_ID': int(os.getenv('ADMIN_USER_ID')),
    'INTERVALS': {
        '1m': KLINE_INTERVAL_1MINUTE,
        '5m': KLINE_INTERVAL_5MINUTE,
        '15m': KLINE_INTERVAL_15MINUTE,
        '1h': KLINE_INTERVAL_1HOUR,
        '4h': KLINE_INTERVAL_4HOUR,
        '1d': KLINE_INTERVAL_1DAY
    }
}

# Telegram Bot'u başlat
bot = TeleBot(config['TELEGRAM_TOKEN'])

# Binance Client'ı başlat
client = None
try:
    client = Client(config['BINANCE_API_KEY'], config['BINANCE_API_SECRET'])
    logger.info("Binance client başarıyla başlatıldı.")
except Exception as e:
    logger.error(f"Binance client başlatılamadı: {e}")

# Veritabanı ayarları
DB_PATH = 'mikabot.db'

def init_db():
    """Veritabanını başlat ve tabloları oluştur."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        api_key TEXT,
        api_secret TEXT,
        spot_enabled INTEGER DEFAULT 0,
        futures_enabled INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS price_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        symbol TEXT,
        price REAL,
        above_below TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        triggered INTEGER DEFAULT 0
    )
    ''')

    conn.commit()
    conn.close()

init_db()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    return user_data

def update_user_data(user_id, **kwargs):
    user_data = get_user_data(user_id)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if user_data:
        cursor.execute('''
        UPDATE users SET
        api_key = ?,
        api_secret = ?,
        spot_enabled = ?,
        futures_enabled = ?
        WHERE user_id = ?
        ''', (
            kwargs.get('api_key', user_data[1]),
            kwargs.get('api_secret', user_data[2]),
            kwargs.get('spot_enabled', user_data[3]),
            kwargs.get('futures_enabled', user_data[4]),
            user_id
        ))
    else:
        cursor.execute('''
        INSERT INTO users (user_id, api_key, api_secret, spot_enabled, futures_enabled)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            user_id,
            kwargs.get('api_key', ''),
            kwargs.get('api_secret', ''),
            kwargs.get('spot_enabled', 0),
            kwargs.get('futures_enabled', 0)
        ))
    conn.commit()
    conn.close()

# Keyboard tasarımı
def create_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    
    # 1. Satır - Hızlı Erişim
    row1 = [
        types.KeyboardButton("💰 Bakiye Sorgula"),
        types.KeyboardButton("📊 BTC Fiyat")
    ]
    
    # 2. Satır - Spot İşlemler
    row2 = [
        types.KeyboardButton("🟢 Hızlı Alım"),
        types.KeyboardButton("🔴 Hızlı Satış")
    ]
    
    # 3. Satır - Analiz Araçları
    row3 = [
        types.KeyboardButton("📈 BTC Analiz"),
        types.KeyboardButton("🚨 Alarmlarım")
    ]
    
    # 4. Satır - Yardım
    row4 = [
        types.KeyboardButton("ℹ️ Bot Komutları"),
        types.KeyboardButton("⚙️ API Ayarları")
    ]
    
    keyboard.add(*row1, *row2, *row3, *row4)
    return keyboard

# API Ekleme Komutu
@bot.message_handler(commands=['apiekle'])
def add_api_keys(message):
    try:
        args = message.text.split()[1:]
        if len(args) < 2:
            bot.reply_to(message, "❌ Hatalı kullanım. Doğru format: /apiekle API_KEY API_SECRET")
            return

        api_key = args[0]
        api_secret = args[1]
        user_id = message.from_user.id

        # API anahtarlarını test et
        try:
            test_client = Client(api_key, api_secret)
            test_client.get_account()
        except Exception as e:
            bot.reply_to(message, f"❌ API anahtarları geçersiz: {str(e)}")
            return

        update_user_data(user_id, api_key=api_key, api_secret=api_secret)
        bot.reply_to(message, "✅ API anahtarları başarıyla eklendi ve doğrulandı!")
    except Exception as e:
        bot.reply_to(message, f"❌ Hata: {str(e)}")

# Spot İşlem Komutları
@bot.message_handler(commands=['spotac'])
def enable_spot(message):
    user_id = message.from_user.id
    update_user_data(user_id, spot_enabled=1)
    bot.reply_to(message, "✅ Spot işlemleri etkinleştirildi!", reply_markup=create_keyboard())

@bot.message_handler(commands=['spotkapat'])
def disable_spot(message):
    user_id = message.from_user.id
    update_user_data(user_id, spot_enabled=0)
    bot.reply_to(message, "✅ Spot işlemleri devre dışı bırakıldı!", reply_markup=create_keyboard())

# Piyasa Komutları
@bot.message_handler(commands=['piyasa'])
def market_data(message):
    try:
        args = message.text.split()[1:]
        if len(args) < 1:
            bot.reply_to(message, "❌ Hatalı kullanım. Doğru format: /piyasa BTCUSDT")
            return

        symbol = args[0].upper()
        ticker = client.get_symbol_ticker(symbol=symbol)
        bot.reply_to(message, f"📊 {symbol} Anlık Fiyat: {ticker['price']}")
    except Exception as e:
        bot.reply_to(message, f"❌ Hata: {str(e)}")

# Grafik Komutu
@bot.message_handler(commands=['grafik'])
def chart_command(message):
    try:
        args = message.text.split()[1:]
        if len(args) < 2:
            bot.reply_to(message, "❌ Hatalı kullanım. Doğru format: /grafik BTCUSDT 1h")
            return

        symbol = args[0].upper()
        interval = args[1]

        if interval not in config['INTERVALS']:
            bot.reply_to(message, f"❌ Geçersiz aralık. Kullanılabilir aralıklar: {', '.join(config['INTERVALS'].keys())}")
            return

        # Binance'ten fiyat verilerini çekiyoruz
        klines = client.get_historical_klines(symbol, config['INTERVALS'][interval], "7 days ago UTC")

        # Fiyat verilerini işliyoruz (Timestamp, Open, High, Low, Close)
        times = [datetime.utcfromtimestamp(kline[0] / 1000) for kline in klines]
        closes = [float(kline[4]) for kline in klines]

        # Grafik oluşturma
        plt.figure(figsize=(10, 5))
        plt.plot(times, closes, label=f"{symbol} Fiyatı")
        plt.title(f"{symbol} {interval} Fiyat Grafiği")
        plt.xlabel("Zaman")
        plt.ylabel("Fiyat (USDT)")
        plt.xticks(rotation=45)
        plt.grid(True)
        plt.tight_layout()

        # Grafiği Telegram'a gönder
        img_buf = io.BytesIO()
        plt.savefig(img_buf, format='png')
        img_buf.seek(0)
        bot.send_photo(message.chat.id, img_buf)

    except Exception as e:
        bot.reply_to(message, f"❌ Hata: {str(e)}")

# Analiz Komutu
@bot.message_handler(commands=['analiz'])
def analyze_command(message):
    try:
        args = message.text.split()[1:]
        if len(args) < 2:
            bot.reply_to(message, "❌ Hatalı kullanım. Doğru format: /analiz BTCUSDT 4h")
            return

        symbol = args[0].upper()
        interval = args[1]

        if interval not in config['INTERVALS']:
            bot.reply_to(message, f"❌ Geçersiz aralık. Kullanılabilir aralıklar: {', '.join(config['INTERVALS'].keys())}")
            return

        bot.reply_to(message, f"📊 {symbol} için {interval} analizi yapılıyor...")
        
        klines = client.get_historical_klines(symbol=symbol, interval=config['INTERVALS'][interval], limit=100)
        
        df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'])
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        
        # Teknik göstergeler
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA50'] = df['close'].rolling(window=50).mean()
        
        def calculate_rsi(data, window=14):
            delta = data.diff()
            gain = delta.where(delta > 0, 0).rolling(window=window).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=window).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))
        
        df['RSI'] = calculate_rsi(df['close'])
        df['EMA12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['EMA26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = df['EMA12'] - df['EMA26']
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['Histogram'] = df['MACD'] - df['Signal']
        
        # Grafik oluştur
        plt.figure(figsize=(12, 10))
        
        plt.subplot(3, 1, 1)
        plt.plot(df.index, df['close'], label='Fiyat', color='black')
        plt.plot(df.index, df['MA20'], label='MA20', color='blue')
        plt.plot(df.index, df['MA50'], label='MA50', color='red')
        plt.title(f'{symbol} {interval} Fiyat ve Hareketli Ortalamalar')
        plt.legend()
        plt.grid(True)
        
        plt.subplot(3, 1, 2)
        plt.plot(df.index, df['RSI'], color='purple')
        plt.axhline(y=70, color='red', linestyle='-')
        plt.axhline(y=30, color='green', linestyle='-')
        plt.title('RSI (14)')
        plt.ylim(0, 100)
        plt.grid(True)
        
        plt.subplot(3, 1, 3)
        plt.plot(df.index, df['MACD'], label='MACD', color='blue')
        plt.plot(df.index, df['Signal'], label='Sinyal', color='red')
        plt.bar(df.index, df['Histogram'], color=df['Histogram'].apply(lambda x: 'green' if x > 0 else 'red'))
        plt.title('MACD')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        
        # Analiz sonucu
        last_price = df['close'].iloc[-1]
        last_ma20 = df['MA20'].iloc[-1]
        last_ma50 = df['MA50'].iloc[-1]
        last_rsi = df['RSI'].iloc[-1]
        macd_trend = "Yükseliş sinyali" if df['MACD'].iloc[-1] > df['Signal'].iloc[-1] else "Düşüş sinyali"
        
        if last_price > last_ma20 and last_ma20 > last_ma50:
            trend = "Güçlü Yükseliş Trendi 📈"
        elif last_price > last_ma20:
            trend = "Yükseliş Trendi 📈"
        elif last_price < last_ma20 and last_ma20 < last_ma50:
            trend = "Güçlü Düşüş Trendi 📉"
        elif last_price < last_ma20:
            trend = "Düşüş Trendi 📉"
        else:
            trend = "Yatay Trend ↔️"
        
        rsi_status = "Aşırı Alım" if last_rsi > 70 else "Aşırı Satım" if last_rsi < 30 else "Normal aralıkta"
        
        analysis_text = f"""
📊 *{symbol} {interval} Teknik Analiz*

💰 *Mevcut Fiyat:* {last_price:.2f}
📈 *Trend Durumu:* {trend}
🔍 *MA20/MA50:* {last_ma20:.2f} / {last_ma50:.2f}
📏 *RSI (14):* {last_rsi:.2f} - {rsi_status}
📊 *MACD:* {macd_trend}

*Özet:*
{trend}. RSI {rsi_status.lower()}. MACD {macd_trend.lower()}.
"""
        
        bot.send_photo(message.chat.id, buf, caption=analysis_text, parse_mode='Markdown')
        plt.close()
        
    except Exception as e:
        logger.error(f"Analiz hatası: {str(e)}")
        bot.reply_to(message, f"❌ Analiz yapılırken hata: {str(e)}")

# Price Alert fonksiyonu
@bot.message_handler(commands=['fiyatalarmi'])
def price_alert_command(message):
    try:
        args = message.text.split()[1:]
        if len(args) < 3:
            bot.reply_to(message, "❌ Hatalı kullanım. Doğru format: /fiyatalarmi BTCUSDT 60000 üstünde")
            return

        symbol = args[0].upper()
        try:
            price = float(args[1])
        except ValueError:
            bot.reply_to(message, "❌ Fiyat sayısal değer olmalıdır.")
            return
            
        direction = args[2].lower()
        if direction not in ['üstünde', 'altında']:
            bot.reply_to(message, "❌ Yön 'üstünde' ya da 'altında' olmalıdır.")
            return
        
        user_id = message.from_user.id
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO price_alerts (user_id, symbol, price, above_below)
        VALUES (?, ?, ?, ?)
        ''', (user_id, symbol, price, 'above' if direction == 'üstünde' else 'below'))
        
        conn.commit()
        conn.close()
        
        bot.reply_to(message, f"✅ Fiyat alarmı oluşturuldu! {symbol} fiyatı {price} {direction} olduğunda bildirim alacaksınız.")
        
    except Exception as e:
        logger.error(f"Fiyat alarmı oluşturma hatası: {str(e)}")
        bot.reply_to(message, f"❌ Fiyat alarmı oluşturulurken hata: {str(e)}")

# SPOT İŞLEM KOMUTLARI
@bot.message_handler(commands=['alim'])
def buy_order(message):
    try:
        args = message.text.split()[1:]
        if len(args) < 2:
            bot.reply_to(message, "❌ Hatalı kullanım. Doğru format: /alim BTCUSDT 0.01")
            return

        symbol = args[0].upper()
        quantity = float(args[1])
        user_id = message.from_user.id
        user_data = get_user_data(user_id)

        if not user_data or not user_data[3]:
            bot.reply_to(message, "❌ Spot işlemleriniz kapalı veya API bilgileriniz yok!")
            return

        user_client = Client(user_data[1], user_data[2])

        try:
            order = user_client.create_order(
                symbol=symbol,
                side=Client.SIDE_BUY,
                type=Client.ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            avg_price = float(order['fills'][0]['price'])
            total_spent = float(order['cummulativeQuoteQty'])
            
            bot.reply_to(message, f"""
✅ Başarılı Alım Emri!
━━━━━━━━━━━━━━
• Sembol: {symbol}
• Miktar: {quantity}
• Ortalama Fiyat: {avg_price:.8f}
• Toplam Harcama: {total_spent:.2f} USDT
━━━━━━━━━━━━━━
            """)
            
        except BinanceAPIException as e:
            bot.reply_to(message, f"❌ Binance hatası: {e.message}")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Sistem hatası: {str(e)}")

@bot.message_handler(commands=['satim'])
def sell_order(message):
    try:
        args = message.text.split()[1:]
        if len(args) < 2:
            bot.reply_to(message, "❌ Hatalı kullanım. Doğru format: /satim BTCUSDT 0.01")
            return

        symbol = args[0].upper()
        quantity = float(args[1])
        user_id = message.from_user.id
        user_data = get_user_data(user_id)

        if not user_data or not user_data[3]:
            bot.reply_to(message, "❌ Spot işlemleriniz kapalı veya API bilgileriniz yok!")
            return

        user_client = Client(user_data[1], user_data[2])

        try:
            order = user_client.create_order(
                symbol=symbol,
                side=Client.SIDE_SELL,
                type=Client.ORDER_TYPE_MARKET,
                quantity=quantity
            )
            
            avg_price = float(order['fills'][0]['price'])
            total_earned = float(order['cummulativeQuoteQty'])
            
            bot.reply_to(message, f"""
✅ Başarılı Satım Emri!
━━━━━━━━━━━━━━
• Sembol: {symbol}
• Miktar: {quantity}
• Ortalama Fiyat: {avg_price:.8f}
• Toplam Kazanç: {total_earned:.2f} USDT
━━━━━━━━━━━━━━
            """)
            
        except BinanceAPIException as e:
            bot.reply_to(message, f"❌ Binance hatası: {e.message}")
            
    except Exception as e:
        bot.reply_to(message, f"❌ Sistem hatası: {str(e)}")

@bot.message_handler(commands=['bakiye'])
def get_balance(message):
    try:
        user_id = message.from_user.id
        user_data = get_user_data(user_id)

        if not user_data or not user_data[1]:
            bot.reply_to(message, "❌ API bilgileriniz kayıtlı değil!")
            return

        user_client = Client(user_data[1], user_data[2])
        
        balances = []
        account = user_client.get_account()
        
        for balance in account['balances']:
            free = float(balance['free'])
            locked = float(balance['locked'])
            total = free + locked
            
            if total > 0.00000001:
                balances.append(f"• {balance['asset']}: {free:.8f} (Kullanılabilir) | {locked:.8f} (Bloke)")
        
        if not balances:
            bot.reply_to(message, "💰 Bakiyeniz boş görünüyor.")
        else:
            bot.reply_to(message, "💰 Bakiyeleriniz:\n" + "\n".join(balances))
            
    except Exception as e:
        bot.reply_to(message, f"❌ Hata: {str(e)}")

# Yardım Komutu
@bot.message_handler(commands=['yardim', 'help'])
def help_command(message):
    help_text = """
🤖 *MikaBot Komut Listesi* 🤖

🔹 *API ve Hesap Yönetimi*
/apiekle API_KEY API_SECRET - Binance API bağlantısı
/spotac - Spot işlemleri aktif et
/spotkapat - Spot işlemleri kapat
/bakiye - Varlık bakiyelerini göster

🔹 *Spot İşlemler*
/alim SİMBOL MİKTAR - Piyasa emriyle alım yapar (Örnek: /alim BTCUSDT 0.001)
/satim SİMBOL MİKTAR - Piyasa emriyle satış yapar (Örnek: /satim ETHUSDT 0.1)

🔹 *Piyasa Verileri*
/piyasa SİMBOL - Anlık fiyat sorgulama (Örnek: /piyasa SOLUSDT)
/grafik SİMBOL ARALIK - Fiyat grafiği (Örnek: /grafik BTCUSDT 1h)
/analiz SİMBOL ARALIK - Teknik analiz (Örnek: /analiz ETHUSDT 4h)

🔹 *Alarmlar*
/fiyatalarmi SİMBOL FİYAT YÖN - Fiyat alarmı ekler (Örnek: /fiyatalarmi BTCUSDT 50000 üstünde)

📌 *Not:* Tüm komutlarda SİMBOL formatı: BTCUSDT, ETHUSDT gibi.
"""
    bot.reply_to(message, help_text, parse_mode='Markdown')

# Start Komutu
@bot.message_handler(commands=['start', 'baslat'])
def start_command(message):
    user = message.from_user
    welcome_text = f"""
✨ *Merhaba {user.first_name}!* ✨

🤖 **MikaBot** size özel kripto asistanınız. 
Binance hesabınıza güvenli erişim sağlar ve piyasa analizleri sunar.

🚀 *Başlamak için:*
1️⃣ API anahtarlarınızı ekleyin
2️⃣ Spot işlemleri aktif edin
3️⃣ Komutlarla ticarete başlayın!

📌 *Güvenlik Uyarısı:* 
API anahtarlarınızı asla paylaşmayın!
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📝 API Ekle", callback_data="add_api"),
        types.InlineKeyboardButton("🔓 Spot Aç", callback_data="enable_spot")
    )
    markup.row(
        types.InlineKeyboardButton("📊 Piyasa", callback_data="market"),
        types.InlineKeyboardButton("📈 Analiz", callback_data="analysis")
    )
    markup.row(
        types.InlineKeyboardButton("🆘 Yardım", callback_data="help"),
        types.InlineKeyboardButton("⚡ Hızlı İşlem", callback_data="quick_trade")
    )
    
    try:
        with open("assets/welcome.png", "rb") as img:
            bot.send_photo(
                chat_id=message.chat.id,
                photo=img,
                caption=welcome_text,
                reply_markup=markup,
                parse_mode="Markdown"
            )
    except:
        bot.send_message(
            chat_id=message.chat.id,
            text=welcome_text,
            reply_markup=markup,
            parse_mode="Markdown"
        )
    
    bot.send_message(
        chat_id=message.chat.id,
        text="Aşağıdaki butonlarla hızlıca işlem yapabilirsiniz:",
        reply_markup=create_keyboard()
    )

# Callback handler
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "add_api":
        bot.send_message(call.message.chat.id, "API eklemek için: /apiekle API_KEY API_SECRET")
    elif call.data == "enable_spot":
        bot.send_message(call.message.chat.id, "Spot işlemleri açmak için: /spotac")
    elif call.data == "market":
        bot.send_message(call.message.chat.id, "Piyasa verisi için: /piyasa BTCUSDT")
    elif call.data == "analysis":
        bot.send_message(call.message.chat.id, "Analiz için: /analiz BTCUSDT 4h")
    elif call.data == "help":
        help_command(call.message)
    elif call.data == "quick_trade":
        bot.send_message(call.message.chat.id, "Hızlı işlem için: /alim BTCUSDT 0.01 veya /satim BTCUSDT 0.01")

# Fiyat alarmlarını kontrol et
def check_price_alerts():
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM price_alerts WHERE triggered = 0')
        alerts = cursor.fetchall()
        
        for alert in alerts:
            alert_id, user_id, symbol, target_price, direction, created_at, triggered = alert
            
            try:
                ticker = client.get_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])
                
                alarm_triggered = False
                if direction == 'above' and current_price >= target_price:
                    alarm_triggered = True
                elif direction == 'below' and current_price <= target_price:
                    alarm_triggered = True
                    
                if alarm_triggered:
                    cursor.execute('UPDATE price_alerts SET triggered = 1 WHERE id = ?', (alert_id,))
                    conn.commit()
                    
                    direction_text = "üstüne çıktı" if direction == 'above' else "altına düştü"
                    message = f"🚨 *Fiyat Alarmı!* 🚨\n\n{symbol} fiyatı {target_price} {direction_text}!\n\nMevcut fiyat: {current_price}"
                    bot.send_message(user_id, message, parse_mode='Markdown')
                    
            except Exception as e:
                logger.error(f"Alarm kontrol hatası (ID: {alert_id}): {str(e)}")
                
        conn.close()
    except Exception as e:
        logger.error(f"Fiyat alarmı kontrol işlemi hatası: {str(e)}")

def schedule_price_alert_checks():
    schedule.every(1).minutes.do(check_price_alerts)
    
    while True:
        schedule.run_pending()
        time.sleep(10)

# Ana çalıştırma fonksiyonu
def run_bot():
    alert_thread = threading.Thread(target=schedule_price_alert_checks)
    alert_thread.daemon = True
    alert_thread.start()
    
    while True:
        try:
            logger.info("Bot başlatılıyor...")
            bot.polling(none_stop=True)
        except Exception as e:
            logger.error(f"Bot hatası: {str(e)}")
            time.sleep(5)

if __name__ == '__main__':
    run_bot()