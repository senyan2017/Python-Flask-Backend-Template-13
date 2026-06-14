# Development Guide

## Quick Start

```bash
cd backend/jobsearcher/api
pip install -r requirements.txt   # or: pip install --break-system-packages -r requirements.txt
python3 api.py
```

Server starts on `http://localhost:5000`.

---

## API Endpoints

### GET /retrieveJobs

Main job-search endpoint.

| Param      | Type   | Default | Description                          |
|------------|--------|---------|--------------------------------------|
| q          | string | ""      | Search keyword (e.g. "python")       |
| location   | string | ""      | Location filter (e.g. "remote")      |
| page       | int    | 1       | Page number                          |
| page_size  | int    | 20      | Items per page (max 100)             |
| source     | string | all     | Restrict to one source (e.g. "remotive") |

**Response:**

```json
{
  "jobs": [
    {
      "id": "...",
      "title": "Senior Python Developer",
      "company": "Acme Corp",
      "location": "Remote",
      "url": "https://...",
      "summary": "...",
      "source": "remotive",
      "posted_at": "2026-06-10T12:00:00",
      "salary": "$80k-$120k",
      "tags": ["python", "django"]
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "total_pages": 3,
  "query": "python",
  "location": "",
  "sources": ["remotive", "indeed"],
  "errors": {}
}
```

### GET /sources

Returns `{"sources": ["remotive", "indeed"]}`.

### GET /health

Returns `{"status": "ok"}`.

---

## Verification (curl)

```bash
# Health check
curl http://localhost:5000/health

# List available sources
curl http://localhost:5000/sources

# Search for Python jobs
curl "http://localhost:5000/retrieveJobs?q=python&page_size=5"

# Filter by location
curl "http://localhost:5000/retrieveJobs?q=developer&location=usa"

# Pagination
curl "http://localhost:5000/retrieveJobs?q=python&page=2&page_size=3"

# Only one source
curl "http://localhost:5000/retrieveJobs?source=remotive&page_size=10"

# Error case — unknown source
curl "http://localhost:5000/retrieveJobs?source=nonexistent"
```

---

## Architecture

```
api.py                  <- Flask routes & request parsing
indeedScraper.py        <- Backward-compatible facade (legacy import shim)
scrapers/
  base.py               <- BaseScraper ABC + Job dataclass
  remotive.py           <- Remotive.com API scraper (primary, most reliable)
  indeed.py             <- Indeed.com HTML scraper (best-effort, often blocked)
  registry.py           <- ScraperRegistry: aggregates & paginates across sources
  __init__.py           <- Package exports
```

### Adding a new job source

1. Create `scrapers/mysource.py`, subclass `BaseScraper`
2. Implement `extract(query, location, page)` and `transform(raw)`
3. Register in `api.py`: `registry.register(MySourceScraper())`

No changes needed in the API layer or other scrapers.

---

## Error Handling

- **Scraper failure**: Individual scraper errors are caught and logged; other sources still return data. The `errors` field in the response shows which sources failed and why.
- **All scrapers fail**: Returns HTTP 207 (Multi-Status) with `jobs: []` and error details.
- **Zero results (legitimate)**: Returns HTTP 200 with `jobs: []`.
- **Invalid source param**: Returns HTTP 400 with an error message.
- **Invalid page/page_size**: Silently clamped to valid range.
