import os

import redis
import requests
from dotenv import load_dotenv
from environs import Env
from more_itertools import chunked
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler
from telegram.ext import Filters, Updater

import load_menu

env = Env()
_database = None
current_page = 0


def fetch_coordinates(apikey, place):
    base_url = "https://geocode-maps.yandex.ru/1.x"
    params = {"geocode": place, "apikey": apikey, "format": "json"}
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    found_places = response.json()['response']['GeoObjectCollection']['featureMember']
    most_relevant = found_places[0]
    lon, lat = most_relevant['GeoObject']['Point']['pos'].split(" ")
    return lon, lat


def start(bot, update):
    chat_id = None
    message_id = None

    global current_page
    products = load_menu.get_products(load_menu.products_url, shop_token)['data']
    products_pages = chunked(products, 8)
    pages = list(products_pages)

    if update.callback_query and '<<' in update.callback_query.data and current_page != 0:
        current_page -= 1

        products_menu = [
                [InlineKeyboardButton(f"{page['name']}", callback_data=f"*{page['id']}")] for page in
                pages[current_page]
                ]

    elif update.callback_query and '>>' in update.callback_query.data and current_page != len(pages) - 1:
        current_page += 1
        products_menu = [
                [InlineKeyboardButton(f"{page['name']}", callback_data=f"*{page['id']}")] for page in
                pages[current_page]
                ]

    elif update.message:
        current_page = 0
        products_menu = [
                [InlineKeyboardButton(f"{page['name']}", callback_data=f"*{page['id']}")] for page in
                pages[current_page]
                ]
    else:
        products_menu = [
                [InlineKeyboardButton(f"{page['name']}", callback_data=f"*{page['id']}")] for page in
                pages[current_page]
                ]

    products_menu.append(
            [InlineKeyboardButton('<<', callback_data='<<'),
             InlineKeyboardButton(f'{current_page + 1}', callback_data=' '),
             InlineKeyboardButton('>>', callback_data='>>'), ]
            )
    reply_markup = InlineKeyboardMarkup(products_menu)

    if update.callback_query:
        chat_id = update.callback_query.message.chat_id
        message_id = update.callback_query.message.message_id

    elif update.message:
        chat_id = update.message.chat_id
        message_id = update.message.message_id

    bot.sendMessage(chat_id=chat_id, text='Please choose:', reply_markup=reply_markup)
    bot.delete_message(chat_id=chat_id, message_id=message_id)

    return "START"


def handle_menu(bot, update):
    product_id = None
    if '*' in update.callback_query.data:
        product_id = update.callback_query.data.replace('*', '')
    product = load_menu.get_product(product_id, shop_token)
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
    payload_cart = {
            "data": {
                    "id": product_id,
                    "type": "cart_item",
                    "quantity": 1
                    }
            }
    load_menu.add_product_to_cart(chat_id, shop_token, payload_cart)

    bot.answer_callback_query(callback_query_id=update.callback_query.id, text=f"Pizza was added to cart.")

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


# def send_email(bot, update):
#     if update.callback_query.data == 'to_payment':
#         bot.sendMessage(chat_id=update.callback_query.message.chat_id, text='please send your email address!')
#
#     bot.delete_message(chat_id=update.callback_query.message.chat_id,
#                        message_id=update.callback_query.message.message_id)
#
#     return 'WAITING_EMAIL'


# def waiting_email(bot, update):
#     customer_id = None
#     db = get_database_connection()
#     users_email = update.message.text
#     user_name = update.message.chat.username
#     email = str(users_email)
#     customer_data = {
#             'data': {
#                     'type': 'customer',
#                     'name': user_name,
#                     'email': email,
#                     }
#             }
#
#     try:
#         customer_id = str(db.get(email).decode('utf-8'))
#     except AttributeError:
#         pass
#     if customer_id:
#         customer = load_menu.get_customer(customer_id)
#     else:
#         customer_id = load_menu.create_customer(customer_data, shop_token)['data']['id']
#         db.set(email, customer_id)
#
#     update.message.reply_text(f"do you send me that email address? : {users_email}")
#
#     bot.delete_message(update.message.chat_id, update.message.message_id)
#
#     return 'WAITING_EMAIL'


def handle_waiting(bot, update):
    chat_id = None
    message_id = None
    if update.message:
        chat_id = update.message.chat_id
        message_id = update.message.message_id
    elif update.callback_query:
        chat_id = update.callback_query.message.chat_id
        message_id = update.callback_query.message.message_id

    bot.sendMessage(chat_id=chat_id, text='Please submit  your address for example "г.Астана ул.Республика 7"')
    bot.deleteMessage(chat_id=chat_id, message_id=message_id)

    return 'HANDLE_GEO'


def location(bot, update):
    print('location')
    message = None
    if update.edited_message:
        chat_id = update.edited_message.chat_id
        message = update.edited_message
        message_id = update.edited_message.message_id
    else:
        chat_id = update.message.chat_id
        message = update.message
        message_id = update.message.message_id

    current_pos = (message.location.latitude, message.location.longitude)
    bot.sendMessage(chat_id=chat_id, text=f'{current_pos}')
    bot.deleteMessage(chat_id=chat_id, message_id=message_id)

    return 'HANDLE_WAITING'


def handle_geo(bot, update):
    print('in geo--------------')
    api_key = env.str('GEO_API_KEY')
    user_reply = None
    chat_id = None
    message_id = None
    lon = None
    lat = None

    if update.message:
        chat_id = update.message.chat_id
        message_id = update.message.message_id
        user_reply = update.message.text
    elif update.callback_query:
        chat_id = update.callback_query.message.chat_id
        message_id = update.callback_query.message.message_id
        user_reply = update.callback_query.data

    try:
        lon, lat = fetch_coordinates(apikey=api_key, place=user_reply)
    except requests.exceptions.ConnectionError as e:
        print(e)
    except ConnectionError as e:
        print(e)
    except Exception as e:
        print(f'something going wrong wrong with GEO API --- {e}')

    bot.sendMessage(chat_id=chat_id, text=f'{lat} - {lon}')
    bot.delete_message(chat_id=chat_id, message_id=message_id)
    return 'HANDLE_GEO'


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
        user_state = 'HANDLE_WAITING'
    elif '*' in user_reply:
        user_state = 'HANDLE_MENU'
    else:
        user_state = db.get(chat_id).decode("utf-8")
        print(user_state)

    states_functions = {
            'START': start,
            'HANDLE_MENU': handle_menu,
            'HANDLE_DESCRIPTION': handle_description,
            'HANDLE_CART': handle_cart,
            'HANDLE_WAITING': handle_waiting,
            'HANDLE_GEO': handle_geo,
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
    dispatcher.add_handler(MessageHandler(Filters.command, handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_geo))
    dispatcher.add_handler(MessageHandler(Filters.location, location))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    updater.start_polling()