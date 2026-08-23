import asyncio
import json
import httpx
from api import _make_request, PLAYER_HEADERS

async def run():
    res = await _make_request('https://h5-api.aoneroom.com/wefeed-h5api-bff/media-player/get-domain')
    domain = res.get('data', 'https://netfilm.world').rstrip('/')
    play_url = f'{domain}/wefeed-h5api-bff/subject/play?subjectId=1489180587696031424&se=1&ep=1&detailPath=avatar-the-last-airbender-hindi-UqlHOlHs0M1'
    async with httpx.AsyncClient(follow_redirects=True, timeout=25) as c:
        resp = await c.get(play_url, headers={**PLAYER_HEADERS, 'Referer': f'{domain}/spa/videoPlayPage/movies/avatar-the-last-airbender-hindi-UqlHOlHs0M1'})
        data = resp.json().get('data', {})
        print(json.dumps(data.get('streams', []), indent=2))
if __name__ == "__main__":
    asyncio.run(run())
