from twilio.rest import Client
import os
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_number = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(account_sid, auth_token)

def send_otp(phone, otp):
    try:
        message = client.messages.create(
            body=f"Your App OTP is {otp}",
            from_=twilio_number,
            to=f"+91{phone}"
        )
        return True
    except Exception as e:
        print("Twilio Error:", e)
        return False
