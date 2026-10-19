"""Emails a failure alert with the tail of a sync log.

Usage: alert_email.py <log_file> [exit_code]

Reads SMTP settings from .env (see .env.example). Does nothing if they are
not configured, so scheduled runs never fail because of the alert itself.
"""
import os
import smtplib
import sys
from email.message import EmailMessage
from email.utils import formatdate


def load_env(path='.env'):
    env = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    env[key.strip()] = val.strip().strip('"').strip("'")
    return env


def tail(path, lines=40):
    try:
        with open(path, errors='replace') as f:
            return ''.join(f.readlines()[-lines:])
    except OSError as e:
        return f'(could not read {path}: {e})'


def main():
    log_file = sys.argv[1] if len(sys.argv) > 1 else ''
    exit_code = sys.argv[2] if len(sys.argv) > 2 else '?'
    env = {**load_env(), **os.environ}
    host = env.get('TESLA_ALERT_SMTP_HOST', '')
    to = [a.strip() for a in env.get('TESLA_ALERT_EMAIL_TO', '').split(',') if a.strip()]
    sender = env.get('TESLA_ALERT_EMAIL_FROM', '') or env.get('TESLA_ALERT_SMTP_USERNAME', '')
    if not (host and to and sender):
        print('Email alert not configured (TESLA_ALERT_SMTP_HOST / _EMAIL_TO / _EMAIL_FROM); skipping.')
        return

    msg = EmailMessage()
    msg['Subject'] = f'Tesla sync failed (exit code {exit_code})'
    msg['From'] = sender
    msg['To'] = ', '.join(to)
    msg['Date'] = formatdate(localtime=True)
    msg.set_content(
        'The daily Tesla sync failed, so the dashboard was not updated.\n\n'
        f'Last lines of {log_file}:\n\n{tail(log_file)}'
    )

    port = int(env.get('TESLA_ALERT_SMTP_PORT', '587'))
    user = env.get('TESLA_ALERT_SMTP_USERNAME', '')
    password = env.get('TESLA_ALERT_SMTP_PASSWORD', '')
    if user and not password:
        print('Email alert has no TESLA_ALERT_SMTP_PASSWORD yet; skipping.')
        return
    try:
        if port == 465:
            client = smtplib.SMTP_SSL(host, port, timeout=30)
        else:
            client = smtplib.SMTP(host, port, timeout=30)
            client.starttls()
        with client:
            if user:
                client.login(user, password)
            client.send_message(msg)
        print(f'Sent failure alert to {", ".join(to)}.')
    except (OSError, smtplib.SMTPException) as e:
        print(f'Could not send failure alert: {e}')


if __name__ == '__main__':
    main()
