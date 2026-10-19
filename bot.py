import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
from flask import Flask
from threading import Thread

# --- CREDENTIALS ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN_HERE').strip()
SHOP_API_KEY = os.environ.get('SHOP_API_KEY', 'hd_1729ff0cbba09a19877994bf65044cbba6bd').strip()
BASE_URL = 'https://api.geminipro7.store'

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
headers = {
    "X-API-Key": SHOP_API_KEY,
    "Content-Type": "application/json"
}

# --- HEALTH CHECK WEB SERVER ---
app = Flask(__name__)

@app.route('/')
@app.route('/healthz')
def health():
    return "Service is running!", 200

# --- BOT HANDLERS ---
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    print(f"Received /start from {message.chat.id}")
    welcome_text = (
        "Welcome to the Shop Bot! Here is what you can do:\n\n"
        "/products - View available items to buy\n"
        "/balance - Check your account balance\n"
        "/orders - View your order history"
    )
    bot.send_message(message.chat.id, welcome_text)

@bot.message_handler(commands=['balance'])
def check_balance(message):
    try:
        response = requests.get(f"{BASE_URL}/me", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            balance = data.get('balance', 'Unknown')
            bot.reply_to(message, f"💰 Your current balance is: {balance}")
        else:
            bot.reply_to(message, "⚠️ Failed to fetch balance. Please try again later.")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['products'])
def list_products(message):
    try:
        response = requests.get(f"{BASE_URL}/products", headers=headers, timeout=10)
        if response.status_code == 200:
            products = response.json()
            if not products:
                bot.reply_to(message, "No products available right now.")
                return

            for product in products:
                markup = InlineKeyboardMarkup()
                buy_button = InlineKeyboardButton(
                    text=f"Buy {product.get('name', 'Item')}", 
                    callback_data=f"buy_{product.get('service_id')}"
                )
                markup.add(buy_button)
                
                text = (
                    f"📦 *{product.get('name', 'Unnamed Product')}*\n\n"
                    f"📝 {product.get('description', 'No description provided.')}\n"
                    f"💵 Price: {product.get('price', 'N/A')}\n"
                    f"ID: {product.get('service_id')}"
                )
                bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.reply_to(message, "⚠️ Could not load products.")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['orders'])
def order_history(message):
    try:
        response = requests.get(f"{BASE_URL}/orders", headers=headers, timeout=10)
        if response.status_code == 200:
            orders = response.json()
            if not orders:
                bot.reply_to(message, "You have no previous orders.")
                return
            
            history_text = "🛒 *Your Orders:*\n\n"
            for order in orders[:10]:
                history_text += f"- Order #{order.get('order_id')} | Status: {order.get('status', 'N/A')}\n"
            
            bot.send_message(message.chat.id, history_text, parse_mode='Markdown')
        else:
            bot.reply_to(message, "⚠️ Could not load order history.")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_purchase(call):
    service_id = call.data.split('_')[1]
    payload = {"service_id": service_id, "quantity": 1}
    
    try:
        response = requests.post(f"{BASE_URL}/order", headers=headers, json=payload, timeout=10)
        if response.status_code in [200, 201]:
            order_data = response.json()
            order_id = order_data.get('order_id', 'Unknown')
            bot.answer_callback_query(call.id, "Order placed successfully!")
            bot.send_message(call.message.chat.id, f"✅ Order successful! Your Order ID is: {order_id}")
        else:
            bot.answer_callback_query(call.id, "Failed to place order.")
            bot.send_message(call.message.chat.id, f"❌ Order failed: {response.text}")
    except Exception as e:
        bot.answer_callback_query(call.id, "Error processing order.")
        bot.send_message(call.message.chat.id, f"Error: {e}")

# --- STARTUP ROUTINE ---
def start_polling():
    print("Telegram polling thread active and listening...")
    bot.infinity_polling(skip_pending=True)

# Run polling thread when the module is imported or executed
poll_thread = Thread(target=start_polling)
poll_thread.daemon = True
poll_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
