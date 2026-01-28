<img width="698" height="698" alt="ocr-icon" src="https://github.com/user-attachments/assets/b2a15987-44f3-4a1a-938a-d53a33c0860f" />
# Screenshot Search

A Windows desktop app that uses OCR to extract text from your screenshots, making them searchable by content.

![Screenshot Search](https://via.placeholder.com/800x500?text=Screenshot+Search+App)

## Features

- **Full-text search** - Find screenshots by the text they contain
- **OCR indexing** - Extracts text from images using Tesseract OCR
- **Preview pane** - View screenshots and their extracted text without leaving the app
- **Date filtering** - Filter results by Today, Last 7 Days, Last 30 Days, or Last Year
- **Folder filtering** - Filter by subfolder (great for organized screenshot folders)
- **Copy text** - Copy extracted text to clipboard with one click
- **Fast search** - Uses SQLite FTS5 for instant full-text search

## Requirements

- Windows 10/11
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (required for text extraction)

## Installation

### Step 1: Install Tesseract OCR (Required)

Download and install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki

During installation, use the default path or add your custom path to the system PATH.

### Step 2: Get Screenshot Search

**Option A: Download the executable (Recommended)**

1. Go to [Releases](https://github.com/yourusername/screenshot-search/releases)
2. Download `ScreenshotSearch.exe`
3. Run it - no Python required!

**Option B: Run from source**

Requires Python 3.10+

```bash
git clone https://github.com/yourusername/screenshot-search.git
cd screenshot-search
pip install -r requirements.txt
python main.py
```

## First-Time Setup

On first launch, the app will ask you to select your screenshots folder. This is where your screenshot tool (ShareX, Snipping Tool, etc.) saves images.

You can change this later via the **Settings** button.

## Usage

1. Click **Scan Now** to index your screenshots (this may take a while for large collections)
2. Type a search term and press Enter or click **Search**
3. Click a thumbnail to preview it
4. Double-click a thumbnail to open the full image
5. Use **Copy Text** to copy the extracted text to clipboard

## Tips

- The app skips already-indexed screenshots, so re-scanning is fast
- Screenshots with no detectable text are still indexed (so they won't be re-scanned)
- Use the date and folder filters to narrow down results
- The search uses full-text search, so partial words work (e.g., "config" matches "configuration")

## File Structure

```
screenshot-search/
├── main.py           # GUI application
├── database.py       # SQLite database operations
├── scanner.py        # Folder scanning and indexing
├── ocr_engine.py     # Tesseract OCR wrapper
├── config.py         # User configuration
├── requirements.txt  # Python dependencies
├── screenshots.db    # SQLite database (created on first run)
└── config.json       # User settings (created on first run)
```

## Troubleshooting

### "Tesseract Not Found" warning

Make sure Tesseract is installed and either:
- Installed to the default path (`C:\Program Files\Tesseract-OCR`)
- Added to your system PATH

### Scan is slow

OCR is CPU-intensive. The first scan of a large collection will take time, but subsequent scans only process new images.

### No results found

- Make sure you've run a scan first
- Try simpler search terms
- Check if Tesseract is working (the app shows a warning if not)

## License

MIT License
