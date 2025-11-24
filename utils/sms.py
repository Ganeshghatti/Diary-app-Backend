from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(account_sid, auth_token)

def send_otp(phone, otp, country_code="+91"):
    try:
        message = client.messages.create(
            body=f"Dear User, your registration OTP with DiaryDad is {otp}. Please do not share this OTP with anyone",
            from_=twilio_number,
            to=f"{country_code}{phone}"
        )
        return True
    except Exception as e:
        print("Twilio Error:", e)
        return False
