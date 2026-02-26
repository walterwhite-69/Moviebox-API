import re
import json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from bs4 import BeautifulSoup

app = FastAPI(
    title="MovieBox API",
    description="Live REST API for moviebox.ph — scrapes all homepage sections with real poster URLs, badges, genres and more",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_URL = "https://moviebox.ph"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Referer": "https://moviebox.ph/",
}

async def fetch_page() -> tuple[BeautifulSoup, str]:
    return await fetch_tab("/")

async def fetch_tab(path: str) -> tuple[BeautifulSoup, str]:
    url = BASE_URL + path if path.startswith("/") else path
    headers = {**HEADERS, "Referer": url}
    async with httpx.AsyncClient(follow_redirects=True, timeout=25) as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(
                status_code=502,
                detail=f"Failed to fetch {url}: HTTP {response.status_code}"
            )
        return BeautifulSoup(response.text, "html.parser"), response.text

def build_blurhash_to_poster_map(raw_html: str) -> dict[str, str]:
    script_match = re.search(
        r'<script[^>]+id="__NUXT_DATA__"[^>]*>(.*?)</script>',
        raw_html, re.DOTALL
    )
    if not script_match:
        return {}

    try:
        data = json.loads(script_match.group(1))
    except (json.JSONDecodeError, Exception):
        return {}

    if not isinstance(data, list):
        return {}

    mapping: dict[str, str] = {}
    cdn_indices = [
        i for i, v in enumerate(data)
        if isinstance(v, str) and "pbcdnw.aoneroom.com" in v
    ]

    for idx in cdn_indices:
        url = data[idx]
        for offset in range(1, 12):
            for direction in (1, -1):
                neighbor_idx = idx + (direction * offset)
                if 0 <= neighbor_idx < len(data):
                    candidate = data[neighbor_idx]
                    if (
                        isinstance(candidate, str)
                        and 8 < len(candidate) < 90
                        and re.match(r'^[A-Za-z0-9$%^&*:;,|{}\[\]~\-=+.@#!?_()/<>\'` ]+$', candidate)
                        and not candidate.startswith("http")
                        and not candidate.startswith("/")
                        and "." not in candidate[:4]
                        and candidate not in mapping
                    ):
                        mapping[candidate] = url
                        break
    return mapping

def build_slug_to_poster_map(raw_html: str) -> dict[str, str]:
    script_match = re.search(
        r'<script[^>]+id="__NUXT_DATA__"[^>]*>(.*?)</script>',
        raw_html, re.DOTALL
    )
    if not script_match:
        return {}
    try:
        data = json.loads(script_match.group(1))
    except Exception:
        return {}
    if not isinstance(data, list):
        return {}

    mapping: dict[str, str] = {}
    slug_re = re.compile(r'^[a-z][a-z0-9\-]+-[a-zA-Z0-9]{11}$')

    for idx, v in enumerate(data):
        if not isinstance(v, str):
            continue
        if not slug_re.match(v) or '-' not in v:
            continue
        if v in mapping:
            continue

        for offset in range(1, 26):
            ni = idx - offset
            if ni < 0:
                break
            candidate = data[ni]
            if isinstance(candidate, str) and "pbcdnw.aoneroom.com" in candidate:
                mapping[v] = candidate
                break

    return mapping

def parse_movie_card(card, blurhash_map: dict) -> dict:
    href = card.get("href", "")
    title_attr = card.get("title", "")

    name_tag = card.find("p")
    if name_tag:
        name = name_tag.get_text(separator=" ", strip=True)
    elif title_attr:
        name = re.sub(r"^go to\s+", "", title_attr, flags=re.IGNORECASE)
        name = re.sub(r"\s+detail page$", "", name, flags=re.IGNORECASE)
    else:
        name = ""

    slug = href.split("/detail/")[-1] if "/detail/" in href else None

    thumb_span = card.find("span", attrs={"thumbnail": True})
    blurhash = thumb_span.get("thumbnail") if thumb_span else None
    poster_url = blurhash_map.get(blurhash) if blurhash else None

    badge_span = card.find("span", class_=lambda c: c and "text-white" in c if c else False)
    badge = badge_span.get_text(strip=True) if badge_span else None

    return {
        "name": name,
        "url": BASE_URL + href if href.startswith("/") else href,
        "slug": slug,
        "poster_url": poster_url,
        "badge": badge,
        "blurhash": blurhash,
    }

def parse_sections(soup: BeautifulSoup, blurhash_map: dict) -> list[dict]:
    sections = []
    seen_titles = set()

    for box in soup.find_all("div", class_="movie-card-list-box"):
        title_div = box.find("div", class_=lambda c: c and "title" in c.split() if c else False)
        if not title_div:
            continue

        raw_title = title_div.get_text(strip=True)
        if not raw_title or raw_title in seen_titles:
            continue
        seen_titles.add(raw_title)

        more_link = box.find("a", class_=lambda c: c and "action-bar" in c.split() if c else False)
        more_href = more_link.get("href") if more_link else None
        more_url = (BASE_URL + more_href if more_href and more_href.startswith("/") else more_href) if more_href else None

        movie_cards = box.find_all("a", class_="movie-card")
        if not movie_cards:
            continue

        movies = [parse_movie_card(card, blurhash_map) for card in movie_cards]

        sections.append({
            "section": raw_title,
            "more_url": more_url,
            "count": len(movies),
            "movies": movies,
        })

    return sections

def parse_card_page(soup: BeautifulSoup, slug_map: dict) -> list[dict]:
    cards = soup.find_all("a", class_="card",
                          href=lambda h: h and "/detail/" in h if h else False)
    movies = []
    for card in cards:
        href = card.get("href", "")
        slug = href.split("/detail/")[-1] if "/detail/" in href else None

        h2 = card.find("h2", class_=lambda c: c and "card-title" in c.split() if c else False)
        name = h2.get_text(strip=True) if h2 else (slug or "")

        year_div = card.find("div", class_=lambda c: c and "text-white" in c and "text-[12px]" in c if c else False)
        year = year_div.get_text(strip=True) if year_div else None

        rating_span = card.find("span")
        rating = rating_span.get_text(strip=True) if rating_span else None

        poster_url = slug_map.get(slug) if slug else None

        movies.append({
            "name": name,
            "url": BASE_URL + href if href.startswith("/") else href,
            "slug": slug,
            "poster_url": poster_url,
            "year": year,
            "rating": rating,
            "badge": None,
            "blurhash": None,
        })

    if not movies:
        return []
    return [{"section": "All", "more_url": None, "count": len(movies), "movies": movies}]

def parse_movie_filter_page(soup: BeautifulSoup, blurhash_map: dict, slug_map: dict, raw_html: str) -> list[dict]:
    all_cards = soup.find_all("a", href=lambda h: h and "/detail/" in h if h else False)
    movies = []
    seen_slugs: set = set()
    for card in all_cards:
        href = card.get("href", "")
        slug = href.split("/detail/")[-1] if "/detail/" in href else None
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        name_tag = card.find("p") or card.find(
            "h2", class_=lambda c: c and "card-title" in c if c else False
        )
        name = name_tag.get_text(strip=True) if name_tag else slug

        thumb = card.find("span", attrs={"thumbnail": True})
        blurhash = thumb.get("thumbnail") if thumb else None
        poster_url = blurhash_map.get(blurhash) if blurhash else None

        badge_span = card.find("span", class_=lambda c: c and "text-white" in c if c else False)
        badge = badge_span.get_text(strip=True) if badge_span else None

        movies.append({
            "name": name,
            "url": BASE_URL + href if href.startswith("/") else href,
            "slug": slug,
            "poster_url": poster_url,
            "badge": badge,
            "blurhash": blurhash,
        })
    if not movies:
        script_match = re.search(r'<script[^>]+id="__NUXT_DATA__"[^>]*>(.*?)</script>', raw_html, re.DOTALL)
        if script_match:
            try:
                data = json.loads(script_match.group(1))
                slugs_idx = [ (i, v) for i, v in enumerate(data) if isinstance(v, str) and '/detail/' not in v and re.match(r'^[a-z0-9][a-z0-9\-]{3,}-[a-zA-Z0-9]{11}$', v)]
                for idx, slug in slugs_idx:
                    if slug in seen_slugs:
                        continue
                    seen_slugs.add(slug)
                    
                    name = slug
                    for j in range(max(0, idx-10), min(len(data), idx+10)):
                        val = data[j]
                        if isinstance(val, str) and len(val) > 2 and not val.startswith('http') and not re.match(r'^[a-z0-9\-]+$', val):
                            name = val.replace("Trailer-", "").strip()
                            break
                            
                    movies.append({
                        "name": name,
                        "url": BASE_URL + f"/detail/{slug}",
                        "slug": slug,
                        "poster_url": slug_map.get(slug),
                        "badge": None,
                        "blurhash": None,
                    })
            except Exception:
                pass

    if not movies:
        return []
    return [{"section": "All Movies", "more_url": None, "count": len(movies), "movies": movies}]

def _resolve_nuxt_data(data, index):
    if not isinstance(index, int) or index < 0 or index >= len(data):
        return index 
    val = data[index]
    if isinstance(val, dict):
        return {k: _resolve_nuxt_data(data, v) for k, v in val.items()}
    elif isinstance(val, list):
        return [_resolve_nuxt_data(data, i) for i in val]
    else:
        return val

@app.get("/detail/{slug}")
async def get_movie_detail(slug: str):
    url = f"https://moviebox.ph/detail/{slug}"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=30)
        
    if resp.status_code != 200:
        raise HTTPException(status_code=404, detail="Movie not found")
        
    match = re.search(r'<script type="application/json" data-nuxt-data="nuxt-app" data-ssr="true" id="__NUXT_DATA__">\s*(.*?)\s*</script>', resp.text, re.DOTALL)
    if not match:
        raise HTTPException(status_code=500, detail="Could not find NUXT data in the page")
        
    try:
        nuxt_json = json.loads(match.group(1))
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse NUXT data")
        
    if not isinstance(nuxt_json, list):
        raise HTTPException(status_code=500, detail="Unexpected NUXT data format")
        
    movie_dict = None
    for i, v in enumerate(nuxt_json):
        if isinstance(v, dict) and 'subjectId' in v and 'title' in v and 'duration' in v:
            movie_dict = _resolve_nuxt_data(nuxt_json, i)
            break
            
    if not movie_dict:
        raise HTTPException(status_code=404, detail="Could not extract movie metadata from NUXT")

    stream_urls = [s for s in nuxt_json if isinstance(s, str) and '.mp4' in s]
    hls_urls = [s for s in nuxt_json if isinstance(s, str) and ('.m3u8' in s or '/m3u8/' in s)]

    return {
        "slug": slug,
        "source": url,
        "metadata": {
            "id": movie_dict.get("subjectId"),
            "title": movie_dict.get("title"),
            "description": movie_dict.get("description"),
            "release_date": movie_dict.get("releaseDate"),
            "duration": movie_dict.get("duration"),
            "genre": movie_dict.get("genre"),
            "country": movie_dict.get("countryName"),
            "imdb_rating": movie_dict.get("imdbRatingValue"),
            "poster": movie_dict.get("cover", {}).get("url") if isinstance(movie_dict.get("cover"), dict) else None,
            "badge": movie_dict.get("corner"),
            "dubs": movie_dict.get("dubs", [])
        },
        "streams": {
            "mp4": stream_urls,
            "hls": hls_urls
        }
    }

def parse_ranking_page(soup: BeautifulSoup, slug_map: dict) -> list[dict]:
    rank_lists = soup.find_all("div", class_=lambda c: c and "rank-subject-list" in c if c else False)

    all_movies = []
    seen_slugs: set = set()
    for rl in rank_lists:
        cards = rl.find_all("a", class_=lambda c: c and "rank-subject-item" in c if c else False)
        for card in cards:
            href = card.get("href", "")
            slug = href.split("/detail/")[-1] if "/detail/" in href else None
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            title_div = card.find("div", class_="title-text")
            name = title_div.get_text(strip=True) if title_div else (slug or "")

            rank_num_div = card.find("div", class_="ranking-corner-num")
            rank = rank_num_div.get_text(strip=True) if rank_num_div else None

            badge_span = card.find("span", class_="special-tag-text")
            badge = badge_span.get_text(strip=True) if badge_span else None

            poster_url = slug_map.get(slug) if slug else None

            all_movies.append({
                "name": name,
                "url": BASE_URL + href if href.startswith("/") else href,
                "slug": slug,
                "rank": rank,
                "poster_url": poster_url,
                "badge": badge,
            })

    if not all_movies:
        return []
    return [{"section": "Most Watched", "more_url": None, "count": len(all_movies), "movies": all_movies}]

def build_title_to_poster_map(raw_html: str) -> dict[str, str]:
    script_match = re.search(
        r'<script[^>]+id="__NUXT_DATA__"[^>]*>(.*?)</script>',
        raw_html, re.DOTALL
    )
    if not script_match:
        return {}
    try:
        data = json.loads(script_match.group(1))
    except Exception:
        return {}
    if not isinstance(data, list):
        return {}

    mapping: dict[str, str] = {}
    for idx, v in enumerate(data):
        if not isinstance(v, str) or len(v) < 2 or len(v) > 120:
            continue
        if "pbcdnw.aoneroom.com" not in v:
            continue
        for offset in range(1, 51):
            ni = idx + offset
            if ni >= len(data):
                break
            candidate = data[ni]
            if (
                isinstance(candidate, str)
                and 2 < len(candidate) < 100
                and " " in candidate
                and not candidate.startswith("http")
                and not re.match(r'^[a-z0-9\-]+$', candidate)
                and not re.match(r'^\d{4}', candidate)
                and candidate not in mapping
            ):
                mapping[candidate] = v
                break
    return mapping

def parse_banner(soup: BeautifulSoup, title_map: dict) -> list[dict]:
    featured = []
    seen = set()

    for name_div in soup.find_all("div", class_=lambda c: c and "work-name" in c if c else False):
        name = name_div.get_text(separator=" ", strip=True)
        name = re.sub(r'\s+', ' ', name).strip()
        if not name or len(name) < 2 or "MovieBox Communities" in name or name in seen:
            continue
        seen.add(name)

        parent = name_div.parent
        year_div = parent.find("div", class_=lambda c: c and "year" in c if c else False) if parent else None
        genre_div = parent.find("div", class_=lambda c: c and "type" in c if c else False) if parent else None

        name_clean = re.sub(r'\[.*?\]', '', name).strip().lower()
        
        poster_url = None
        for key, url in title_map.items():
            key_clean = re.sub(r'\[.*?\]', '', key).strip().lower()
            if name_clean == key_clean:
                poster_url = url
                break
                
        if not poster_url and len(name_clean) > 3:
            for key, url in title_map.items():
                key_clean = re.sub(r'\[.*?\]', '', key).strip().lower()
                if name_clean in key_clean or key_clean in name_clean:
                    poster_url = url
                    break
            
            if not poster_url:
                words_name = name_clean.split()
                if len(words_name) >= 2:
                    for key, url in title_map.items():
                        key_clean = re.sub(r'\[.*?\]', '', key).strip().lower()
                        words_key = key_clean.split()
                        if len(words_key) >= 2 and words_name[0] == words_key[0] and words_name[1] == words_key[1]:
                            poster_url = url
                            break

        featured.append({
            "name": name,
            "year": year_div.get_text(strip=True) if year_div else None,
            "genres": genre_div.get_text(strip=True).split(",") if genre_div and genre_div.get_text(strip=True) else [],
            "poster_url": poster_url,
        })
    return featured

@app.get("/")
def list_endpoints():
    return {
        "api": "MovieBox API",
        "version": "3.1.0",
        "docs": "/docs",
        "endpoints": {
            "home": {
                "/home": "Get home page data (banners and sections)",
                "/home/sections": "Get only the names of available sections on the home page",
                "/home/section/{name}": "Get a specific section by name from the home page"
            },
            "movies": {
                "/movies": "Get all movies from filter page",
                "/movies/sections": "List all available movie sections",
                "/movies/section/{name}": "Get a specific movie section by name",
                "/search/suggest": "Get keyword autocomplete suggestions (e.g. ?q=avatar)",
                "/search": "Search for movies (e.g. ?q=avatar)",
                "/detail/{slug}": "Get movie/show details and stream URLs (e.g. tokyo-ghoul-hindi-OlanoKZKGR2)"
            },
            "tv_series": {
                "/tv-series": "Get all TV series from filter page",
                "/tv-series/sections": "List all available TV series sections",
                "/tv-series/section/{name}": "Get a specific TV series section by name"
            },
            "animation": {
                "/animation": "Get all animations from filter page",
                "/animation/sections": "List all available animation sections",
                "/animation/section/{name}": "Get a specific animation section by name"
            },
            "ranking": {
                "/ranking": "Get all ranking lists",
                "/ranking/sections": "List all available ranking sections",
                "/ranking/section/{name}": "Get a specific ranking section by name"
            }
        }
    }

@app.get("/home")
async def get_home():
    url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/home?host=moviebox.ph"
    headers = {"User-Agent": "Mozilla/5.0"}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=30)
    
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Failed to fetch backend API")
        
    data = resp.json().get("data", {})
    ops = data.get("operatingList", [])
    
    sections = []
    map_size = 0 
    
    for op in ops:
        title = op.get("title", "")
        
        if op.get("banner"):
            banner_items = []
            for item in op["banner"].get("items", []):
                name = item.get("title")
                if "Communities" in name or not name: continue
                
                poster = item.get("image", {}).get("url")
                if not poster and item.get("subject"):
                    poster = item["subject"].get("cover", {}).get("url")
                
                detail_path = item.get("detailPath")
                badge = None
                if item.get("subject"):
                    badge = item["subject"].get("corner") 
                
                banner_items.append({
                    "name": name,
                    "poster_url": poster,
                    "url": BASE_URL + f"/detail/{detail_path}" if detail_path else None,
                    "badge": badge,
                    "slug": detail_path
                })
            sections.append({
                "section": "Banner",
                "count": len(banner_items),
                "movies": banner_items,
                "more_url": None
            })
            continue

        subs = op.get("subjects", [])
        if not subs or not title: continue
        
        movies = []
        for sub in subs:
            name = sub.get("title") or sub.get("name")
            poster = sub.get("cover", {}).get("url") or sub.get("thumbnail")
            detail_path = sub.get("detailPath")
            
            movies.append({
                "name": name,
                "poster_url": poster,
                "url": BASE_URL + f"/detail/{detail_path}" if detail_path else None,
                "slug": detail_path,
                "badge": sub.get("corner"),
                "blurhash": sub.get("cover", {}).get("blurHash")
            })
            
        sections.append({
            "section": title,
            "count": len(movies),
            "movies": movies,
            "more_url": None
        })

    return {
        "source": url,
        "total_sections": len(sections),
        "poster_map_size": map_size,
        "sections": sections,
    }

@app.get("/home/sections")
async def get_section_names():
    home_data = await get_home()
    sections = home_data["sections"]
    return {
        "total": len(sections),
        "sections": [
            {"name": s["section"], "count": s["count"], "more_url": s["more_url"]}
            for s in sections
        ]
    }

@app.get("/home/banner")
async def get_banner():
    home_data = await get_home()
    for s in home_data["sections"]:
        if s["section"] == "Banner":
            return {"count": s["count"], "featured": s["movies"]}
    return {"count": 0, "featured": []}

@app.get("/home/trending")
async def get_trending():
    home_data = await get_home()
    for s in home_data["sections"]:
        if "trending now" in s["section"].lower():
            return s
    raise HTTPException(status_code=404, detail="Trending Now section not found")

@app.get("/home/hot")
async def get_hot():
    home_data = await get_home()
    for s in home_data["sections"]:
        if "hot" in s["section"].lower():
            return s
    raise HTTPException(status_code=404, detail="Hot section not found")

@app.get("/home/cinema")
async def get_cinema():
    home_data = await get_home()
    for s in home_data["sections"]:
        if "cinema" in s["section"].lower():
            return s
    raise HTTPException(status_code=404, detail="Cinema section not found")

@app.get("/home/section/{name}")
async def get_section_by_name(name: str):
    home_data = await get_home()
    sections = home_data["sections"]
    matched = [s for s in sections if name.lower() in s["section"].lower()]
    if not matched:
        raise HTTPException(
            status_code=404,
            detail={
                "message": f"No section matching '{name}'",
                "available": [s["section"] for s in sections]
            }
        )
    return {"results": matched}

async def _tab_sections(path: str) -> tuple[list, int]:
    soup, raw = await fetch_tab(path)
    bmap = build_blurhash_to_poster_map(raw)
    smap = build_slug_to_poster_map(raw)

    if soup.find("a", class_="card",
                 href=lambda h: h and "/detail/" in h if h else False) or "tv-series" in path or "animation" in path:
        sections = parse_card_page(soup, smap)
    elif soup.find("a", class_=lambda c: c and "rank-subject-item" in c if c else False) or "ranking" in path:
        sections = parse_ranking_page(soup, smap)
    elif soup.find("div", class_=lambda c: c and "filter-name" in " ".join(c) if c else False) or "movie" in path:
        sections = parse_movie_filter_page(soup, bmap, smap, raw)
    else:
        sections = parse_sections(soup, bmap)

    return sections, len(bmap)

@app.get("/tv-series")
async def get_tv_series():
    sections, map_size = await _tab_sections("/web/tv-series")
    return {
        "source": BASE_URL + "/web/tv-series",
        "total_sections": len(sections),
        "poster_map_size": map_size,
        "sections": sections,
    }

@app.get("/tv-series/section/{name}")
async def get_tv_series_section(name: str):
    sections, _ = await _tab_sections("/web/tv-series")
    matched = [s for s in sections if name.lower() in s["section"].lower()]
    if not matched:
        raise HTTPException(
            status_code=404,
            detail={"message": f"No section matching '{name}'",
                    "available": [s["section"] for s in sections]}
        )
    return {"results": matched}

@app.get("/movies")
async def get_movies():
    sections, map_size = await _tab_sections("/web/movie")
    return {
        "source": BASE_URL + "/web/movie",
        "total_sections": len(sections),
        "poster_map_size": map_size,
        "sections": sections,
    }

@app.get("/movies/section/{name}")
async def get_movies_section(name: str):
    sections, _ = await _tab_sections("/web/movie")
    matched = [s for s in sections if name.lower() in s["section"].lower()]
    if not matched:
        raise HTTPException(
            status_code=404,
            detail={"message": f"No section matching '{name}'",
                    "available": [s["section"] for s in sections]}
        )
    return {"results": matched}

@app.get("/animation")
async def get_animation():
    sections, map_size = await _tab_sections("/web/animated-series")
    return {
        "source": BASE_URL + "/web/animated-series",
        "total_sections": len(sections),
        "poster_map_size": map_size,
        "sections": sections,
    }

@app.get("/animation/section/{name}")
async def get_animation_section(name: str):
    sections, _ = await _tab_sections("/web/animated-series")
    matched = [s for s in sections if name.lower() in s["section"].lower()]
    if not matched:
        raise HTTPException(
            status_code=404,
            detail={"message": f"No section matching '{name}'",
                    "available": [s["section"] for s in sections]}
        )
    return {"results": matched}

@app.get("/ranking")
async def get_ranking():
    sections, map_size = await _tab_sections("/ranking-list")
    return {
        "source": BASE_URL + "/ranking-list",
        "total_sections": len(sections),
        "poster_map_size": map_size,
        "sections": sections,
    }

@app.get("/search/suggest")
async def get_search_suggestions(q: str):
    url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/subject/search-suggest"
    payload = {"keyword": q, "perPage": 10}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, timeout=10)
        
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Search API failed")
        
    data = resp.json()
    items = data.get("data", {}).get("items", [])
    suggestions = [item.get("word") for item in items if item.get("word")]
    return {"query": q, "suggestions": suggestions}

@app.get("/search")
async def get_search_results(q: str):
    url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/subject/search"
    payload = {"keyword": q, "perPage": 30, "page": 1}
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json"
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, headers=headers, timeout=15)
        
    if resp.status_code != 200:
        raise HTTPException(status_code=500, detail="Search API failed")
        
    data = resp.json()
    items = data.get("data", {}).get("items", [])
    
    movies = []
    for sub in items:
        name = sub.get("title")
        poster = sub.get("cover", {}).get("url")
        detail_path = sub.get("detailPath")
        
        movies.append({
            "name": name,
            "poster_url": poster,
            "url": BASE_URL + f"/detail/{detail_path}" if detail_path else None,
            "slug": detail_path,
            "badge": sub.get("corner"),
            "blurhash": sub.get("cover", {}).get("blurHash")
        })
        
    return {
        "query": q,
        "count": len(movies),
        "movies": movies
    }

@app.get("/ranking/section/{name}")
async def get_ranking_section(name: str):
    sections, _ = await _tab_sections("/ranking-list")
    matched = [s for s in sections if name.lower() in s["section"].lower()]
    if not matched:
        raise HTTPException(
            status_code=404,
            detail={"message": f"No section matching '{name}'",
                    "available": [s["section"] for s in sections]}
        )
    return {"results": matched}

@app.get("/api/stream/{subject_id}")
async def get_stream_sources(subject_id: str, detail_path: str, se: int = 0, ep: int = 0):
    domain_url = "https://h5-api.aoneroom.com/wefeed-h5api-bff/media-player/get-domain"
    domain = "https://123movienow.cc" 
    
    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Client-Info": '{"timezone":"Asia/Dhaka"}',
        "X-Client-Type": "h5",
        "X-App-Version": "1.0.0"
    }

    async with httpx.AsyncClient() as client:
        try:
            r_dom = await client.get(domain_url, headers=headers, timeout=5)
            if r_dom.status_code == 200:
                dom_data = r_dom.json()
                domain = dom_data.get("data", domain)
                if domain.endswith("/"):
                    domain = domain[:-1]
        except Exception as e:
            print(f"Warning: Failed to fetch player domain, using fallback: {e}")
            pass
            
        play_url = f"{domain}/wefeed-h5api-bff/subject/play?subjectId={subject_id}&se={se}&ep={ep}&detailPath={detail_path}"
        
        play_headers = {
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.9',
            'referer': f'{domain}/spa/videoPlayPage/movies/{detail_path}?id={subject_id}&type=/movie/detail&detailSe=&detailEp=&lang=en',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'x-client-info': '{"timezone":"Asia/Dhaka"}',
            'x-source': ''
        }
        
        cookies = {
            "uuid": "d8c3539e-2e46-4000-af20-7046a856e30a" 
        }

        resp = await client.get(play_url, headers=play_headers, cookies=cookies, timeout=15)
        
        if resp.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Player API returned {resp.status_code}")
            
        data = resp.json()
        streams = data.get("data", {}).get("streams", [])
        
        if not streams:
            raise HTTPException(status_code=404, detail="No streams found or hasResource is False.")
            
        formatted_streams = []
        for s in streams:
            formatted_streams.append({
                "resolution": s.get("resolutions") + "p" if s.get("resolutions") else "Unknown",
                "format": s.get("format"),
                "url": s.get("url"),
                "size_bytes": s.get("size"),
                "id": s.get("id")
            })
            
        try:
            formatted_streams.sort(key=lambda x: int(x["resolution"].replace("p", "")), reverse=True)
        except:
             pass

        return {
            "subject_id": subject_id,
            "detail_path": detail_path,
            "season": se,
            "episode": ep,
            "stream_domain": domain,
            "count": len(formatted_streams),
            "sources": formatted_streams,
            "raw": data.get("data", {})
        }