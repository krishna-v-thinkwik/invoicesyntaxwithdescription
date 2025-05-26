from flask import Flask, request, jsonify
from google.oauth2 import service_account
from googleapiclient.discovery import build
import os
import json
import re

app = Flask(__name__)

# Setup Google Sheets API (initialize only once on startup)
SERVICE_ACCOUNT_JSON = os.environ.get('SERVICE_ACCOUNT_JSON')
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
SHEET_ID = '1sVuQGZjHToaryPNNSOytHNZPnGHFqzc2XfbDGsOxRSI'
SHEET_NAME = 'pizza_price'

if not SERVICE_ACCOUNT_JSON:
    raise Exception("SERVICE_ACCOUNT_JSON not found in environment variables")

# Load service account credentials from environment variable JSON
creds_dict = json.loads(SERVICE_ACCOUNT_JSON)
creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)

service = build('sheets', 'v4', credentials=creds)
sheet = service.spreadsheets()

# Fetch item prices once on startup
result = sheet.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_NAME}!A2:B").execute()
data = result.get('values', [])
item_prices = {row[0].strip().lower(): int(row[1]) for row in data}

# Parsing functions
def parse_items(text):
    pattern = r'(\d+)\s+([\w\s]+?)(?:\sand\s|$)'
    matches = re.findall(pattern, text)
    return [(int(qty), name.strip().lower()) for qty, name in matches]

def parse_toppings(topping_text):
    topping_sets = {}
    patterns = re.findall(r'(.+?)\s+for\s+([\w\s]+?)(?:\sand\s|$)', topping_text)
    for toppings, pizza in patterns:
        topping_list = [t.strip().lower() for t in re.split(r'and|,', toppings)]
        topping_sets[pizza.strip().lower()] = topping_list
    return topping_sets

def extract_pizza_description(name, toppings):
    name = name.lower()
    desc_parts = []

    # Size
    if 'regular' in name:
        desc_parts.append("Size : Regular")
    elif 'medium' in name:
        desc_parts.append("Size : Medium")
    elif 'large' in name:
        desc_parts.append("Size : Large")

    # Crust/Burst types (check longer names first to avoid partial matches)
    if 'cheese burst' in name:
        desc_parts.append("Burst : Cheese Burst")
    elif 'fresh pan pizza' in name:
        desc_parts.append("Crust : Fresh Pan Pizza")
    elif 'wheat thin crust' in name:
        desc_parts.append("Crust : Wheat Thin Crust")
    elif 'new hand tossed' in name:
        desc_parts.append("Crust : New Hand Tossed")
    elif 'classic hand tossed' in name:
        desc_parts.append("Crust : Classic Hand Tossed")

    # Toppings
    if toppings:
        desc_parts.append("Toppings : " + ", ".join(t.capitalize() for t in toppings))

    return " , ".join(desc_parts)

@app.route('/calculate_price', methods=['POST'])
def calculate_price():
    request_json = request.get_json()

    if not request_json:
        return jsonify({'error': 'Invalid JSON'}), 400

    pizzaname = request_json.get('pizzaname', '')
    pizzatoppings = request_json.get('pizzatoppings', '')
    additionalitems = request_json.get('additionalitems', '')

    response_items = []

    # Calculate pizzas
    parsed_pizzas = parse_items(pizzaname)
    parsed_toppings = parse_toppings(pizzatoppings)

    for qty, pizza in parsed_pizzas:
        base_price = item_prices.get(pizza, 0)
        toppings = []

        for key in parsed_toppings:
            if key in pizza:
                toppings = parsed_toppings[key]
                break

        topping_total = sum(item_prices.get(t, 0) for t in toppings)
        pizza_total = (base_price + topping_total) * qty

        description = extract_pizza_description(pizza, toppings)

        response_items.append({
            "name": pizza,
            "qty": qty,
            "amount": pizza_total,
            "currency": "USD",
            "description": description
        })

    # Calculate additional items
    parsed_additional = parse_items(additionalitems)
    for qty, item in parsed_additional:
        item_price = item_prices.get(item, 0)
        item_total = item_price * qty
        response_items.append({
            "name": item,
            "qty": qty,
            "amount": item_total,
            "currency": "USD"
        })

    return jsonify(response_items)

@app.route('/')
def home():
    return "Pizza Price Calculator API is running!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
