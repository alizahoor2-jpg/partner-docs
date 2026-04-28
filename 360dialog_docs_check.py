#!/usr/bin/env python3
"""
360dialog Partner Docs - Scheduled Email Notification Script
Checks every 6 hours and sends email with status
"""

import hashlib
import json
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

BASE_URL = "https://docs.360dialog.com/partner"
STORAGE_FILE = Path.home() / ".360dialog_docs_baseline.json"

# Email config (can be overridden by environment variables for GitHub Actions)
GMAIL = os.environ.get("GMAIL_ADDR", "mohdalizahoor@gmail.com")
APP_PASSWORD = os.environ.get("APP_PASS", "qlwblerbnwomowna")
RECIPIENT = os.environ.get("SEND_TO", "mohdalizahoor@gmail.com")

def fetch_page(url):
    import requests
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return {"hash": hashlib.sha256(resp.text.encode()).hexdigest(), "content_length": len(resp.text)}
        return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def get_urls():
    import requests
    resp = requests.get(f"{BASE_URL}/sitemap.md", timeout=30)
    urls = []
    for line in resp.text.split("\n"):
        if "(https://" in line and ".md)" in line:
            start = line.find("(https://")
            end = line.find(")", start)
            if start != -1 and end != -1:
                url = line[start+1:end]
                if url.endswith(".md"):
                    urls.append(url)
    return urls

def send_status_email(changes_summary, pages_checked):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if changes_summary['total'] == 0:
        subject = f"✅ 360dialog Partner Docs - No Changes ({pages_checked} pages checked)"
        body = f"""360dialog Partner Docs - No Changes
=====================================

Checked: {now}

Total Pages Monitored: {pages_checked}
Changes Found: 0

✅ NO CHANGES - Docs are up to date.

View docs: {BASE_URL}

---
Automated check every 6 hours
"""
    else:
        subject = f"🚨 360dialog Partner Docs - {changes_summary['total']} Change(s)!"
        body = f"""360dialog Partner Docs - Changes Detected!
==============================================

Checked: {now}

Total Changes: {changes_summary['total']}

"""
        if changes_summary.get("additions"):
            body += f"📝 NEW PAGES ({len(changes_summary['additions'])}):\n"
            for item in changes_summary["additions"]:
                body += f"  + {item['url']}\n"
            body += "\n"
        
        if changes_summary.get("deletions"):
            body += f"🗑️ DELETED PAGES ({len(changes_summary['deletions'])}):\n"
            for item in changes_summary["deletions"]:
                body += f"  - {item['url']}\n"
            body += "\n"
        
        if changes_summary.get("modifications"):
            body += f"✏️ MODIFIED PAGES ({len(changes_summary['modifications'])}):\n"
            for item in changes_summary["modifications"]:
                body += f"  ~ {item['url']}\n"
                body += f"     Size: {item['old_length']:,} → {item['new_length']:,}\n"
            body += "\n"
        
        body += f"""View docs: {BASE_URL}

---
Automated check every 6 hours - Baseline updated after notification
"""
    
    msg = MIMEMultipart()
    msg["From"] = GMAIL
    msg["To"] = RECIPIENT
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL, APP_PASSWORD)
        server.sendmail(GMAIL, RECIPIENT, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Email failed: {e}")
        return False

def run_check():
    import requests
    
    print(f"Checking 360dialog Partner Docs... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    with open(STORAGE_FILE) as f:
        baseline = json.load(f)
    
    urls = get_urls()
    current = {}
    for url in urls:
        result = fetch_page(url)
        if "error" not in result:
            current[url] = result
        time.sleep(0.2)
    
    changes = {"additions": [], "deletions": [], "modifications": []}
    old_urls = set(baseline["pages"].keys())
    new_urls = set(current.keys())
    
    for url in new_urls - old_urls:
        changes["additions"].append({"url": url})
    
    for url in old_urls - new_urls:
        changes["deletions"].append({"url": url})
    
    for url in old_urls & new_urls:
        if baseline["pages"][url].get("hash") != current[url]["hash"]:
            changes["modifications"].append({
                "url": url,
                "old_length": baseline["pages"][url].get("content_length", 0),
                "new_length": current[url]["content_length"]
            })
    
    total = len(changes["additions"]) + len(changes["deletions"]) + len(changes["modifications"])
    
    print(f"Changes found: {total}")
    
    # Always send email
    send_status_email({"total": total, **changes}, len(urls))
    
    # Update baseline after notifying of changes
    if total > 0:
        baseline["pages"] = current
        baseline["last_checked"] = datetime.now().isoformat()
        with open(STORAGE_FILE, "w") as f:
            json.dump(baseline, f, indent=2)
        print("Baseline updated")
    
    return total

if __name__ == "__main__":
    run_check()