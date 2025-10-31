from flask import Blueprint
from controllers.user import update_profile, get_profile

user_routes = Blueprint("user_routes", __name__)

user_routes.route("/user/profile", methods=["PUT"])(update_profile)
user_routes.route("/user/profile", methods=["GET"])(get_profile)

