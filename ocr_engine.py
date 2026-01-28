import pytesseract
from PIL import Image
from pathlib import Path

# Common Tesseract installation paths on Windows
TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    r"C:\Users\liamd\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
]


def configure_tesseract():
    """Configure the path to Tesseract executable if not in PATH."""
    for path in TESSERACT_PATHS:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path
            return True
    return False


def extract_text(image_path: str) -> str:
    """
    Extract text from an image using Tesseract OCR.

    Args:
        image_path: Path to the image file

    Returns:
        Extracted text as a string, or empty string if extraction fails
    """
    try:
        image = Image.open(image_path)

        # Convert to RGB if necessary (handles PNG with transparency)
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')

        # Run OCR
        text = pytesseract.image_to_string(image)

        return text.strip()

    except Exception as e:
        print(f"OCR failed for {image_path}: {e}")
        return ""


def is_tesseract_available() -> bool:
    """Check if Tesseract is available."""
    try:
        # Try to configure tesseract path first
        configure_tesseract()

        # Test by getting version
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False
