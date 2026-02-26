<p align="center">
  <img src="https://h5-static.aoneroom.com/ssrStatic/mbOfficial/public/_nuxt/web-logo.apJjVir2.svg" alt="LOGO" width="200"/>
</p>

# 🎬 MovieBox API (v1.0.0)

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Live-4c1?style=for-the-badge)](https://moviebox.ph)
[![License](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

> **The ultimate REST API for MovieBox.ph.** 🚀 Optimized for high-speed metadata scraping, real-time stream extraction, and seamless frontend integration.

---

## ✨ Features

- **🏠 Comprehensive Homepage**: Instant access to Banners, Trending Now, Hot, Cinema, and custom Operating categories.
- **🔍 Advanced Search**: Real-time keyword suggestions and full-text search results.
- **📱 Tabbed Navigation**: Fully functional endpoints for Movies, TV Series, Animation, and Rankings.
- **🗃️ Deep Metadata**: Extraction of IMDb ratings, release dates, high-res posters, genres, and dub/sub lists.
- **▶️ Direct Streaming**: Direct `.mp4` and HLS stream retrieval with automatic server discovery and Cloudflare bypass.
- **⚡ High Performance**: Built with FastAPI and Httpx for asynchronous, non-blocking requests.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **Networking**: Httpx (Async HTTP Client)
- **Parsing**: BeautifulSoup4 & Regex (NUXT_DATA Parsing)
- **Deployment**: Uvicorn

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9 or higher
- `pip` (Python package installer)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/walterwhite-69/Moviebox-API.git
   cd Moviebox-API
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *Note: If requirements.txt is missing, install manually:*
   `pip install fastapi uvicorn httpx beautifulsoup4`

3. **Start the server**:
   ```bash
   uvicorn api:app --host 0.0.0.0 --port 8000 --reload
   ```

---

## 📡 API Endpoints

### 🏠 Home
| Endpoint | Description |
| :--- | :--- |
| `GET /home` | Full homepage data including banners and all sections. |
| `GET /home/banner` | Return only active featured banner items. |
| `GET /home/sections` | List all available section names and movie counts. |
| `GET /home/trending` | Get "Trending Now" specific items. |

### 🎬 Movies & TV
| Endpoint | Description |
| :--- | :--- |
| `GET /movies` | Fetch the full movie filter page. |
| `GET /tv-series` | Fetch the full TV series catalog. |
| `GET /animation` | Fetch animated series and anime. |
| `GET /ranking` | Get most-watched and top-rated rankings. |

### 🔍 Search & Details
| Endpoint | Description |
| :--- | :--- |
| `GET /search?q={query}` | Search for any title. |
| `GET /search/suggest?q={query}` | Get autocomplete suggestions. |
| `GET /detail/{slug}` | Get full metadata and available stream links. |
| `GET /api/stream/{id}?detail_path={slug}` | **Raw Stream URL Discovery**. |

---

## 🏎️ Performance Verification

Run the built-in verification suite to ensure all endpoints are pointing to the live backend correctly:

```bash
python verify.py
```

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/walterwhite-69/Moviebox-API/issues).

## 📜 License

Distributed under the **MIT License**. See `LICENSE` for more information.

---

<p align="center">
  Made by walter for the Streaming Community
</p>
