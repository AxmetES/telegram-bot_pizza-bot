import requests
from environs import Env

import flows

env = Env()
env.read_env()

entries_url = 'https://api.moltin.com/v2/flows/pizzeria/entries'
access_token = flows.create_client_credential_token(flows.access_token_url)


def get_pizzerias_coords(entries_url, access_token):
    pizzerias_coords = []
    headers = {
            'Authorization': 'Bearer {}'.format(access_token),
            }

    response = requests.get(entries_url, headers=headers)
    response.raise_for_status()

    for pizzeria in response.json()['data']:
        pizzerias_coords.append(
                {
                        pizzeria['pizzeria-1-address']: {
                                'lng': pizzeria['pizzeria-1-lng'], 'lat': pizzeria['pizzeria-1-lat']
                                }
                        })

    return pizzerias_coords


pizzerias_coords = get_pizzerias_coords(entries_url, access_token)
