import os

import redis
import requests
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
            [InlineKeyboardButton("go to cart", callback_data='/сart'),
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
    message_id = update.callback_query.message.message_id

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

    menu.append([InlineKeyboardButton(f"payment", callback_data="/location")])
    menu.append([InlineKeyboardButton(f"back to menu", callback_data="/start")])
    reply_markup = InlineKeyboardMarkup(menu)

    bot.sendMessage(chat_id=chat_id, text=f'{items_message}\nTotal: {total_cost}',
                    reply_markup=reply_markup)

    bot.delete_message(chat_id=chat_id, message_id=message_id)

    return 'HANDLE_CART'


def handle_waiting(bot, update):
    chat_id = None
    message_id = None
    if update.message:
        chat_id = update.message.chat_id
        message_id = update.message.message_id
    elif update.callback_query:
        chat_id = update.callback_query.message.chat_id
        message_id = update.callback_query.message.message_id

    bot.sendMessage(chat_id=chat_id,
                    text='Please submit  your location or address \n'
                         'for example:  г.Астана ул.Республика 7')
    bot.delete_message(chat_id=chat_id, message_id=message_id)

    return 'HANDLE_RANGE'


def handle_rang(bot, update):
    api_key = env.str('GEO_API_KEY')
    message = None
    chat_id = None
    message_id = None

    if update.message:
        chat_id = update.message.chat_id
        message = update.message
        message_id = update.message.message_id

    if message.location:
        current_pos = f'{message.location.longitude}, {message.location.latitude}'
        print(current_pos)
        print('current_pos_locations-------------')
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        return 'HANDLE_RANGE'

    else:
        chat_id = update.message.chat_id
        message_id = update.message.message_id
        user_reply = update.message.text
        try:
            lon, lat = fetch_coordinates(apikey=api_key, place=user_reply)
            current_pos = f'{lon},{lat}'
            print(current_pos)
            print('current_pos------------')
            # db.set(chat_id, str(coords))

        except (requests.exceptions.ConnectionError, ConnectionError, IndexError):

            bot.sendMessage(chat_id=chat_id,
                            text=f'The address you gave is incorrect, please try again, or try the incorrect operation of the system later.')
            bot.delete_message(chat_id=chat_id, message_id=message_id)
            return 'HANDLE_WAITING'
        return 'HANDLE_RANGE'


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
    elif user_reply == '/сart':
        user_state = 'HANDLE_CART'
    elif user_reply == '/location':
        user_state = 'HANDLE_WAITING'
    elif '*' in user_reply:
        user_state = 'HANDLE_MENU'
    else:
        user_state = db.get(chat_id).decode("utf-8")
        print(user_state)
        print('user_state-----------')

    states_functions = {
            'START': start,
            'HANDLE_MENU': handle_menu,
            'HANDLE_DESCRIPTION': handle_description,
            'HANDLE_CART': handle_cart,
            'HANDLE_WAITING': handle_waiting,
            'HANDLE_RANGE': handle_rang,
            }
    state_handler = states_functions[user_state]
    next_state = state_handler(bot, update)
    db.set(chat_id, next_state)
    print(next_state)
    print('next_state-----------')


def get_database_connection():
    global _database
    if _database is None:
        database_password = os.getenv("DATABASE_PASSWORD")
        database_host = os.getenv("DATABASE_HOST")
        database_port = os.getenv("DATABASE_PORT")
        _database = redis.Redis(host=database_host, port=database_port, password=database_password)
    return _database


if __name__ == '__main__':
    client_id = env.str('CLIENT_ID')
    client_secret_key = env.str('CLIENT_SECRET')
    token = env.str("TG_TOKEN")
    updater = Updater(token)

    data = {
            'client_id': client_id,
            'client_secret': client_secret_key,
            'grant_type': 'client_credentials'
            }
    shop_token = load_menu.get_access_token(load_menu.token_url)['access_token']
    print(f' shop token ---- {shop_token}')

    dispatcher = updater.dispatcher
    dispatcher.add_handler(CallbackQueryHandler(handle_users_reply))
    dispatcher.add_handler(CommandHandler('start', handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.text, handle_users_reply))
    dispatcher.add_handler(MessageHandler(Filters.location, handle_rang))
    updater.start_polling()
