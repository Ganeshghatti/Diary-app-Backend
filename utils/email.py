import requests
import os
from dotenv import load_dotenv

load_dotenv()

# ZeptoMail API configuration
ZEPTOMAIL_URL = "https://api.zeptomail.in/v1.1/email"
ZEPTOMAIL_TOKEN = os.getenv("ZEPTOMAIL_TOKEN")
ZEPTOMAIL_DOMAIN = os.getenv("ZEPTOMAIL_DOMAIN")

def send_welcome_email(email, name):
    """
    Send welcome email to new user
    
    Args:
        email (str): User's email address
        name (str): User's name
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        payload = {
            "from": {"address": ZEPTOMAIL_DOMAIN},
            "to": [{"email_address": {"address": email, "name": name}}],
            "subject": "Welcome to Diary App!",
            "htmlbody": f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #333;">Welcome to Diary App!</h2>
                <p>Hello {name},</p>
                <p>Thank you for joining Diary App! We're excited to have you on board.</p>
                <p>Start documenting your thoughts, experiences, and memories with our easy-to-use diary platform.</p>
                <p>If you have any questions, feel free to reach out to our support team.</p>
                <br>
                <p>Happy writing!<br>Diary App Team</p>
            </div>
            """
        }
        
        headers = {
            'accept': "application/json",
            'content-type': "application/json",
            'authorization': ZEPTOMAIL_TOKEN,
        }
        
        response = requests.post(ZEPTOMAIL_URL, json=payload, headers=headers)
        
        if response.status_code == 200:
            print("Welcome email sent successfully")
            return True
        else:
            print(f"Welcome email sending failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print("Email Error:", e)
        return False
