import os

import redis
import requests
from environs import Env
from geopy.distance import distance
from more_itertools import chunked
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, MessageHandler, Filters, Updater

import bot_load_data
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
                    text='Please submit  your location or address.')
    bot.delete_message(chat_id=chat_id, message_id=message_id)

    return 'HANDLE_RANGE'


def get_distance(args):
    return args['distance']


def calculate_range_to_pizzeria(chat_id, current_pos, get_pizzerias_coords):
    distances = []
    for pizzeria_pos in get_pizzerias_coords:
        for key in pizzeria_pos:
            pizzeria_coords = pizzeria_pos[key]
            dist_to_pizzeria = distance((current_pos), (pizzeria_coords['lng'], pizzeria_coords['lat'])).km
            distances.append({
                    'pizzeria_address': key,
                    'distance': round(dist_to_pizzeria, 3),
                    })

    min_dist_to_pizz = min(distances, key=get_distance)
    return min_dist_to_pizz


def handle_rang(bot, update):
    db = get_database_connection()
    api_key = env.str('GEO_API_KEY')
    message = None
    chat_id = None
    message_id = None
    text = None

    if update.message:
        chat_id = update.message.chat_id
        message = update.message
        message_id = update.message.message_id
        username = update.message.from_user['username']
        print(username)
        print('user------')

    if message.location:
        current_pos = f'{message.location.longitude}, {message.location.latitude}'
        bot.delete_message(chat_id=chat_id, message_id=message_id)
    else:
        chat_id = update.message.chat_id
        message_id = update.message.message_id
        user_reply = update.message.text
        try:
            lon, lat = fetch_coordinates(apikey=api_key, place=user_reply)
            current_pos = f'{lon},{lat}'

        except (requests.exceptions.ConnectionError, ConnectionError, IndexError):
            bot.sendMessage(chat_id=chat_id,
                            text=f'The address you gave is incorrect, please try again, or try the incorrect operation of the system later.')
            bot.delete_message(chat_id=chat_id, message_id=message_id)
            return 'HANDLE_WAITING'

    delivery_menu = [[InlineKeyboardButton('Do you want we deliver your pizza?.', callback_data='/delivery')],
                     [InlineKeyboardButton('Do you want pick up your pizza?.', callback_data='/pickup')]]
    replay_markup = InlineKeyboardMarkup(delivery_menu)

    min_dist_to_pizz = calculate_range_to_pizzeria(chat_id, current_pos, bot_load_data.pizzerias_coords)

    db.set(str(username), min_dist_to_pizz['pizzeria_address'])

    if min_dist_to_pizz['distance'] < 0.5:
        text = '''Pizzeria less than 0,5 km from you, delivery cost free. Pizzeria's address {}.\n \
                {} km from you'''.format(
                min_dist_to_pizz['pizzeria_address'], min_dist_to_pizz['distance'])
    if 0.5 < min_dist_to_pizz['distance'] < 5:
        text = '''Pizzeria less than 5 km from you, delivery cost 100 RUB. Pizzeria's address {}.\n \
                {} km from you'''.format(
                min_dist_to_pizz['pizzeria_address'], min_dist_to_pizz['distance'])
    if 5 < min_dist_to_pizz['distance'] < 20:
        text = '''Pizzeria less than 20 km from you, delivery cost 300 RUB. Pizzeria's address {}.\n \
                {} km from you'''.format(
                min_dist_to_pizz['pizzeria_address'], min_dist_to_pizz['distance'])
    if 20 < min_dist_to_pizz['distance'] < 51:
        text = '''Pizzeria in 20 - 50 km from you, you can pick up your pizza yourself. Pizzeria address {},\n \
               {} km from you'''.format(min_dist_to_pizz['pizzeria_address'],
                                        min_dist_to_pizz['distance'])

    if min_dist_to_pizz['distance'] > 51:
        text = '''Out of our pizzerias service range.\n \
        Pizzeria address {}, rang {} km from you.'''.format(min_dist_to_pizz['pizzeria_address'],
                                                            min_dist_to_pizz['distance'])
    bot.send_message(chat_id=chat_id, text=text, reply_markup=replay_markup)
    return 'HANDLE_RANGE'


def handle_pickup(bot, update):
    db = get_database_connection()

    if update.callback_query:
        username = update.callback_query.from_user['username']
        print(username)
        pizzeria_address = db.get(str(username)).decode('utf-8')
        bot.send_message(chat_id=update.callback_query.message.chat_id,
                         text='Thank you, you can pickup you pizza here:\n {}.'.format(pizzeria_address))
    return 'HANDLE_PICKUP'


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
    elif user_reply == '/pickup':
        user_state = 'HANDLE_PICKUP'
    else:
        user_state = db.get(chat_id).decode("utf-8")

    states_functions = {
            'START': start,
            'HANDLE_MENU': handle_menu,
            'HANDLE_DESCRIPTION': handle_description,
            'HANDLE_CART': handle_cart,
            'HANDLE_WAITING': handle_waiting,
            'HANDLE_RANGE': handle_rang,
            'HANDLE_PICKUP': handle_pickup,
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
