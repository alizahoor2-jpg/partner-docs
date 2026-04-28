# Partner Docs Monitor

Monitors [360dialog Partner Documentation](https://docs.360dialog.com/partner) for any changes and sends email notifications.

## Features

- Monitors 100+ pages for changes
- Runs daily at 12:00 PM PKT
- Sends email regardless of changes (with status report)
- Detects: new pages, deleted pages, content modifications
- Updates baseline after each check

## Setup

### Local Setup
```bash
git clone https://github.com/alizahoor2-jpg/partner-docs.git
cd partner-docs
pip3 install requests
```

### GitHub Secrets (Required)
Go to Settings → Secrets and add:
- `GMAIL` - Your Gmail address
- `APP_PASSWORD` - Your Gmail App Password
- `RECIPIENT` - Email to receive notifications

### Local Cron (macOS)
```bash
crontab -e
# Add: 0 7 * * * cd /path/to/partner-docs && /usr/bin/python3 360dialog_docs_check.py
```

### GitHub Actions
Automatically runs daily via GitHub Actions (see `.github/workflows/`)

## Files

- `360dialog_docs_check.py` - Main check script (used by cron/GitHub Actions)
- `360dialog_docs_email.py` - Standalone email version
- `360dialog_docs_monitor.py` - Standalone monitor (no email)

## Schedule

- Daily at 12:00 PM Pakistan time (07:00 UTC)
- Can be manually triggered via GitHub Actions

## Monitoring Coverage

- Get Started (Quickstarts, Pricing, Billing, Tech Provider)
- Onboarding (Integrated Onboarding, Webhooks, Coexistence)
- Partner API (11 API reference docs)
- Partner Hub (Overview, WABAs, Users, Billing)
- Messaging (Templates, Marketing, Commerce)

---
Built for 360dialog Partners