import asyncio
import json
from api import _make_request

async def run():
    res = await _make_request('https://h5-api.aoneroom.com/wefeed-h5api-bff/detail?detailPath=avatar-the-last-airbender-hindi-UqlHOlHs0M1')
    keys = res.get('data', {}).get('subject', {}).keys()
    print(list(keys))
if __name__ == "__main__":
    asyncio.run(run())
