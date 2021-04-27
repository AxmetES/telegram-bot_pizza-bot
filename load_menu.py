import os

import requests
from dotenv import load_dotenv

import load_data

load_dotenv()

token_url = 'https://api.moltin.com/oauth/access_token'
products_url = 'https://api.moltin.com/v2/products'
file_url = 'https://api.moltin.com/v2/files'
entries_url = 'https://api.moltin.com/v2/flows/:pizzeria/entries'

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv('CLIENT_SECRET')


def get_access_token(url):
    data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
            }
    responce = requests.post(url, data=data)
    # responce.raise_for_status()
    return responce.json()


def get_customer(customer_id):
    url = f'https://api.moltin.com/v2/customers/{customer_id}'
    headers = {
            'Authorization': f'Bearer {access_token}',
            }
    response = requests.get(url, headers=headers)
    return response.json()


def create_customer(customer_data, access_token):
    customer_url = 'https://api.moltin.com/v2/customers'
    headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            }
    response = requests.post(customer_url, headers=headers, json=customer_data)
    response.raise_for_status()
    return response.json()


def creat_product(url, access_token, pizza):
    headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            }
    data = {
            "data": {
                    "type": "product", "name": pizza['name'], "slug": str(pizza['id']) + '-pizza',
                    "sku": str(pizza['id']),
                    "description": pizza['description'],
                    "manage_stock": False,
                    "price": [{"amount": pizza['price'], "currency": "RUB", "includes_tax": False}],
                    "status": "live", "commodity_type": "physical"
                    }
            }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json()


def create_file(url, access_token, image_url):
    image = requests.get(image_url)
    headers = {
            'Authorization': f'Bearer {access_token}',
            }
    files = {
            'file': (image_url, image.content),
            'public': (None, 'true'),
            }
    response = requests.post(url, headers=headers, files=files)
    # response.raise_for_status()
    return response.json()


def create_main_image_relation(created_product_id, image_file_id):
    url = f'https://api.moltin.com/v2/products/{created_product_id}/relationships/main-image'
    headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            }
    data = {"data": {"type": "main_image", "id": image_file_id}}
    response = requests.post(url, headers=headers,
                             json=data)
    return response.json()


def get_cart(chat_id, access_token):
    cart_url = f'https://api.moltin.com/v2/carts/{chat_id}'
    headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            }
    response = requests.get(cart_url, headers=headers)
    # response.raise_for_status()
    return response.json()


def add_product_to_cart(chat_id, access_token, payload_cart):
    url = f'https://api.moltin.com/v2/carts/{chat_id}/items/'

    headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
            }
    response = requests.post(url, headers=headers, json=payload_cart)
    response.raise_for_status()


def get_cart_items(chat_id, access_token):
    url = f'https://api.moltin.com/v2/carts/{chat_id}/items/'
    headers = {
            'Authorization': f'Bearer {access_token}',
            }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_cart_total(access_token, chat_id):
    url = f'https://api.moltin.com/v2/carts/{chat_id}'
    headers = {
            'Authorization': f'Bearer {access_token}',
            }

    response = requests.get(url, headers=headers)
    return response.json()


def get_products(product_url, access_token):
    headers = {
            'Authorization': f'Bearer {access_token}'
            }
    response = requests.get(product_url, headers=headers)
    response.raise_for_status()
    return response.json()


def get_product(products_id, access_token):
    url = f'https://api.moltin.com/v2/products/{products_id}'
    headers = {
            'Authorization': f'Bearer {access_token}',
            }
    response = requests.get(url, headers=headers)
    # response.raise_for_status()
    return response.json()


def get_file_url(main_image_id, access_token):
    headers = {
            f"Authorization": access_token,
            }
    file_url = f'https://api.moltin.com/v2/files/{main_image_id}/'
    response = requests.get(file_url, headers=headers)
    # response.raise_for_status()
    image_url = response.json()
    return image_url


def load_menu_to_pizzeria(menu, access_token):
    for pizza in menu:
        try:
            created_product_id = creat_product(products_url, access_token, pizza)['data']['id']
        except Exception as msg:
            print(msg)
            continue
        print(created_product_id)

        image_file_id = \
            create_file(file_url, access_token, image_url=pizza['product_image']['url'])[
                'data']['id']
        print(f' image id ---- {image_file_id}')

        main_image_relation = create_main_image_relation(created_product_id, image_file_id)
        print(f' relations info ---- {main_image_relation}')


def delete_cart_product(chat_id, product_id, access_token):
    cart_url = f'https://api.moltin.com/v2/carts/{chat_id}/items/{product_id}'

    headers = {
            'Authorization': f'Bearer {access_token}',
            }

    response = requests.delete(cart_url, headers=headers)
    response.raise_for_status()


def get_all_products(products_url, access_token):
    headers = {
            'Authorization': f'Bearer {access_token}',
            }
    response = requests.get(products_url, headers=headers)
    return response.json()


def get_all_files(file_url, access_token):
    headers = {
            'Authorization': f'Bearer {access_token}',
            }
    response = requests.get(file_url, headers=headers)
    return response.json()


def delete_products(access_token, product_id):
    url = f'https://api.moltin.com/v2/products/{product_id}'
    headers = {
            'Authorization': f'Bearer {access_token}',
            }
    requests.delete(url, headers=headers)


def delete_files(access_token, file_id):
    url = f'https://api.moltin.com/v2/files/{file_id}'
    headers = {
            'Authorization': f'Bearer {access_token}',
            }
    requests.delete(url, headers=headers)


if __name__ == '__main__':
    menu = load_data.load_menu(load_data.menu_url)

    access_token = get_access_token(token_url)['access_token']
    print(f' shop token ---- {access_token}')

    # load_menu_to_pizzeria(menu, access_token)
    # all_files = get_all_products(file_url, access_token)
    # for file in all_files['data']:
    #     delete_files(access_token, file['id'])
    #
    # all_products = get_all_products(products_url, access_token)
    # for products in all_products['data']:
    #     delete_products(access_token, products['id'])
