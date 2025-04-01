# Binance Funding Rate Bot

Bu proje, Binance Vadeli İşlemlerindeki fonlama oranlarını takip eden ve belirli değişiklikler olduğunda **Telegram üzerinden bildirim gönderen** bir bottur.

## 🚀 Tanıtım

Binance Funding Rate Bot, belirlenen eşik değeri (**varsayılan: %0.05**) aşan **fonlama oranı değişimlerini** tespit eder ve yatırımcılara **anlık bildirimler** gönderir.

## 📌 Kullanım

Botun desteklediği Telegram komutları:

- **/start** → Bot hakkında bilgi verir.
- **/status** → Anlık fonlama durumu ve takip edilen coin sayısını gösterir.
- **/threshold <değer>** → Bildirim eşik değerini değiştirir. Örn: `/threshold 0.05`
- **/check** → Manuel olarak fonlama oranlarını kontrol eder.
- **/restart** → Botun takibini sıfırlar.

## 🛠 Kurulum

### 1️⃣ Depoyu Klonlayın

```bash
git clone https://github.com/kullaniciadi/binance-funding-bot.git
```
```bash
cd binance-funding-bot
```

### 2️⃣ Gerekli Bağımlılıkları Yükleyin

```bash
pip install -r requirements.txt
```

### 3️⃣ Config Dosyanızı Düzenleyin

`config.json` dosyasını oluşturup aşağıdaki gibi düzenleyin:

```json
{
  "TELEGRAM_BOT_TOKEN": "YOUR_TELEGRAM_BOT_TOKEN",
  "CHANNEL_ID": "YOUR_TELEGRAM_CHANNEL_ID",
  "BINANCE_FUNDING_RATE_URL": "https://fapi.binance.com/fapi/v1/fundingRate"
}
```

### 4️⃣ Botu Çalıştırın

```bash
python bot.py
```

## 🖼 Görseller

![Telegram Bot](https://via.placeholder.com/800x400?text=Telegram+Bot+Preview)

## 💰 Bağış Yaparak Destek Olabilirsiniz
[![BuyMeACoffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/kullaniciadi)

####
<p align="center"> <img src="https://komarev.com/ghpvc/?username=kullaniciadi&label=Profile%20views&color=0e75b6&style=flat" alt="kullaniciadi" /> </p>

