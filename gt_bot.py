import os
import redis
from dotenv import load_dotenv
from telegram.ext import Filters, Updater
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from more_itertools import chunked

import load_menu
import pprint

_database = None
current_page = 0


def start(bot, update):
    global current_page
    reply_markup = None
    products = load_menu.get_products(load_menu.products_url, shop_token)['data']
    products_pages = chunked(products, 8)
    pages = list(products_pages)

    if update.callback_query and '<<' in update.callback_query.data:
        current_page -= 1
        print(current_page)

        products_menu = [
            [InlineKeyboardButton(f"{page['name']}", callback_data=f"{page['id']}")] for page in
            pages[current_page]
        ]
        products_menu.append(
            [InlineKeyboardButton('<<', callback_data='<<'),
             InlineKeyboardButton(f'{current_page}', callback_data=' '),
             InlineKeyboardButton('>>', callback_data='>>'), ]
        )
        reply_markup = InlineKeyboardMarkup(products_menu)

    if update.callback_query and '>>' in update.callback_query.data:
        current_page += 1
        print(current_page)

        products_menu = [
            [InlineKeyboardButton(f"{page['name']}", callback_data=f"{page['id']}")] for page in
            pages[current_page]
        ]
        products_menu.append(
            [InlineKeyboardButton('<<', callback_data='<<'),
             InlineKeyboardButton(f'{current_page}', callback_data=' '),
             InlineKeyboardButton('>>', callback_data='>>'), ]
        )
        reply_markup = InlineKeyboardMarkup(products_menu)

    if update.message:
        current_page = 0
        products_menu = [
            [InlineKeyboardButton(f"{page['name']}", callback_data=f"{page['id']}")] for page in
            pages[current_page]
        ]
        products_menu.append(
            [InlineKeyboardButton('<<', callback_data='<<'),
             InlineKeyboardButton(f'{current_page}', callback_data=' '),
             InlineKeyboardButton('>>', callback_data='>>'), ]
        )
        reply_markup = InlineKeyboardMarkup(products_menu)

    if update.callback_query:
        bot.sendMessage(chat_id=update.callback_query.message.chat_id, text='Please choose:', reply_markup=reply_markup)
        bot.delete_message(chat_id=update.callback_query.message.chat_id,
                           message_id=update.callback_query.message.message_id)

    elif update.message:
        update.message.reply_text('Please choose:', reply_markup=reply_markup)
        bot.delete_message(chat_id=update.message.chat_id,
                           message_id=update.message.message_id)

    return "START"


def handle_menu(bot, update):
    product_id = update.callback_query.data
    product = load_menu.get_product(product_id, shop_token)
    print(product)
    main_image_id = product['data']['relationships']['main_image']['data']['id']
    image_url = load_menu.get_file_url(main_image_id, shop_token)['data']['link']['href']
    menu = [
        [InlineKeyboardButton(f"Add to cart {product['data']['name']}", callback_data=f"{product['data']['id']}")],
        [InlineKeyboardButton("go to cart", callback_data='to_сart'),
         InlineKeyboardButton("back to menu", callback_data='/start')]
    ]
    reply_markup = InlineKeyboardMarkup(menu)

    bot.send_photo(chat_id=update.callback_query.message.chat_id, photo=image_url,
                   caption=f"{product['data']['name']}\n\nprice {product['data']['price'][0]['amount']} {product['data']['price'][0]['currency']}\n\n"
                           f"Description:\n"
                           f"{product['data']['description']}", reply_markup=reply_markup)

    bot.delete_message(chat_id=update.callback_query.message.chat_id,
                       message_id=update.callback_query.message.message_id)

    return "HANDLE_DESCRIPTION"


def handle_description(bot, update):
    product_id = update.callback_query.data
    chat_id = str(update.callback_query.message.chat_id)
    load_menu.get_cart(chat_id, shop_token)
    payload_cart = {"data": {"id": product_id,
                             "type": "cart_item",
                             "quantity": 1}}

    load_menu.add_product_to_cart(chat_id, shop_token, payload_cart)
    bot.answer_callback_query(callback_query_id=update.callback_query.id, text=f"Pizza was added to cart.",
                              show_alert=False)

    return 'HANDLE_DESCRIPTION'


def handle_cart(bot, update):
    items_message = "Cart is empty."
    chat_id = str(update.callback_query.message.chat_id)

    if '|||' in update.callback_query.data:
        product_id = update.callback_query.data.split('|||').pop(0)
        product_id = product_id.strip()

        load_menu.delete_cart_product(chat_id, product_id, shop_token)
        bot.answer_callback_query(callback_query_id=update.callback_query.id, text=f"Pizza was deleted.",
                                  show_alert=False)

    cart_products = load_menu.get_cart_items(chat_id, shop_token)
    message = []
    for product in cart_products['data']:
        message.append(product['name'])
        message.append(product['description'])
        message.append(
            f"Quantity: {product['quantity']}\nPrice: {product['value']['amount']} {product['value']['currency']}")
        message.append(' ')
        items_message = '\n'.join(message)
    total = load_menu.get_cart_total(shop_token, chat_id=chat_id)
    total_cost = total['data']['meta']['display_price']['without_tax']['amount']

    menu = []
    for product in cart_products['data']:
        menu.append([InlineKeyboardButton(f"remove from cart {product['name']}",
                                          callback_data=f"{product['id']}|||")])

    menu.append([InlineKeyboardButton(f"payment", callback_data="to_payment")])
    menu.append([InlineKeyboardButton(f"back to menu", callback_data="/start")])
    reply_markup = InlineKeyboardMarkup(menu)

    bot.sendMessage(chat_id=update.callback_query.message.chat_id, text=f'{items_message}\nTotal: {total_cost}',
                    reply_markup=reply_markup)

    bot.delete_message(chat_id=update.callback_query.message.chat_id,
                       message_id=update.callback_query.message.message_id)

    return 'HANDLE_CART'


def send_email(bot, update):
    if update.callback_query.data == 'to_payment':
        bot.sendMessage(chat_id=update.callback_query.message.chat_id, text='please send your email address!')

    bot.delete_message(chat_id=update.callback_query.message.chat_id,
                       message_id=update.callback_query.message.message_id)

    return 'WAITING_EMAIL'


def waiting_email(bot, update):
    customer_id = None
    db = get_database_connection()
    users_email = update.message.text
    user_name = update.message.chat.username
    email = str(users_email)
    customer_data = {'data': {
        'type': 'customer',
        'name': user_name,
        'email': email,
    }}

    try:
        customer_id = str(db.get(email).decode('utf-8'))
    except AttributeError:
        pass
    if customer_id:
        customer = load_menu.get_customer(customer_id)
        print(customer)
    else:
        customer_id = load_menu.create_customer(customer_data, shop_token)['data']['id']
        db.set(email, customer_id)

    update.message.reply_text(f"do you send me that email address? : {users_email}")

    bot.delete_message(update.message.chat_id, update.message.message_id)

    return 'WAITING_EMAIL'


def handle_users_reply(bot, update):
    db = get_database_connection()
    if update.message:
        user_reply = update.message.text
        chat_id = update.message.chat_id
    elif update.callback_query:
        user_reply = update.callback_query.data
        chat_id = update.callback_query.message.chat_id
    else:
        return
    if user_reply == '/start':
        user_state = 'START'
    elif user_reply == 'to_сart':
        user_state = 'HANDLE_CART'
    elif user_reply == 'to_payment':
        user_state = 'SEND_EMAIL'
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
        'START': start,
        'HANDLE_MENU': handle_menu,
        'HANDLE_DESCRIPTION': handle_description,
        'HANDLE_CART': handle_cart,
        'WAITING_EMAIL': waiting_email,
        'SEND_EMAIL': send_email,
    }
    state_handler = states_functions[user_state]
    next_state = state_handler(bot, update)
    db.set(chat_id, next_state)


def get_database_connection():
    global _database
    if _database is None:
        database_password = os.getenv("DATABASE_PASSWORD")
        database_host = os.getenv("DATABASE_HOST")
        database_port = os.getenv("DATABASE_PORT")
        _database = redis.Redis(host=database_host, port=database_port, password=database_password)
    return _database


if __name__ == '__main__':
    load_dotenv()
    client_id = os.getenv('CLIENT_ID')
    client_secret_key = os.getenv('CLIENT_SECRET')
    token = os.getenv("TG_TOKEN")
    updater = Updater(token)

    data = {
        'client_id': client_id,
        'client_secret': client_secret_key,
        'grant_type': 'client_credentials'
    }
    shop_token = load_menu.get_shop_token(load_menu.token_url)['access_token']
    print(f' shop token ---- {shop_token}')

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    updater.start_polling()
