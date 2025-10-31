from flask import Blueprint
from controllers.admin import admin_login, get_all_users, get_user_details, get_engagement_stats

admin_routes = Blueprint("admin_routes", __name__)

# Admin login (no auth required)
admin_routes.route("/admin/login", methods=["POST"])(admin_login)

# Protected admin routes
admin_routes.route("/admin/users", methods=["GET"])(get_all_users)
admin_routes.route("/admin/users/<user_id>", methods=["GET"])(get_user_details)
admin_routes.route("/admin/engagement", methods=["GET"])(get_engagement_stats)

