# Binance Funding Rate Bot

This project is a bot that monitors funding rates in **Binance Futures** and sends **Telegram notifications** when significant changes occur.

## 🚀 Introduction

Binance Funding Rate Bot detects funding rate changes exceeding the set threshold (**default: 0.05%**) and sends **real-time notifications** to investors.

## 📌 Usage

Supported Telegram commands:

- **/start** → Provides information about the bot.
- **/status** → Displays the current funding status and the number of tracked coins.
- **/threshold <value>** → Changes the notification threshold. Example: `/threshold 0.05`
- **/check** → Manually checks funding rates.
- **/restart** → Resets the bot's tracking.

## 🛠 Installation

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/xberkayio/binance-funding-bot
```
```bash
cd binance-funding-bot
```

### 2️⃣ Configure Your Settings

Create a `config.json` file and edit it as follows:

```json
{
  "TELEGRAM_BOT_TOKEN": "YOUR_TELEGRAM_BOT_TOKEN",
  "CHANNEL_ID": "YOUR_TELEGRAM_CHANNEL_ID",
  "BINANCE_FUNDING_RATE_URL": "https://fapi.binance.com/fapi/v1/fundingRate"
}
```

### 3️⃣ Run the Bot

```bash
python bot.py
```



# With ![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)

  ## 💰 You can help me by Donating
  [![BuyMeACoffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?style=for-the-badge&logo=buy-me-a-coffee&logoColor=black)](https://www.buymeacoffee.com/xberkay-o) 

####
<p align="center"> <img src="https://komarev.com/ghpvc/?username=xberkay-o&label=Profile%20views&color=0e75b6&style=flat" alt="xberkay-o" /> </p>
