import requests
import pprint

address_url = 'https://dvmn.org/media/filer_public/90/90/9090ecbf-249f-42c7-8635-a96985268b88/addresses.json'
menu_url = 'https://dvmn.org/media/filer_public/a2/5a/a25a7cbd-541c-4caf-9bf9-70dcdf4a592e/menu.json'


def load_address(address_url):
    response = requests.get(address_url)
    response.raise_for_status()
    return response.json()


def load_menu(menu_url):
    response = requests.get(menu_url)
    response.raise_for_status()
    return response.json()


def main():
    address = load_address(address_url)
    menu = load_menu(menu_url)

    # pprint.pprint(address)
    pprint.pprint(menu)


if __name__ == '__main__':
    main()
