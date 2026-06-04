import os

DIARY_IMAGES_FOLDER = "uploads/diary_images"
DEFAULT_PUBLIC_API_URL = "https://backend.diarydad.me"


def _public_api_base():
    return (os.getenv("PUBLIC_API_URL") or DEFAULT_PUBLIC_API_URL).rstrip("/")


def diary_image_public_url(image_path):
    """Convert a stored diary image path to a public HTTP URL."""
    if not image_path:
        return None
    if image_path.startswith(("http://", "https://")):
        return image_path
    if image_path.startswith("data:"):
        return image_path

    path = image_path if image_path.startswith("/") else f"/{image_path}"
    return f"{_public_api_base()}{path}"


def enrich_diary_image_for_response(diary_doc):
    """Ensure diary.image_url is a public URL when the file exists."""
    if not diary_doc:
        return diary_doc

    diary_obj = diary_doc.get("diary")
    if not isinstance(diary_obj, dict):
        return diary_doc

    image_url = diary_obj.get("image_url")
    if not image_url or image_url.startswith(("http://", "https://", "data:")):
        if image_url and image_url.startswith("data:"):
            diary_obj.pop("image_url", None)
        return diary_doc

    filename = image_url.split("/")[-1]
    filepath = os.path.join(DIARY_IMAGES_FOLDER, filename)

    if not os.path.exists(filepath):
        diary_obj.pop("image_url", None)
        return diary_doc

    diary_obj["image_url"] = diary_image_public_url(image_url)
    return diary_doc
