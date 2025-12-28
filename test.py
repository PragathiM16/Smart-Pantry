import smtplib
from email.message import EmailMessage

EMAIL_ADDRESS = "smartpantry28@gmail.com"
EMAIL_PASSWORD = "rbtecldpxtzhjjey"

msg = EmailMessage()
msg["Subject"] = "Test Email"
msg["From"] = EMAIL_ADDRESS
msg["To"] = EMAIL_ADDRESS
msg.set_content("Hello! This is a test email from Python.")

try:
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)
    print("Email sent successfully!")
except Exception as e:
    print("Error:", e)
