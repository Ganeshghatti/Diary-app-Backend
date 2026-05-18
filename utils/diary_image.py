import base64
import os

DIARY_IMAGES_FOLDER = "uploads/diary_images"

def _mime_type_for_filename(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpeg"
    if ext == "png":
        return "image/png"
    if ext == "gif":
        return "image/gif"
    if ext == "webp":
        return "image/webp"
    return "image/jpeg"

def enrich_diary_image_for_response(diary_doc):
    """Replace stored diary.image_url path with a base64 data URI for API responses."""
    if not diary_doc:
        return diary_doc

    diary_obj = diary_doc.get("diary")
    if not isinstance(diary_obj, dict):
        return diary_doc

    image_url = diary_obj.get("image_url")
    if not image_url or image_url.startswith("data:"):
        return diary_doc

    filename = image_url.split("/")[-1]
    filepath = os.path.join(DIARY_IMAGES_FOLDER, filename)

    if not os.path.exists(filepath):
        diary_obj.pop("image_url", None)
        return diary_doc

    try:
        with open(filepath, "rb") as image_file:
            image_data = base64.b64encode(image_file.read()).decode("utf-8")
            mime_type = _mime_type_for_filename(filename)
            diary_obj["image_url"] = f"data:{mime_type};base64,{image_data}"
    except Exception as e:
        print(f"Warning: Could not load diary image: {str(e)}")
        diary_obj.pop("image_url", None)

    return diary_doc

def diary_image_path_to_data_uri(image_url):
    """Convert a stored diary image path to a base64 data URI."""
    if not image_url or image_url.startswith("data:"):
        return image_url

    filename = image_url.split("/")[-1]
    filepath = os.path.join(DIARY_IMAGES_FOLDER, filename)
    if not os.path.exists(filepath):
        return None

    with open(filepath, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode("utf-8")
        mime_type = _mime_type_for_filename(filename)
        return f"data:{mime_type};base64,{image_data}"
