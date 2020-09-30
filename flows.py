import requests

import load_data
import load_menu
import argparse

flow_url = 'https://api.moltin.com/v2/flows'
flow_id = '295dd7e9-c8ca-47bf-b761-8e678be2be8a'
url = 'https://api.moltin.com/v2/fields'


# def create_flow(url):
#     headers = {
#         'Authorization': f'{shop_token}',
#         'Content-Type': 'application/json',
#     }
#     data = {"data": {"type": "flow", "name": flow_name, "slug": "pizzeria",
#                      "description": "Extends the default product object", "enabled": True}}
#
#     response = requests.post(url, headers=headers, json=data)
#     return response.json()


def create_field_to_flow(url, token, field, field_type, field_slug):
    headers = {
        'Authorization': token,
        'Content-Type': 'application/json',
    }

    data = {"data": {"type": "field", "name": field, "slug": field_slug, "field_type": field_type,
                     "description": "Pizzeria Flow", "required": False, "default": 0,
                     "enabled": True, "order": 1, "omit_null": False, "relationships": {
            "flow": {"data": {"type": "flow", "id": flow_id}}}}}

    response = requests.post(url, headers=headers, json=data)
    return response.json()


def create_fields(field_url, fields, shop_token):
    created_fields = []
    for field in fields:
        field_data = create_field_to_flow(field_url, shop_token, field=field['field'], field_type=field['field_type'],
                                          field_slug=field['field_slug'])
        created_fields.append(field_data)
    return created_fields


def create_entry(shop_token, field, flow_slug):
    entry_url = f'https://api.moltin.com/v2/flows/{flow_slug}/entries'
    headers = {
        'Authorization': shop_token,
        'Content-Type': 'application/json',
    }
    json = {'data': {"type": "entry", "pizzeria-1-address": field['address']['full'],
                     "pizzeria-1-alias": field['alias'],
                     "pizzeria-1-lat": float(field['coordinates']['lat']),
                     "pizzeria-1-lng": float(field['coordinates']['lon']),
                     }}

    response = requests.post(entry_url, headers=headers, json=json)
    return response.json()


def upload_address_to_flow(shop_token, fields, flow_slug):
    for field in fields:
        created_entry = create_entry(shop_token, field, flow_slug)
        print(created_entry)


if __name__ == '__main__':
    flow_slug = 'pizzeria'
    fields = load_data.load_menu(load_data.address_url)

    shop_token = load_menu.get_shop_token(load_menu.token_url)['access_token']
    print(shop_token)

    upload_address_to_flow(shop_token, fields, flow_slug)

    # created_fields = create_fields(url, fields, shop_token)
    # print(created_fields)
