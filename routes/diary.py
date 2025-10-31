from flask import Blueprint
from controllers.diary import (
    upsert_diary_entry,
    get_diary_entry,
    delete_diary_entry,
    get_month_diaries_entries,
    get_all_diaries_entries
)
from controllers.diary_ai import extract_text_from_image, generate_summary, chat_with_diary

diary_routes = Blueprint("diary_routes", __name__)

# CRUD routes
diary_routes.route("/diary", methods=["POST", "PUT"])(upsert_diary_entry)
diary_routes.route("/diary", methods=["GET"])(get_diary_entry)
diary_routes.route("/diary", methods=["DELETE"])(delete_diary_entry)

# Additional routes
diary_routes.route("/diary/month", methods=["GET"])(get_month_diaries_entries)
diary_routes.route("/diary/all", methods=["GET"])(get_all_diaries_entries)

# AI routes
diary_routes.route("/diary/extract-text", methods=["POST"])(extract_text_from_image)
diary_routes.route("/diary/generate-summary", methods=["POST"])(generate_summary)
diary_routes.route("/diary/chat", methods=["POST"])(chat_with_diary)

