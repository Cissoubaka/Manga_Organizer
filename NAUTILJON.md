# 🌊 Nautiljon Integration Guide

## Overview

Nautiljon integration allows your Manga Organizer to automatically fetch detailed manga information including:
- Total number of volumes (worldwide)
- French volumes count
- French publisher
- Mangaka/Author
- Series status (ongoing/completed)
- Publication years
- Direct links to Nautiljon pages

## Features

### 1. **Automatic Enrichment During Scan** ✨
When scanning a library, you can automatically enrich all detected series with Nautiljon data.

```
POST /api/scan/<library_id>
{
    "auto_enrich": true
}
```

### 2. **Manual Series Enrichment** 🔍
Enrich a specific series manually:

```
POST /api/nautiljon/enrich/<series_id>
{
    "search_by": "title",  // or "url"
    "value": "Manga Title"  // or Nautiljon URL
}
```

### 3. **Search Nautiljon** 🔎
Search for a manga on Nautiljon:

```
GET /api/nautiljon/search?q=manga_title

Response:
{
    "success": true,
    "results": [
        {
            "title": "Manga Title",
            "url": "https://www.nautiljon.com/manga/xxxxx"
        }
    ]
}
```

### 4. **Get Manga Info** 📖
Fetch detailed info for a manga:

```
GET /api/nautiljon/info?url=nautiljon_url
or
GET /api/nautiljon/info?title=manga_title

Response:
{
    "success": true,
    "info": {
        "title": "Manga Title",
        "url": "https://www.nautiljon.com/manga/xxxxx",
        "total_volumes": 45,
        "french_volumes": 38,
        "editor": "Glénat",
        "status": "En cours",
        "mangaka": "Author Name",
        "year_start": 2010,
        "year_end": null
    }
}
```

### 5. **View Series with Nautiljon Data** 📊
Get complete series details including Nautiljon info:

```
GET /api/series/<series_id>

Response includes:
{
    "id": 1,
    "title": "Manga Title",
    "nautiljon": {
        "url": "...",
        "total_volumes": 45,
        "french_volumes": 38,
        "editor": "Glénat",
        "status": "En cours",
        "mangaka": "Author Name",
        "year_start": 2010,
        "year_end": null,
        "updated_at": "2026-02-16..."
    },
    "volumes": [...]
}
```

### 6. **Batch Enrichment** ⚡
Enrich multiple series at once:

```
POST /api/nautiljon/batch-enrich
{
    "series_ids": [1, 2, 3, 4, 5],
    "search_by": "title"
}

Response:
{
    "success": true,
    "total": 5,
    "succeeded": 4,
    "failed": 1,
    "results": {
        "success": [...],
        "failed": [...]
    }
}
```

## Database Schema

New columns added to `series` table:

```sql
- nautiljon_url (TEXT)
- nautiljon_total_volumes (INTEGER)
- nautiljon_french_volumes (INTEGER)
- nautiljon_editor (TEXT)
- nautiljon_status (TEXT)
- nautiljon_mangaka (TEXT)
- nautiljon_year_start (INTEGER)
- nautiljon_year_end (INTEGER)
- nautiljon_updated_at (TIMESTAMP)
```

These columns are automatically created when the library scanner initializes.

## Implementation Details

### Scanner Enhancement

The `LibraryScanner` class in `blueprints/library/scanner.py` includes:

```python
def scan_directory(self, library_id, library_path, auto_enrich=False):
    """
    library_id: ID of the library to scan
    library_path: Path to the library directory
    auto_enrich: If True, enriches detected series with Nautiljon data
    """
```

### Nautiljon Scraper

Located at `blueprints/nautiljon/scraper.py`, the `NautiljonScraper` class provides:

- `search_manga(title)` - Search for a manga by title
- `get_manga_info(url_or_title)` - Fetch detailed manga information
- `search_and_get_best_match(title)` - Search and return best result
- Built-in caching to minimize requests

### Routes

New API routes in `blueprints/nautiljon/routes.py`:

- `GET /api/nautiljon/search` - Search manga
- `GET /api/nautiljon/info` - Get manga details
- `POST /api/nautiljon/enrich/<series_id>` - Enrich a series
- `GET /api/nautiljon/series/<series_id>` - Get series data with Nautiljon info
- `POST /api/nautiljon/batch-enrich` - Batch enrich multiple series

## Usage Examples

### Example 1: Scan with Automatic Enrichment

```bash
curl -X POST http://localhost:5000/api/scan/1 \
  -H "Content-Type: application/json" \
  -d '{"auto_enrich": true}'
```

### Example 2: Manually Enrich a Series

```bash
curl -X POST http://localhost:5000/api/nautiljon/enrich/1 \
  -H "Content-Type: application/json" \
  -d '{
    "search_by": "title",
    "value": "One Piece"
  }'
```

### Example 3: Enrich All Series in a Library

```bash
# First get all series
curl http://localhost:5000/api/library/1/series

# Then batch enrich them
curl -X POST http://localhost:5000/api/nautiljon/batch-enrich \
  -H "Content-Type: application/json" \
  -d '{
    "series_ids": [1, 2, 3, 4, 5],
    "search_by": "title"
  }'
```

## Frontend Integration

To integrate Nautiljon into the UI, you would typically:

1. **Add a search modal** to search Nautiljon directly
2. **Show Nautiljon data** in series detail pages
3. **Add enrichment button** during import or in series management
4. **Display info cards** with volume counts, publisher, etc.

Example UI elements:

```html
<!-- Series details with Nautiljon info -->
<div class="nautiljon-info">
    <h3>Publication Info</h3>
    <p>Total Volumes: {{ series.nautiljon.total_volumes }}</p>
    <p>French Volumes: {{ series.nautiljon.french_volumes }}</p>
    <p>Editor: {{ series.nautiljon.editor }}</p>
    <p>Status: {{ series.nautiljon.status }}</p>
    <p>Mangaka: {{ series.nautiljon.mangaka }}</p>
    <a href="{{ series.nautiljon.url }}" target="_blank">View on Nautiljon</a>
</div>

<!-- Enrichment button -->
<button onclick="enrichWithNautiljon({{ series.id }})">
    Enrich with Nautiljon Data
</button>
```

## Performance Considerations

- **Caching**: Scraper caches results to minimize requests
- **Rate Limiting**: Respectful delays between requests
- **Async Processing**: For batch operations, consider async processing
- **Error Handling**: Graceful fallbacks if Nautiljon is unavailable

## Troubleshooting

### "Manga not found on Nautiljon"
- Check the series title matches what's on Nautiljon
- Try searching manually on nautiljon.com to verify it exists
- The search algorithm is fuzzy, so slight variations may not match

### Missing Nautiljon Data
- Some manga may not have complete info on Nautiljon
- Not all fields are guaranteed to be populated
- Check the `nautiljon_url` to manually verify on Nautiljon

### Slow Enrichment
- Initial lookups are slower as results aren't cached
- Subsequent requests for the same series will be faster
- Batch enrichment may take time for large series counts

## Future Improvements

Potential enhancements:

1. **Web UI Integration**
   - Add Nautiljon search panel to settings
   - Show enrichment progress during batch operations
   - Display Nautiljon info in series list with status indicators

2. **Advanced Matching**
   - Fuzzy title matching algorithm
   - Alternative title fallbacks
   - Manual URL mapping for difficult cases

3. **Periodic Updates**
   - Automatic refresh of Nautiljon data periodically
   - Notifications for series status changes
   - Volume count updates

4. **Export Features**
   - Export series data to CSV with Nautiljon info
   - Sync with external databases

---

**Author**: GitHub Copilot  
**Date**: February 16, 2026  
**Version**: 1.0
