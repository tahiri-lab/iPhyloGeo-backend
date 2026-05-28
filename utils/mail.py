"""
Email utility to send notifications to users.
"""

import os
import resend
from email_validator import validate_email, EmailSyntaxError, EmailUndeliverableError

from assets.logo_base64 import LOGO_BASE64
from utils.i18n import t


def send_email(subject, content, user_email):
    """
    Send an email using Resend.

    Args:
        subject (str): Email subject
        content (str): Email content (HTML)
        user_email (str): Recipient email address
    """
    try:
        resend.api_key = os.environ["RESEND_API_KEY"]
        from_address = os.environ.get("EMAIL_FROM", "iPhyloGeo <noreply@iphylogeo.ca>")

        resend.Emails.send({
            "from": from_address,
            "to": [user_email],
            "subject": subject,
            "html": content,
        })
        print(f"[Mail] Email sent successfully to {user_email}")
        return True
    except Exception as e:
        print(f"[Mail] Error sending email: {e}")
        return False


def get_results_email_template(results_url, lang="en"):
    """
    Generate the HTML content for the results email.

    Args:
        results_url (str): The URL path to the results (e.g., "/result/123")
    """
    # Ensure full URL if it's relative
    if not results_url.startswith("http"):
        frontend_base = os.environ.get("FRONTEND_URL", "https://i-phylo-geo-frontend.vercel.app")
        full_url = f"{frontend_base}{results_url}"
    else:
        full_url = results_url

    title = t("result.email-template.title", lang)
    completed = t("result.email-template.completed", lang)
    view_prompt = t("result.email-template.view-prompt", lang)
    button_text = t("result.email-template.button", lang)

    html_lang = "fr" if lang == "fr" else "en"

    return f"""
<!DOCTYPE html>
<html lang="{html_lang}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #e3e3e3;
        }}
        .container {{
            width: 100%;
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            padding: 20px;
        }}
        .header {{
            text-align: center;
            background-color: #f8f8f8;
            padding: 10px;
        }}
        .header img {{
            width: 250px;
            height: auto;
        }}
        .title {{
            text-align: center;
            font-size: 24px;
            margin: 20px 0;
            color: #333333;
        }}
        .content {{
            text-align: center;
            font-size: 16px;
            line-height: 1.5;
            color: #333333;
        }}
        .button-container {{
            text-align: center;
            margin: 20px 0;
        }}
        .button {{
            display: inline-block;
            background-color: #007c58;
            color: #ffffff !important;
            padding: 15px 30px;
            text-decoration: none;
            font-size: 16px;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="{LOGO_BASE64}" alt="iPhyloGeo Logo">
        </div>
        <div class="title">
            {title}
        </div>
        <div class="content">
            <p>{completed}</p>
            <p>{view_prompt}</p>
        </div>
        <div class="button-container">
            <a href="{full_url}" class="button">{button_text}</a>
        </div>
    </div>
</body>
</html>
"""

def verify_email_address(user_email):
    """
    Verify the user email for any error

    Args:
    user_email (str): Recipient email

    Returns
    Error string or None
    """
    try:
        validate_email(user_email, check_deliverability=False)
        return None
    except EmailSyntaxError:
        return "The format of the email address is invalid"
    except EmailUndeliverableError:
        return "The domain of the email address is invalid"


def send_results_ready_email(user_email, results_url, lang="en"):
    """
    Send the standard 'Results Ready' email to the user.

    Args:
        user_email (str): Recipient email
        results_url (str): URL to the results page
    """
    subject = t("result.email-template.subject", lang)
    content = get_results_email_template(results_url, lang)
    return send_email(subject, content, user_email)
