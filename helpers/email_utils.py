import os
import smtplib
import logging
from email.message import EmailMessage

logger = logging.getLogger("uvicorn.error")

def send_invitation_email(recipient_email: str, team_name: str, inviter_name: str = "A team administrator", is_existing_user: bool = False) -> bool:
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", "no-reply@cruk-datahub.org")

    if is_existing_user:
        subject = f"You have been added to team '{team_name}' on CRUK Metadata Catalogue"
        body = f"""Hello,

{inviter_name} has added you to team '{team_name}' on the CRUK Metadata Catalogue.

You can now log in using your account ({recipient_email}) to access and collaborate within the '{team_name}' team space.

Best regards,
The CRUK Metadata Catalogue Team
"""
    else:
        subject = f"You have been invited to join team '{team_name}' on CRUK Metadata Catalogue"
        body = f"""Hello,

{inviter_name} has invited you to join team '{team_name}' on the CRUK Metadata Catalogue.

To accept this invitation:
1. Visit the CRUK Datahub website.
2. Click "Sign In / Register" and choose "Register".
3. Register using this email address ({recipient_email}) and set your password.

Once registered, your team membership will automatically be activated!

Best regards,
The CRUK Metadata Catalogue Team
"""

    if smtp_server and smtp_user and smtp_password:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = smtp_from
            msg["To"] = recipient_email
            msg.set_content(body)

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
            logger.info(f"Invitation email sent successfully to {recipient_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send invitation email to {recipient_email}: {e}")
            return False
    else:
        logger.info(f"[MOCK EMAIL DISPATCH] To: {recipient_email}\nSubject: {subject}\nBody:\n{body}")
        print(f"[MOCK EMAIL DISPATCH] To: {recipient_email}\nSubject: {subject}\nBody:\n{body}")
        return True
