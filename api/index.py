import re
import json
import httpx
import asyncio
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="MovieBox API Pro",
    description="Full Pure REST API for moviebox.ph — Multi-Language & Direct Stream Extraction",
    version="2.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://moviebox.ph"
API_BASE = "https://h5-api.aoneroom.com/wefeed-h5api-bff"
STREAM_BASE = "https://h5.aoneroom.com/wefeed-h5-bff"

_bearer_token: str | None = None

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
    "Referer": "https://moviebox.ph/",
    "Origin": "https://moviebox.ph",
    "X-Client-Info": '{"timezone":"Asia/Dhaka"}',
    "X-Request-Lang": "en",
    "X-Forwarded-For": "119.92.128.1",
    "X-Real-IP": "119.92.128.1",
    "CF-IPCountry": "PH",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
}

def _extract_language_badge(title: str, corner: str = "") -> str:
    """Extract language/dubbing badge from corner or title [Language]."""
    if corner and corner.strip():
        return corner.strip()
    if not title:
        return ""
    m = re.search(r"\[(.*?)\]", title)
    if m:
        return m.group(1).strip()
    return ""

# ── Content Validation Helpers ──────────────────────────────────────
import time as _time

_slug_cache: dict[str, tuple[bool, float]] = {}   # slug -> (is_valid, timestamp)
_CACHE_TTL = 600   # 10 minutes
_validation_semaphore = asyncio.Semaphore(5)       # max 5 concurrent upstream checks


async def _validate_slug(slug: str, client: httpx.AsyncClient, token: str) -> bool:
    """Return True if the slug has a valid detail response."""
    if not slug:
        return False

    cached = _slug_cache.get(slug)
    if cached:
        is_valid, ts = cached
        if _time.time() - ts < _CACHE_TTL:
            return is_valid

    url = f"{API_BASE}/detail?detailPath={slug}"
    try:
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": f"Bearer {token}" if token else "",
        }
        async with _validation_semaphore:
            resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            _slug_cache[slug] = (False, _time.time())
            return False
        data = resp.json()
        detail_data = data.get("data")
        if not detail_data:
            _slug_cache[slug] = (False, _time.time())
            return False
        subject = detail_data.get("subject")
        if not subject:
            _slug_cache[slug] = (False, _time.time())
            return False
        if subject.get("isPremium") is True:
            _slug_cache[slug] = (False, _time.time())
            return False
        _slug_cache[slug] = (True, _time.time())
        return True
    except Exception:
        _slug_cache[slug] = (False, _time.time())
        return False


async def _validate_items(items: list) -> list:
    """Filter a list of items, keeping only those with valid detail slugs."""
    if not items:
        return items

    token = await _get_bearer_token()

    async def _do_validation():
        async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
            async def _check(item):
                slug = item.get("slug")
                is_valid = await _validate_slug(slug, client, token)
                return (item, is_valid)

            results = await asyncio.gather(
                *[_check(item) for item in items],
                return_exceptions=True
            )
        valid_items = []
        for result in results:
            if isinstance(result, Exception):
                continue
            item, is_valid = result
            if is_valid:
                valid_items.append(item)
        return valid_items

    try:
        return await asyncio.wait_for(_do_validation(), timeout=15.0)
    except asyncio.TimeoutError:
        print("[VALIDATE] Batch validation timed out, returning all items unfiltered")
        return items

async def _get_bearer_token() -> str:
    """Auto-acquire a guest JWT from the x-user response header."""
    global _bearer_token
    if _bearer_token:
        return _bearer_token
    async with httpx.AsyncClient(follow_redirects=True, timeout=25) as client:
        resp = await client.get(f"{API_BASE}/home?host=moviebox.ph", headers=DEFAULT_HEADERS)
        x_user = resp.headers.get("x-user")
        if x_user:
            _bearer_token = json.loads(x_user).get("token")
        if not _bearer_token:
            cookie = resp.headers.get("set-cookie", "")
            m = re.search(r"token=([^;]+)", cookie)
            if m:
                _bearer_token = m.group(1)
    return _bearer_token or ""

async def _make_request(url: str, method: str = "GET", payload: dict = None, custom_headers: dict = None) -> dict:
    global _bearer_token
    token = await _get_bearer_token()
    headers = {
        **DEFAULT_HEADERS,
        "Authorization": f"Bearer {token}" if token else "",
        **(custom_headers or {})
    }
    async with httpx.AsyncClient(follow_redirects=True, timeout=25) as client:
        try:
            if method == "POST":
                resp = await client.post(url, headers=headers, json=payload)
            else:
                resp = await client.get(url, headers=headers)

            x_user = resp.headers.get("x-user")
            if x_user:
                new_token = json.loads(x_user).get("token")
                if new_token:
                    _bearer_token = new_token

            if resp.status_code != 200:
                raise HTTPException(status_code=502, detail=f"Upstream API error: {resp.status_code}")

            return resp.json()
        except Exception as e:
            if isinstance(e, HTTPException): raise e
            raise HTTPException(status_code=502, detail=f"Request failed: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MovieBox Pure API | Pro Dashboard</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono:wght@400;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --primary: #ff3d71;
                --secondary: #3366ff;
                --accent: #00f2ff;
                --bg: #07080c;
                --card-bg: rgba(255, 255, 255, 0.03);
                --glass: rgba(255, 255, 255, 0.06);
                --text: #ffffff;
            }
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body {
                font-family: 'Outfit', sans-serif;
                background: var(--bg);
                color: var(--text);
                min-height: 100vh;
                background-image: 
                    radial-gradient(circle at 10% 10%, rgba(255, 61, 113, 0.12) 0%, transparent 40%),
                    radial-gradient(circle at 90% 90%, rgba(51, 102, 255, 0.12) 0%, transparent 40%);
            }
            .container { max-width: 1200px; margin: 0 auto; padding: 60px 24px; }
            header { text-align: center; margin-bottom: 80px; }
            h1 { font-size: clamp(2.5rem, 8vw, 4rem); font-weight: 800; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 30px; margin-top: 20px; }
            .card { background: var(--card-bg); border: 1px solid var(--glass); border-radius: 28px; padding: 35px; backdrop-filter: blur(12px); display: flex; flex-direction: column; }
            .card-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 18px; }
            .card-desc { color: #9ea3ac; font-size: 1rem; line-height: 1.6; margin-bottom: 25px; flex-grow: 1; }
            .endpoint { font-family: 'JetBrains Mono', monospace; background: rgba(0,0,0,0.4); padding: 14px; border-radius: 14px; font-size: 0.85rem; color: var(--accent); border: 1px solid rgba(0,242,255,0.15); margin-bottom: 25px; word-break: break-all; }
            .btn { display: flex; align-items: center; justify-content: center; padding: 16px; background: #ffffff; color: #000000; text-decoration: none; border-radius: 16px; font-weight: 700; font-size: 0.95rem; }
            .btn:hover { background: var(--primary); color: #fff; }
        </style>
    </head>
    <body>
        <div class="container">
            <header>
                <h1>MovieBox Pro</h1>
                <p style="color: #667; font-size: 1.25rem;">Multi-Language Direct Stream Extraction API</p>
            </header>
            <div class="grid">
                <div class="card">
                    <div class="card-title">🏠 Multi-Language Home</div>
                    <p class="card-desc">Headlines, Tagalog Dubbed, Hindi Dubbed, Anime & Trending blocks.</p>
                    <div class="endpoint">/home</div>
                    <a href="/home" target="_blank" class="btn">Launch API</a>
                </div>
                <div class="card">
                    <div class="card-title">🏆 Rankings</div>
                    <p class="card-desc">Top rated, most watched charts.</p>
                    <div class="endpoint">/ranking</div>
                    <a href="/ranking" target="_blank" class="btn">View Rankings</a>
                </div>
                <div class="card">
                    <div class="card-title">🎬 Direct Stream Engine</div>
                    <p class="card-desc">Working direct MP4 CDN links (Supports 360p - 1080p).</p>
                    <div class="endpoint">/api/stream/{subject_id}?se=1&ep=1</div>
                    <a href="/api/stream/56988683026712168?detail_path=attack-on-titan-hindi-kGWQOIx0d4&se=1&ep=1" target="_blank" class="btn">Test Streams</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/home")
async def get_home():
    """Returns rich Home & Explore sections including Tagalog Dubbed, Hindi Dubbed, Movies, Series & Anime."""
    token = await _get_bearer_token()
    headers = {
        **DEFAULT_HEADERS,
        "Authorization": f"Bearer {token}" if token else ""
    }

    async with httpx.AsyncClient(follow_redirects=True, timeout=12) as client:
        async def fetch_home_base():
            try:
                res = await client.get(f"{API_BASE}/home?host=moviebox.ph", headers=headers)
                if res.status_code != 200: return []
                sections = []
                for op in res.json().get("data", {}).get("operatingList", []) or []:
                    op_type = op.get("type")
                    title = op.get("title", "Featured")
                    if op_type == "BANNER":
                        items = [{
                            "name": item.get("title") or (item.get("subject") or {}).get("title"),
                            "poster_url": item.get("image", {}).get("url") or (item.get("subject") or {}).get("cover", {}).get("url"),
                            "slug": item.get("detailPath") or (item.get("subject") or {}).get("detailPath"),
                            "subject_id": (item.get("subject") or {}).get("subjectId"),
                            "badge": _extract_language_badge(item.get("title"), (item.get("subject") or {}).get("corner"))
                        } for item in op.get("banner", {}).get("items", []) if item.get("title") and "Communities" not in item.get("title")]
                        sections.append({"section": "Banner", "count": len(items), "items": items})
                    elif op_type in ["SUBJECTS_MOVIE", "SUBJECTS_TV", "SUBJECTS_ANIMATION"]:
                        items = [{
                            "name": sub.get("title"),
                            "poster_url": sub.get("cover", {}).get("url"),
                            "slug": sub.get("detailPath"),
                            "subject_id": sub.get("subjectId"),
                            "badge": _extract_language_badge(sub.get("title"), sub.get("corner")),
                            "rating": sub.get("imdbRatingValue")
                        } for sub in op.get("subjects", [])]
                        sections.append({"section": title, "count": len(items), "items": items})
                return sections
            except Exception:
                return []

        async def fetch_search_row(title: str, keyword: str):
            try:
                res = await client.post(f"{API_BASE}/subject/search", headers=headers, json={"keyword": keyword, "page": 1, "perPage": 18})
                if res.status_code != 200: return None
                raw = res.json().get("data", {}).get("items", [])
                items = [{
                    "name": sub.get("title"),
                    "poster_url": sub.get("cover", {}).get("url"),
                    "slug": sub.get("detailPath"),
                    "subject_id": sub.get("subjectId"),
                    "badge": _extract_language_badge(sub.get("title"), sub.get("corner")) or keyword.strip("[]"),
                    "rating": sub.get("imdbRatingValue"),
                    "description": sub.get("description", ""),
                    "genre": sub.get("genre", ""),
                    "year": sub.get("releaseDate", "")[:4] if sub.get("releaseDate") else ""
                } for sub in raw]
                if items:
                    return {"section": title, "count": len(items), "items": items}
            except Exception:
                pass
            return None

        async def fetch_category_row(title: str, tab_id: int):
            try:
                res = await client.post(f"{API_BASE}/subject/filter", headers=headers, json={"tabId": tab_id, "filter": {"sort": "RECOMMEND", "genre": "ALL", "country": "ALL", "year": "ALL", "language": "ALL"}, "page": 1, "perPage": 18})
                if res.status_code != 200: return None
                raw = res.json().get("data", {}).get("items", [])
                items = [{
                    "name": sub.get("title"),
                    "poster_url": sub.get("cover", {}).get("url"),
                    "slug": sub.get("detailPath"),
                    "subject_id": sub.get("subjectId"),
                    "badge": _extract_language_badge(sub.get("title"), sub.get("corner")),
                    "rating": sub.get("imdbRatingValue"),
                    "year": sub.get("releaseDate", "")[:4] if sub.get("releaseDate") else ""
                } for sub in raw]
                if items:
                    return {"section": title, "count": len(items), "items": items}
            except Exception:
                pass
            return None

        # Execute parallel section gathering for speed
        results = await asyncio.gather(
            fetch_home_base(),
            fetch_search_row("Tagalog Dubbed Series & Movies", "[Tagalog]"),
            fetch_search_row("Hindi Dubbed Blockbusters", "[Hindi]"),
            fetch_category_row("Top TV Series", 5),
            fetch_category_row("Popular Movies", 2),
            fetch_category_row("Anime & Animation", 8),
            fetch_search_row("Asian & Korean Dramas", "Korean Drama")
        )

        all_sections = []
        if results[0]:
            all_sections.extend(results[0])
        for sec in results[1:]:
            if sec and sec.get("count", 0) > 0:
                all_sections.append(sec)

    return {"status": "success", "sections": all_sections}

async def _get_category_data(tab_id: int, page: int = 1, per_page: int = 24, sort: str = "RECOMMEND", language: str = "ALL") -> dict:
    url = f"{API_BASE}/subject/filter"
    payload = {"tabId": tab_id, "filter": {"sort": sort, "genre": "ALL", "country": "ALL", "year": "ALL", "language": language}, "page": page, "perPage": per_page}
    data = await _make_request(url, method="POST", payload=payload)
    inner = data.get("data", {})
    raw_items = inner.get("items", inner.get("subjects", []))
    items = [{
        "name": sub.get("title"),
        "poster_url": sub.get("cover", {}).get("url"),
        "slug": sub.get("detailPath"),
        "subject_id": sub.get("subjectId"),
        "badge": _extract_language_badge(sub.get("title"), sub.get("corner")),
        "rating": sub.get("imdbRatingValue"),
        "year": sub.get("releaseDate", "")[:4] if sub.get("releaseDate") else None
    } for sub in raw_items]
    pager = inner.get("pager", {})
    total = pager.get("totalCount") or inner.get("total") or len(items)
    return {"page": page, "per_page": per_page, "total": total, "items": items}

@app.get("/movies")
async def get_movies(page: int = 1, sort: str = "RECOMMEND", language: str = "ALL"):
    return await _get_category_data(tab_id=2, page=page, sort=sort, language=language)

@app.get("/tv-series")
async def get_tv_series(page: int = 1, sort: str = "RECOMMEND", language: str = "ALL"):
    return await _get_category_data(tab_id=5, page=page, sort=sort, language=language)

@app.get("/animation")
async def get_animation(page: int = 1, sort: str = "RECOMMEND", language: str = "ALL"):
    return await _get_category_data(tab_id=8, page=page, sort=sort, language=language)

@app.get("/search/suggest")
async def get_search_suggestions(q: str = Query(..., min_length=1)):
    url = f"{API_BASE}/subject/search-suggest"
    data = await _make_request(url, method="POST", payload={"keyword": q, "perPage": 10})
    inner = data.get("data", {})
    raw = inner.get("items", inner.get("list", []))
    suggestions = []
    for item in raw:
        sub = item.get("subject") or {}
        suggestions.append({
            "title": sub.get("title") or item.get("word") or item.get("title"),
            "slug": sub.get("detailPath") or item.get("detailPath"),
            "subject_id": sub.get("subjectId") or item.get("subjectId")
        })
    return {"suggestions": suggestions}

@app.get("/search")
async def search(q: str = Query(..., min_length=1), page: int = 1):
    url = f"{API_BASE}/subject/search"
    data = await _make_request(url, method="POST", payload={"keyword": q, "page": page, "perPage": 20})
    inner = data.get("data", {})
    raw = inner.get("items", inner.get("list", []))
    items = [{
        "name": sub.get("title"),
        "poster_url": sub.get("cover", {}).get("url"),
        "slug": sub.get("detailPath"),
        "subject_id": sub.get("subjectId"),
        "description": sub.get("description", ""),
        "genre": sub.get("genre", ""),
        "language": _extract_language_badge(sub.get("title"), sub.get("corner")),
        "badge": _extract_language_badge(sub.get("title"), sub.get("corner")),
        "rating": sub.get("imdbRatingValue", ""),
        "year": sub.get("releaseDate", "")[:4] if sub.get("releaseDate") else "",
        "country": sub.get("countryName", "")
    } for sub in raw]
    items = await _validate_items(items)
    pager = inner.get("pager", {})
    total = pager.get("totalCount") or inner.get("total") or len(items)
    return {"query": q, "page": page, "total": total, "items": items}

@app.get("/detail/{slug}")
async def get_movie_detail(slug: str):
    url = f"{API_BASE}/detail?detailPath={slug}"
    return await _make_request(url)

@app.get("/ranking")
async def get_ranking():
    url = f"{API_BASE}/ranking-list"
    data = await _make_request(url)
    ranking_list = data.get("data", {}).get("rankingList", []) or []
    
    async def fetch_rank_movies(rank):
        rank_id = rank.get("id")
        rank_name = rank.get("name")
        if not rank_id:
            return None
        try:
            rank_data = await _make_request(f"{API_BASE}/ranking-list?id={rank_id}")
            raw_subjects = rank_data.get("data", {}).get("subjectList", []) or []
            movies = [{
                "name": sub.get("title"),
                "poster_url": sub.get("cover", {}).get("url") if sub.get("cover") else None,
                "slug": sub.get("detailPath"),
                "subject_id": str(sub.get("subjectId", "") or ""),
                "badge": _extract_language_badge(sub.get("title"), sub.get("corner")),
                "rating": sub.get("imdbRatingValue"),
                "year": sub.get("releaseDate", "")[:4] if sub.get("releaseDate") else None
            } for sub in raw_subjects]
            return {
                "section": rank_name,
                "count": len(movies),
                "items": movies,
                "movies": movies
            }
        except Exception:
            return None

    tasks = [fetch_rank_movies(rank) for rank in ranking_list]
    sections = await asyncio.gather(*tasks)
    sections = [s for s in sections if s is not None]
    return {"status": "success", "sections": sections}

async def _fetch_raw_stream_data(client: httpx.AsyncClient, subject_id: str, detail_path: str, se: int, ep: int, token: str = "") -> dict | None:
    targets = [
        {
            "url": f"https://h5.aoneroom.com/wefeed-h5-bff/web/subject/play?subjectId={subject_id}&se={se}&ep={ep}&detailPath={detail_path}",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://netfilm.world",
                "Referer": f"https://netfilm.world/spa/videoPlayPage/movies/{detail_path}?id={subject_id}&type=/movie/detail&detailSe={se}&detailEp={ep}&lang=en",
                "X-Forwarded-For": "119.92.128.1",
                "X-Real-IP": "119.92.128.1",
                "CF-IPCountry": "PH"
            }
        },
        {
            "url": f"https://netfilm.world/wefeed-h5api-bff/subject/play?subjectId={subject_id}&se={se}&ep={ep}&detailPath={detail_path}",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://netfilm.world",
                "Referer": f"https://netfilm.world/spa/videoPlayPage/movies/{detail_path}?id={subject_id}&type=/movie/detail&detailSe={se}&detailEp={ep}&lang=en",
                "X-Forwarded-For": "119.92.128.1",
                "X-Real-IP": "119.92.128.1",
                "CF-IPCountry": "PH"
            }
        },
        {
            "url": f"https://h5-api.aoneroom.com/wefeed-h5api-bff/subject/play?subjectId={subject_id}&se={se}&ep={ep}&detailPath={detail_path}",
            "headers": {
                **DEFAULT_HEADERS,
                "Authorization": f"Bearer {token}" if token else ""
            }
        }
    ]
    
    for target in targets:
        try:
            resp = await client.get(target["url"], headers=target["headers"], timeout=8)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                streams = [s for s in data.get("streams", []) if s.get("url")]
                if streams or data.get("hasResource"):
                    return data
        except Exception:
            continue
    return None

# ----------------------------------------------------
# 📌 ফিক্স করা স্ট্রিমিং এন্ডপয়েন্ট (Multi-Domain Direct MP4 Stream)
# ----------------------------------------------------
@app.get("/api/stream/{subject_id}")
async def get_stream_sources(subject_id: str, detail_path: str = "", se: int = 0, ep: int = 0):
    token = await _get_bearer_token()
    data = None

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        # Attempt 1: Requested (se, ep)
        data = await _fetch_raw_stream_data(client, subject_id, detail_path, se, ep, token)
        
        # Attempt 2: Smart fallback (0,0) <-> (1,1) if no stream sources found
        if not data or not [s for s in data.get("streams", []) if s.get("url")]:
            fallback_se, fallback_ep = (1, 1) if (se == 0 and ep == 0) else (0, 0)
            fallback_data = await _fetch_raw_stream_data(client, subject_id, detail_path, fallback_se, fallback_ep, token)
            if fallback_data and [s for s in fallback_data.get("streams", []) if s.get("url")]:
                data = fallback_data
                se, ep = fallback_se, fallback_ep

    if not data:
        return {
            "subject_id": subject_id,
            "se": se,
            "ep": ep,
            "has_resource": False,
            "sources": [],
            "hls": [],
            "dash": [],
            "free_episodes": None,
            "limited": False,
            "note": "No stream found for this selection."
        }

    has_resource = data.get("hasResource", False)
    streams = [
        {
            "resolution": f"{s.get('resolutions')}p" if s.get('resolutions') else "HD",
            "format": s.get("format", "mp4"),
            "url": s.get("url"),
            "size": s.get("size"),
            "duration": s.get("duration"),
            "codec": s.get("codecName")
        }
        for s in data.get("streams", []) if s.get("url")
    ]
    
    return {
        "subject_id": subject_id,
        "se": se,
        "ep": ep,
        "has_resource": has_resource or len(streams) > 0,
        "sources": streams,
        "hls": data.get("hls", []),
        "dash": data.get("dash", []),
        "free_episodes": data.get("freeNum"),
        "limited": data.get("limited", False),
        "note": None if (has_resource or len(streams) > 0) else "No stream found for this selection."
    }

@app.get("/api/stream/{subject_id}/captions")
async def get_captions(subject_id: str, detail_path: str = "", se: int = 0, ep: int = 0):
    token = await _get_bearer_token()
    data = None
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        data = await _fetch_raw_stream_data(client, subject_id, detail_path, se, ep, token)
        if not data:
            fallback_se, fallback_ep = (1, 1) if (se == 0 and ep == 0) else (0, 0)
            data = await _fetch_raw_stream_data(client, subject_id, detail_path, fallback_se, fallback_ep, token)
            if data:
                se, ep = fallback_se, fallback_ep

    if not data:
        return {"subject_id": subject_id, "se": se, "ep": ep, "count": 0, "captions": []}

    streams = data.get("streams", [])
    dash = data.get("dash", [])

    stream_id = None
    stream_format = None
    if streams:
        stream_id = streams[0].get("id")
        stream_format = streams[0].get("format", "MP4")
    elif dash:
        stream_id = dash[0].get("id")
        stream_format = dash[0].get("format", "DASH")

    if not stream_id:
        return {"subject_id": subject_id, "se": se, "ep": ep, "count": 0, "captions": []}

    cap_url = (
        f"{API_BASE}/subject/caption"
        f"?format={stream_format}&id={stream_id}&subjectId={subject_id}&detailPath={detail_path}"
    )
    try:
        data = await _make_request(cap_url)
        inner = data.get("data", {})
        captions = inner.get("captions", []) if isinstance(inner, dict) else inner
        return {"subject_id": subject_id, "se": se, "ep": ep, "count": len(captions), "captions": captions}
    except Exception:
        return {"subject_id": subject_id, "se": se, "ep": ep, "count": 0, "captions": []}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.index:app", host="0.0.0.0", port=8000, reload=True)
