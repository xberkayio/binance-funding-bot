import httpx
import json
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime
import traceback

import nest_asyncio
nest_asyncio.apply()

logging.basicConfig(
  format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
  level = logging.INFO,
  handlers=[
    logging.FileHandler("bot.log"),
    logging.StreamHandler()
  ]
)
logger = logging.getLogger(__name__)

with open('config.json') as config_file:
  config = json.load(config_file)

BINANCE_FUNDING_RATE_URL = config['BINANCE_FUNDING_RATE_URL']

previous_rates = {}
notification_threshold = 0.0005
CHANNEL_ID = config['CHANNEL_ID']
MAX_RETRY_ATTEMPTS = 5
RETRY_DELAY = 5

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  welcome_message = (
    "🚀 *Welcome to Binance Funding Rate Bot!*\n\n"
    "This bot, Tracks funding rate changes for all coins in the Binance futures market.\n"
    "It automatically sends notifications when there is a %0.05 change in any coin.\n\n"
    "*Commands You Can Use:*\n"
    "/start - Starts the bot and displays this message.\n"
    "/status - Shows the current status of the bot.\n"
    "/threshold <value> - Sets the notification threshold value. For example: `/threshold 0.05`\n"
    "/check - Checks the current funding rates of all coins.\n"
  )
  await update.message.reply_text(welcome_message, parse_mode="Markdown")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  global previous_rates, notification_threshold

  try:
    async with httpx.AsyncClient() as client:
      r = await client.get(BINANCE_FUNDING_RATE_URL, httpx.Timeout(10.0))
      r.raise_for_status()
      current_rates = r.json()

      time_remaining = "Unknown"
      if current_rates and len(current_rates) > 0:
        next_funding_time = int(current_rates[0]["nextFundingTime"])
        time_remaining = get_time_remaining(next_funding_time)

      connection_status = "✅ Connection status: Active"

      status_message = (
        "🤔 *Bot Status*\n\n"
        f"🔍 *Number of Coins Tracked:* {len(current_rates)}\n"
        f"⚙️ *Notification Threshold:* %{notification_threshold * 100:.4f}\n"
        f"⏳ *Remaining Time Until Next Funding:* {time_remaining}\n"
        f"{connection_status}\n\n"
        f"Final Check: {datetime.now().strftime('%H:%M:%S')}"
      )
      await update.message.reply_text(status_message, parse_mode="Markdown")

  except Exception as e:
    connection_status = "❌ Connection Status: Error"
    error_message = (
      "🤔 *Bot Status*\n\n"
      f"{connection_status}\n"
      f"Error: {str(e)}\n\n"
      f"Final Check: {datetime.now().strftime('%H:%M:%S')}"
    )
    await update.message.reply_text(error_message, parse_mode="Markdown")
    logger.error(f"Status command error: {str(e)}")

async def threshold_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  global notification_threshold

  if len(context.args) == 0:
    await update.message.reply_text(
      f"Current notification threshold: %{notification_threshold * 100:.4f}\n"
      f"To change: /threshold <value>\n"
      f"Example: /threshold 0.05 (for 5 percent)"
    )
    return
  
  try:
    new_threshold = float(context.args[0]) / 100

    if new_threshold <= 0:
      await update.message.reply_text("❌ The threshold value must be greater than zero.")
      return
    
    notification_threshold = new_threshold
    await update.message.reply_text(f"✅ Notification threshold set to % {notification_threshold * 100:.4f}.")
  except ValueError:
    await update.message.reply_text("❌ Please enter a valid number. Example: /threshold 0.05")

async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text("🔍 The funding rates of all coins are being checked...")

  try:
    changed_coins = await check_funding_rates(context.bot, manual_check=True)

    if changed_coins:
      await update.message.reply_text(f"✅ Check completed. Change detected in {len(changed_coins)} coin.")
    else:
      await update.message.reply_text("✅ Check completed. No change exceeding the threshold value was detected.")
  except Exception as e:
    logger.error(f"Check command error: {str(e)}")
    await update.message.reply_text(f"Error occurred during check: {str(e)}")

def get_time_remaining(next_funding_time):
  now = int(datetime.now().timestamp() * 1000)
  remaining_ms = next_funding_time - now

  if remaining_ms <= 0:
    return "00:00:00"
  
  seconds = int(remaining_ms / 1000)
  hours, remainder = divmod(seconds, 3600)
  minutes, seconds = divmod(remainder, 60)

  return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

async def check_funding_rates(bot, manual_check=False):
  global previous_rates, notification_threshold
  changed_coins = []

  retry_count = 0
  while retry_count < MAX_RETRY_ATTEMPTS:
    try:
      async with httpx.AsyncClient() as client:
        r = httpx.get(BINANCE_FUNDING_RATE_URL, httpx.Timeout(10.0))
        r.raise_for_status()
        current_data = r.json()

        if CHANNEL_ID and retry_count > 0:
          await bot.send_message(
            chat_id = CHANNEL_ID,
            text = f"📡 Bot connection re-established (Tries: {retry_count})"
          )

        for item in current_data:
          symbol = item["symbol"]
          current_rate = float(item["lastFundingRate"])
          next_funding_time = int(item["nextFundingTime"])
          time_remaining = get_time_remaining(next_funding_time)

          if symbol not in previous_rates:
            previous_rates[symbol] = current_rate
            continue

          previous_rate = previous_rates[symbol]
          difference = abs(current_rate, previous_rate)

          if difference >= notification_threshold or manual_check:
            current_percentage = current_rate * 100
            previous_percentage = previous_rate * 100
            diff_percentage = difference * 100

            if current_rate > previous_rate:
              direction = "📈↑"
            elif current_data < previous_rate:
              direction = "📉↓"
            else:
              direction = "↔️"

            message = (
              f"🚨 #{symbol} {direction}\n\n"
              f"Instant Rate: %{current_percentage:.6f}\n"
              f"Previous Rate: &{previous_percentage:.6f}\n"
              f"Change: %{diff_percentage:.6f}\n"
              f"Next Funding: {time_remaining}\n"
            )

            if difference >= notification_threshold:
              if CHANNEL_ID:
                await bot.send_message(chat_id=CHANNEL_ID, text=message)
                changed_coins.append(symbol)
                logger.info(
                  f"Funding rate change detected: {symbol}: {previous_rate} -> {current_rate}"
                )
            previous_rate[symbol] = current_rate
      break   

    except Exception as e:
      retry_count += 1
      logger.error(f"Error checking funding rates (attemp {retry_count}/{MAX_RETRY_ATTEMPTS}): {str(e)}")

      if retry_count >= MAX_RETRY_ATTEMPTS:
        if CHANNEL_ID:
          await bot.send_message(
            chat_id = CHANNEL_ID,
            text = f"❌ The bot is having trouble connecting. Last error: {str(e)}\nIt will try to reconnect automatically."
          )
          break
      
      await asyncio.sleep(RETRY_DELAY)

    return changed_coins
  
async def scheduled_check(context: ContextTypes.DEFAULT_TYPE):
  try:
    await check_funding_rates(context.bot)

    current_hour = datetime.now().hour
    current_minute = datetime.now().minute

    if current_minute == 0:
      logger.info(f"Hourly health check at {current_hour}:00")
      if CHANNEL_ID:
        await context.bot.send_message(
          chat_id = CHANNEL_ID,
          text = f"📊 Bot health check: {datetime.now().strftime('%H:%M:%S')}\nEverything is working normally."
        )
  except Exception as e:
    logger.error(f"Scheduled check error: {str(e)}")
    logger.error(traceback.format_exc())

async def restart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
  await update.message.reply_text("🔄 Bot is restarting...")
  logger.info("Bot restart requested via command")

  global previous_rates
  previous_rates = {}

  try:
    async with httpx.AsyncClient() as client:
      r = await client.get(BINANCE_FUNDING_RATE_URL, httpx.Timeout(10.0))
      funding_rates = r.json()

      for item in funding_rates:
        previous_rates[item["symbol"]] = float(item["lastFundingRate"])

      await update.message.reply_text(f"✅ Bot successfully restarted. {len(previous_rates)} coins are being tracked.")
  except Exception as e:
    await update.message.reply_text(f"❌ Error during restart: {str(e)}")

async def heartbeat_check(context: ContextTypes.DEFAULT_TYPE):
  try:
    async with httpx.AsyncClient() as client:
      r = client.get(BINANCE_FUNDING_RATE_URL, httpx.Timeout(10.0))
      r.raise_for_status()
      logger.info("Heartbeat check: Success")
  except Exception as e:
    logger.error(f"Heartbeat check failed: {str(e)}")

    if CHANNEL_ID:
      await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text = f"⚠️ Bot connection problem detected. Attempting automatic restart...\nError: {str(e)}"
      )
    
    global previous_rates
    previous_rates = {}

    try:
      async with httpx.AsyncClient() as client:
        r = client.get(BINANCE_FUNDING_RATE_URL, httpx.Timeout(10.0))
        funding_rates = r.json()

        for item in funding_rates:
          previous_rates[item["symbol"]] = float(item["lastFundingRate"])

        logger.info(f"Auto-restart successful. Tracking {len(previous_rates)} coins.")

        if CHANNEL_ID:
          await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text = f"✅ Bot automatically restarted. {len(previous_rates)} coins are being followed."
          ) 
    except Exception as restart_error:
      logger.error(f"Auto-restart failed: {str(restart_error)}")
      if CHANNEL_ID:
        await context.bot.send_message(
        chat_id=CHANNEL_ID,
        text=f"❌ Otomatik yeniden başlatma başarısız: {str(restart_error)}\nManuel müdahale gerekebilir."
        )

async def main():
  bot_token = config["TELEGRAM_BOT_TOKEN"]

  application = Application.builder().token(bot_token).build()

  application.add_handler(CommandHandler("start", start_command))
  application.add_handler(CommandHandler("status", status_command))
  application.add_handler(CommandHandler("threshold", threshold_command))
  application.add_handler(CommandHandler("check", check_command))
  application.add_handler(CommandHandler("restart", restart_command))

  job_queue = application.job_queue
  
  if job_queue is not None:
    job_queue.run_repeating(scheduled_check, interval=15)
    job_queue.run_repeating(heartbeat_check, interval=300)

    logger.info("Job queue scheduled successfully")
  else:
    logger.error("Job queue is None! Scheduled tasks will not run.")

  try:
    async with httpx.AsyncClient() as client:
      r = client.get(BINANCE_FUNDING_RATE_URL, httpx.Timeout(10.0))
      funding_rates = r.json()

      for item in funding_rates:
        previous_rates[item["symbol"]] = float(item["lastFundingRate"])

      logger.info(f"Initialized {len(previous_rates)} funding rates")

      if CHANNEL_ID:
        await application.bot.send_message(
          chat_id=CHANNEL_ID,
          text = f"💰 Funding Rate Bot has been launched!\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{len(previous_rates)} coins are being tracked"
        )
  except Exception as e:
    logger.error(f"Failed to initialize funding rates: {str(e)}")

  await application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
  loop = asyncio.get_event_loop()
  try:
    logger.info("Bot starting up...")
    loop.run_until_complete(main())
  except KeyboardInterrupt:
    logger.info("Bot manually stopped via keyboard interrupt.")
    print("The Bot has been stopped.")
  except Exception as e:
    logger.critical(f"Fatal error occured: {str(e)}")
    logger.critical(traceback.format_exc())
  finally:
    loop.close()
    