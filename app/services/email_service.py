import asyncio
import html
import logging
import smtplib
from email.message import EmailMessage
from typing import Any

from app.core.config import settings
from app.models.client import Client
from app.models.kam import Kam
from app.models.monthly_report import MonthlyReport

logger = logging.getLogger(__name__)

MONTHS_FR = [
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]


def month_name(month: int) -> str:
    if 1 <= month <= 12:
        return MONTHS_FR[month - 1]
    return f"{month:02d}"


def notification_subject(report: MonthlyReport, client: Client) -> str:
    return (
        f"[Sales Visual] Rapport {client.name} – "
        f"{month_name(report.report_month)} {report.report_year} disponible"
    )


def email_url(value: str | None) -> str | None:
    if not value or not value.strip():
        return None

    url = value.strip()
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("/"):
        return f"{settings.PUBLIC_APP_URL.rstrip('/')}{url}"
    return url


def render_kam_notification_html(
    report: MonthlyReport,
    client: Client,
    kam: Kam,
) -> str:
    period = f"{month_name(report.report_month)} {report.report_year}"
    power_bi_url = email_url(client.power_bi_url)
    file_url = email_url(report.fichier_url)
    power_bi_button = ""
    if power_bi_url:
        power_bi_button = f"""
                <table role="presentation" cellspacing="0" cellpadding="0" style="width:100%;margin:0 0 14px 0;">
                  <tr>
                    <td>
                      <a href="{html.escape(power_bi_url)}" target="_blank" style="display:block;background:#2563eb;color:#ffffff;text-decoration:none;text-align:center;font-weight:800;font-size:16px;padding:15px 18px;border-radius:12px;">
                        Ouvrir Power BI
                      </a>
                    </td>
                  </tr>
                </table>"""

    file_button = ""
    if file_url:
        file_button = f"""
                <table role="presentation" cellspacing="0" cellpadding="0" style="width:100%;margin:0 0 30px 0;">
                  <tr>
                    <td>
                      <a href="{html.escape(file_url)}" target="_blank" style="display:block;background:#16a34a;color:#ffffff;text-decoration:none;text-align:center;font-weight:800;font-size:16px;padding:15px 18px;border-radius:12px;">
                        Télécharger le fichier Excel
                      </a>
                    </td>
                  </tr>
                </table>"""

    return f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(notification_subject(report, client))}</title>
  </head>
  <body style="margin:0;padding:0;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;color:#111827;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f4f6;padding:24px 12px;">
      <tr>
        <td align="center">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:640px;background:#ffffff;border-radius:18px;overflow:hidden;border:1px solid #e5e7eb;">
            <tr>
              <td style="background:#2563eb;padding:28px 32px;color:#ffffff;">
                <div style="font-size:13px;letter-spacing:0.08em;text-transform:uppercase;font-weight:700;opacity:0.9;">Sales Visual</div>
                <div style="font-size:26px;font-weight:800;line-height:1.2;margin-top:8px;">AVO Carbon</div>
              </td>
            </tr>
            <tr>
              <td style="padding:32px;">
                <h1 style="margin:0 0 18px 0;font-size:24px;line-height:1.25;color:#111827;">
                  Votre rapport Sales Visual est disponible
                </h1>
                <p style="margin:0 0 12px 0;font-size:16px;line-height:1.6;color:#374151;">
                  Bonjour {html.escape(kam.name)},
                </p>
                <p style="margin:0 0 24px 0;font-size:16px;line-height:1.6;color:#374151;">
                  Le rapport mensuel pour <strong>{html.escape(client.name)}</strong> est maintenant disponible.
                </p>

                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f8fafc;border:1px solid #e5e7eb;border-radius:14px;margin:0 0 26px 0;">
                  <tr>
                    <td style="padding:20px 22px;">
                      <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                        <tr>
                          <td style="padding:8px 0;font-size:13px;color:#6b7280;width:38%;">Client</td>
                          <td style="padding:8px 0;font-size:15px;color:#111827;font-weight:700;">{html.escape(client.name)}</td>
                        </tr>
                        <tr>
                          <td style="padding:8px 0;font-size:13px;color:#6b7280;">Période</td>
                          <td style="padding:8px 0;font-size:15px;color:#111827;font-weight:700;">{html.escape(period)}</td>
                        </tr>
                        <tr>
                          <td style="padding:8px 0;font-size:13px;color:#6b7280;">Préparé par</td>
                          <td style="padding:8px 0;font-size:15px;color:#111827;font-weight:700;">Aziza Hamrouni</td>
                        </tr>
                        <tr>
                          <td style="padding:8px 0;font-size:13px;color:#6b7280;">Statut</td>
                          <td style="padding:8px 0;font-size:15px;color:#16a34a;font-weight:800;">Disponible</td>
                        </tr>
                      </table>
                    </td>
                  </tr>
                </table>

{power_bi_button}
{file_button}

                <p style="margin:0;font-size:15px;line-height:1.6;color:#374151;">
                  Cordialement,<br>
                  <strong>Sales Visual Platform</strong>
                </p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>"""


def _send_message(report: MonthlyReport, client: Client, kam: Kam) -> dict[str, Any]:
    if not settings.SMTP_HOST or not settings.EMAIL_FROM:
        raise RuntimeError("SMTP settings are not configured")

    subject = notification_subject(report, client)
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = kam.email
    msg.set_content(
        f"Bonjour {kam.name},\n\n"
        f"Le rapport mensuel pour {client.name} est maintenant disponible.\n\n"
        "Cordialement,\nSales Visual Platform"
    )
    msg.add_alternative(render_kam_notification_html(report, client, kam), subtype="html")

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        if settings.SMTP_USER:
            smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        refused = smtp.send_message(msg)

    if refused:
        raise RuntimeError(f"SMTP refused recipients: {refused}")

    return {
        "recipient": kam.email,
        "subject": subject,
        "smtp_refused_recipients": refused,
    }


async def send_kam_email(
    report: MonthlyReport,
    client: Client,
    kam: Kam,
) -> tuple[bool, str | None, dict[str, Any] | None]:
    try:
        response = await asyncio.to_thread(_send_message, report, client, kam)
    except Exception as exc:
        logger.exception("Failed to send KAM notification")
        return False, str(exc), None
    return True, None, response


async def send_kam_notification(
    report: MonthlyReport,
    client: Client,
) -> dict[str, Any]:
    if not client.kams:
        raise RuntimeError("No KAMs configured for client")

    kam = client.kams[0]
    success, error_msg, response = await send_kam_email(report, client, kam)
    if not success:
        return {
            "success": False,
            "recipient": kam.email,
            "subject": notification_subject(report, client),
            "mailtrap_test": True,
            "error": error_msg,
        }

    return {
        "success": True,
        "recipient": kam.email,
        "subject": notification_subject(report, client),
        "mailtrap_test": True,
        "smtp_response": response,
    }
