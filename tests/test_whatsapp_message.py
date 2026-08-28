import os

import requests

access_token = os.environ["FR_AGENT_WHATSAPP_TOKEN"]
phone_number_id = os.environ["FR_AGENT_WHATSAPP_PHONE_NUMBER_ID"]
number_destine = ""

url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content_Type": "application/json",
}

payload = {
    "messaging_product": "whatsapp",
    "to": number_destine,
    "type": "template",
    "template": {"name": "hello_world", "language": {"code": "en_US"}},
}

respuesta = requests.post(url, headers=headers, json=payload)

print("Status: ", respuesta.status_code)
print("Response: ", respuesta.text)
