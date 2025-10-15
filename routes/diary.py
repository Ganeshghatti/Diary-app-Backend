from flask import Blueprint
from controllers.diary import add_or_update_diary, get_diaries_month, get_diary_by_date, extract_text_from_image, delete_diary_by_date

diary_routes = Blueprint("diary_routes", __name__)

diary_routes.route("/diary", methods=["POST"])(add_or_update_diary)
diary_routes.route("/diary/month", methods=["GET"])(get_diaries_month)
diary_routes.route("/diary/date", methods=["GET"])(get_diary_by_date)
diary_routes.route("/diary/extract-text", methods=["POST"])(extract_text_from_image)
diary_routes.route("/diary/delete", methods=["DELETE"])(delete_diary_by_date)