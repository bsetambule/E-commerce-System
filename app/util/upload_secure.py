# =====================================================
# app/utils/upload_helpers.py
# =====================================================

import os
import uuid
from io import BytesIO
from PIL import Image
from flask import current_app

# =====================================================
# CONFIG
# =====================================================
ALLOWED_FORMATS = {"JPEG", "JPG", "PNG", "WEBP"}
MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB

# =====================================================
# SAVE IMAGE SECURE
# =====================================================
def save_image_secure(file) -> str:
    """
    Secure image upload helper.
    Validates size & format, strips metadata, converts to optimized JPEG.
    Returns public URL.
    """
    if not file:
        raise ValueError("No image provided.")

    # Validate size
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_IMAGE_SIZE:
        raise ValueError("Image exceeds 5MB limit.")

    # Upload folder
    upload_folder = current_app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        raise RuntimeError("UPLOAD_FOLDER not configured.")
    os.makedirs(upload_folder, exist_ok=True)

    # Safe filename
    filename = f"{uuid.uuid4().hex}.jpg"
    save_path = os.path.join(upload_folder, filename)

    # Process image
    try:
        image = Image.open(file)
        image_format = (image.format or "").upper()
        if image_format not in ALLOWED_FORMATS:
            raise ValueError("Unsupported image format.")

        # Convert to RGB & strip metadata
        image = image.convert("RGB")
        clean_image = Image.new(image.mode, image.size)
        clean_image.putdata(list(image.getdata()))

        # Save optimized JPEG
        clean_image.save(save_path, "JPEG", quality=85, optimize=True)

    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(f"Image processing failed: {str(e)}")

    # Return public URL
    return f"/static/uploads/{filename}"


# =====================================================
# SAVE IMAGE FROM EXCEL UPLOAD
# =====================================================
def save_bulk_image(file_bytes_io) -> str:
    """
    Save an image coming from Excel upload (BytesIO object).
    Returns public URL string.
    """
    return save_image_secure(file_bytes_io)