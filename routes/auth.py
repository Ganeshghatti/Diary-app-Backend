from flask import Blueprint
from controllers.auth import request_otp, verify_otp

auth_routes = Blueprint("auth_routes", __name__)

auth_routes.route("/auth/request-otp", methods=["POST"])(request_otp)
auth_routes.route("/auth/verify-otp", methods=["POST"])(verify_otp)
