import asyncio
import json
from api import _make_request

async def run():
    res = await _make_request('https://h5-api.aoneroom.com/wefeed-h5api-bff/detail?detailPath=the-boys-hindi-g82RrsyHOK5')
    data = res.get('data', {})
    print(list(data.keys()))
if __name__ == "__main__":
    asyncio.run(run())
