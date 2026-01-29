# Changelog

All notable changes to Screenshot Search will be documented in this file.

## [1.0.0] - 2025-01-28

### Features

#### Search & Indexing
- **Full-text search** - Search screenshots by the text they contain using SQLite FTS5
- **OCR text extraction** - Automatically extract text from images using Tesseract OCR
- **Smart indexing** - Skips already-indexed screenshots for fast re-scanning
- **Recursive scanning** - Scans all subfolders within your screenshots directory
- **Multi-format support** - Supports PNG, JPG, JPEG, GIF, BMP, and WebP images

#### User Interface
- **Thumbnail grid** - View search results as a grid of clickable thumbnails
- **Preview pane** - Click a thumbnail to see a larger preview without opening external apps
- **Extracted text viewer** - View the full OCR text for any screenshot in the preview pane
- **Progress indicator** - See scanning progress with a progress bar
- **Status bar** - Shows total indexed screenshots and current folder

#### Filtering
- **Date filtering** - Filter results by Today, Last 7 Days, Last 30 Days, or Last Year
- **Folder filtering** - Filter by subfolder (automatically detects year/month folder structure)

#### Actions
- **Copy text** - Copy extracted text to clipboard with one click
- **Open image** - Double-click or use button to open full image in default viewer
- **Open folder** - Open the containing folder in Windows Explorer

#### Configuration
- **First-run setup** - Guided setup to select your screenshots folder on first launch
- **Settings dialog** - Change screenshots folder at any time via Settings button
- **Portable config** - Settings saved to local `config.json` file

### Technical
- Built with Python and tkinter
- SQLite database with FTS5 for fast full-text search
- Tesseract OCR integration via pytesseract
- Standalone executable available (no Python required)
