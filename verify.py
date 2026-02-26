import httpx, json

BASE = "http://localhost:8000"

ENDPOINTS = [
    "/",
    "/home",
    "/home/trending",
    "/home/hot",
    "/home/cinema",
    "/home/banner",
    "/home/sections",
    "/tv-series",
    "/movies",
    "/animation",
    "/ranking",
]

def check_movies(movies, label):
    total = len(movies)
    with_poster = sum(1 for m in movies if m.get("poster_url"))
    with_name = sum(1 for m in movies if m.get("name"))
    print(f"    movies: {total} | names: {with_name}/{total} | posters: {with_poster}/{total}")
    if movies:
        m = movies[0]
        print(f"    sample: name={m.get('name','?')[:40]!r} | poster={'YES' if m.get('poster_url') else 'NULL'}")

for path in ENDPOINTS:
    url = BASE + path
    try:
        r = httpx.get(url, timeout=30)
        data = r.json()
        status = "OK" if r.status_code == 200 else f"ERR {r.status_code}"
        print(f"\n[{status}] {path}")

        # Root
        if path == "/":
            print(f"  endpoints listed: {len(data.get('endpoints', []))}")
            continue

        # Banner
        if path == "/home/banner":
            featured = data.get("featured", [])
            print(f"  featured: {len(featured)}")
            if featured:
                f = featured[0]
                print(f"  sample: name={f.get('name','?')[:40]!r} | poster={'YES' if f.get('poster_url') else 'NULL'}")
            continue

        # Sections list
        if path == "/home/sections":
            secs = data.get("sections", [])
            print(f"  sections: {len(secs)}")
            for s in secs:
                print(f"    - {s['name']!r} ({s['count']} movies)")
            continue

        # Single section (trending/hot/cinema)
        if "movies" in data:
            print(f"  section: {data.get('section','?')!r}")
            check_movies(data["movies"], path)
            continue

        # Multi-section pages (/home, /tv-series, etc.)
        sections = data.get("sections", [])
        print(f"  total_sections: {len(sections)} | poster_map_size: {data.get('poster_map_size', '?')}")
        for s in sections:
            print(f"  [{s['section']!r}] {s['count']} movies")
            check_movies(s.get("movies", []), s["section"])

    except Exception as e:
        print(f"\n[FAIL] {path} => {e}")

print("\n\nDone.")
