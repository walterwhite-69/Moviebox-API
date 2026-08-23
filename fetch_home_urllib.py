import urllib.request
import json

req = urllib.request.Request(
    'https://h5-api.aoneroom.com/wefeed-h5api-bff/home?host=moviebox.ph',
    headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36',
        'X-Client-Info': '{"timezone":"America/New_York"}',
        'X-Request-Lang': 'en'
    }
)
with urllib.request.urlopen(req) as response:
    data = json.loads(response.read().decode())
    with open('home.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
