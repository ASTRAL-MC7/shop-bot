import os
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# --- CREDENTIALS & SETUP ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN_HERE').strip()
SHOP_API_KEY = os.environ.get('SHOP_API_KEY', 'hd_1729ff0cbba09a19877994bf65044cbba6bd').strip()
BASE_URL = 'https://api.geminipro7.store'

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
headers = {
    "X-API-Key": SHOP_API_KEY,
    "Content-Type": "application/json"
}

# --- HEALTH CHECK WEB SERVER (FOR RENDER) ---
app = Flask(__name__)

@app.route('/')
@app.route('/healthz')
def health():
    return "Service is running!", 200

# --- BOT COMMAND HANDLERS ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
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
            if isinstance(data, dict):
                balance = data.get('balance', data.get('funds', 'Unknown'))
            else:
                balance = data
            bot.reply_to(message, f"💰 Your current balance is: {balance}")
        else:
            bot.reply_to(message, f"⚠️ Failed to fetch balance: {response.text}")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['products'])
def list_products(message):
    try:
        response = requests.get(f"{BASE_URL}/products", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract product list from root list or common wrapper keys
            product_list = []
            if isinstance(data, list):
                product_list = data
            elif isinstance(data, dict):
                product_list = (
                    data.get('products')
                    or data.get('data')
                    or data.get('items')
                    or data.get('services', [])
                )
            
            if not isinstance(product_list, list):
                bot.reply_to(message, f"⚠️ Unexpected response structure: {data}")
                return

            if not product_list:
                bot.reply_to(message, "No products available right now.")
                return

            for product in product_list:
                if not isinstance(product, dict):
                    continue

                service_id = str(product.get('service_id') or product.get('id', ''))
                name = product.get('name', 'Unnamed Product')
                description = product.get('description', 'No description provided.')
                price = product.get('price', 'N/A')

                markup = InlineKeyboardMarkup()
                buy_button = InlineKeyboardButton(
                    text=f"Buy {name}", 
                    callback_data=f"buy_{service_id}"
                )
                markup.add(buy_button)
                
                text = (
                    f"📦 *{name}*\n\n"
                    f"📝 {description}\n"
                    f"💵 Price: {price}\n"
                    f"ID: `{service_id}`"
                )
                bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=markup)
        else:
            bot.reply_to(message, f"⚠️ Failed to load products: {response.text}")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

@bot.message_handler(commands=['orders'])
def order_history(message):
    try:
        response = requests.get(f"{BASE_URL}/orders", headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            orders_list = []
            if isinstance(data, list):
                orders_list = data
            elif isinstance(data, dict):
                orders_list = (
                    data.get('orders')
                    or data.get('data')
                    or data.get('items', [])
                )
            
            if not isinstance(orders_list, list) or not orders_list:
                bot.reply_to(message, "You have no previous orders.")
                return
            
            history_text = "🛒 *Your Orders:*\n\n"
            for order in orders_list[:10]:
                if isinstance(order, dict):
                    order_id = order.get('order_id') or order.get('id', 'N/A')
                    status = order.get('status', 'N/A')
                    history_text += f"- Order #{order_id} | Status: {status}\n"
            
            bot.send_message(message.chat.id, history_text, parse_mode='Markdown')
        else:
            bot.reply_to(message, f"⚠️ Could not load order history: {response.text}")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

# --- CALLBACK QUERY HANDLER (INLINE BUTTONS) ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_'))
def handle_purchase(call):
    service_id = call.data.split('_', 1)[1]
    payload = {
        "service_id": service_id,
        "quantity": 1
    }
    
    try:
        response = requests.post(f"{BASE_URL}/order", headers=headers, json=payload, timeout=10)
        if response.status_code in [200, 201]:
            order_data = response.json()
            order_id = 'Unknown'
            if isinstance(order_data, dict):
                order_id = order_data.get('order_id') or order_data.get('id', 'Unknown')
            bot.answer_callback_query(call.id, "Order placed successfully!")
            bot.send_message(call.message.chat.id, f"✅ Order successful! Your Order ID is: `{order_id}`", parse_mode='Markdown')
        else:
            bot.answer_callback_query(call.id, "Failed to place order.")
            bot.send_message(call.message.chat.id, f"❌ Order failed: {response.text}")
    except Exception as e:
        bot.answer_callback_query(call.id, "Error processing order.")
        bot.send_message(call.message.chat.id, f"Error: {e}")

# --- STARTUP THREADS ---

def start_polling():
    print("Telegram polling thread active and listening...")
    bot.infinity_polling(skip_pending=True)

# Run polling loop in background daemon thread
poll_thread = Thread(target=start_polling)
poll_thread.daemon = True
poll_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
