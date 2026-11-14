# MovieBox REST API (v2.0.0)

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-1080p_Active-brightgreen?style=flat-square)](https://moviebox.ph)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](https://opensource.org/licenses/MIT)

> It doesnt work properly, Moviebox blocking the bypass


REST API for MovieBox with 1080p stream extraction, adaptive DASH manifests, multi-language subtitle parsing, and an embedded web dashboard.

---

## Features

- **1080p Stream Extraction**: Direct MP4 streams up to 1080p resolution and DASH manifests.
- **Signed Policy Decoder**: Decodes signed Edge-Cache-Cookie and CloudFront-Policy tokens.
- **Subtitles**: Multi-language SRT and VTT caption tracks with authenticated CDN URLs.
- **Search & Autocomplete**: Keyword search with suggestions and full metadata.
- **TV Series & Movies**: Deep metadata, seasons, episode breakdowns, and audio dub lists.
- **Dashboard**: Embedded web UI at root (`/`) for testing streams, watching in-browser, and opening raw JSON endpoints.

---

## Tech Stack

- **Framework**: FastAPI
- **Networking**: `curl_cffi` (TLS/JA3 fingerprint impersonation) with `httpx` fallback
- **Server**: Uvicorn

---

## Getting Started

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/walterwhite-69/Moviebox-API.git
   cd Moviebox-API
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Start the server:
   ```bash
   uvicorn api:app --host 0.0.0.0 --port 8000 --reload
   ```

4. Open `http://localhost:8000` in your browser.

---

## Workflow & Examples

### 1. Movie Stream Flow

Movies only require the `subject_id`:

1. **Search Title**:
   ```http
   GET /search?q=Avatar
   ```
2. **Resolve 1080p Streams**:
   ```http
   GET /api/stream/8906247916759695608
   ```
3. **Fetch Subtitles**:
   ```http
   GET /api/stream/8906247916759695608/captions
   ```

---

### 2. TV Series Episode Stream Flow

TV series require checking available seasons and episodes first, then querying with `se` (season) and `ep` (episode) query parameters:

1. **Search Series**:
   ```http
   GET /search?q=Breaking+Bad
   ```
2. **Retrieve Season & Episode Breakdown**:
   ```http
   GET /episodes/6207982430134357800
   ```
   *Response:*
   ```json
   {
     "subject_id": "6207982430134357800",
     "seasons": [
       {"season": 1, "episode_count": 7},
       {"season": 2, "episode_count": 13},
       {"season": 3, "episode_count": 13},
       {"season": 4, "episode_count": 13},
       {"season": 5, "episode_count": 16}
     ]
   }
   ```
3. **Resolve Streams for a Specific Episode** (e.g. Season 1, Episode 1):
   ```http
   GET /api/stream/6207982430134357800?se=1&ep=1
   ```
   *Querying Season 1, Episode 2:*
   ```http
   GET /api/stream/6207982430134357800?se=1&ep=2
   ```
4. **Fetch Subtitles for that Episode**:
   ```http
   GET /api/stream/6207982430134357800/captions?se=1&ep=1
   ```

---

## Endpoints Summary

### Streams & Subtitles
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/stream/{subject_id}` | `GET` | Resolves 1080p, 720p, 480p, 360p MP4 & DASH streams. Query params: `se` (season, default 0), `ep` (episode, default 0), `detail_path`. |
| `/api/stream/{subject_id}/captions` | `GET` | Subtitle tracks (.srt/.vtt) with signed URLs. Query params: `se`, `ep`, `stream_id`. |

### Search & Details
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/search?q={query}&page=1` | `GET` | Search titles with release year, ratings, and posters. |
| `/search/suggest?q={query}` | `GET` | Search autocomplete suggestions. |
| `/detail/{subject_id}` | `GET` | Title metadata, genres, audio dubs, and plot summary. |
| `/episodes/{subject_id}` | `GET` | Season breakdown and episode counts for TV Series. |

### Catalog & Discovery
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/movies?page=1` | `GET` | Filtered movies catalog. |
| `/tv-series?page=1` | `GET` | Filtered TV series catalog. |
| `/home` | `GET` | Featured banners, trending titles, and section feeds. |

---

## License

Distributed under the MIT License. See `LICENSE` for details.
