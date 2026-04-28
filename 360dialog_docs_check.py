#!/usr/bin/env python3
"""
360dialog Partner Docs - Scheduled Email Notification Script
Checks every 6 hours and sends email with status
Highly sensitive - detects ANY change (single character)
"""

import hashlib
import json
import os
import smtplib
import time
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

BASE_URL = "https://docs.360dialog.com/partner"

# Use local file for GitHub Actions
if os.environ.get('GITHUB_ACTIONS'):
    STORAGE_FILE = Path(__file__).parent / ".baseline.json"
else:
    STORAGE_FILE = Path.home() / ".360dialog_docs_baseline.json"

# Email config
GMAIL = "mohdalizahoor@gmail.com"
APP_PASSWORD = "qlwblerbnwomowna"
RECIPIENT = "mohdalizahoor@gmail.com"

def fetch_page(url):
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            content = resp.text
            return {
                "content": content,
                "hash": hashlib.sha256(content.encode()).hexdigest(),
                "content_length": len(content),
                "word_count": len(content.split()),
                "line_count": len(content.split('\n')),
            }
        return {"error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def get_urls():
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
        subject = f"✅ 360dialog Partner Docs - No Changes ({pages_checked} pages)"
        body = f"""360dialog Partner Docs - No Changes
=====================================

Checked: {now}

Pages Monitored: {pages_checked}
Changes Found: 0

✅ NO CHANGES - Docs are exactly the same.

Every page verified - no character changes detected.

View docs: {BASE_URL}

---
Automated check every 6 hours
"""
    else:
        subject = f"🚨 360dialog Partner Docs - {changes_summary['total']} Change(s)!"
        body = f"""360dialog Partner Docs - CHANGES DETECTED!
==============================================

Checked: {now}

TOTAL CHANGES: {changes_summary['total']}

"""
        if changes_summary.get("additions"):
            body += f"\n📝 NEW PAGES ADDED ({len(changes_summary['additions'])}):\n"
            for item in changes_summary["additions"]:
                body += f"  + {item['url']}\n"
                body += f"    Size: {item['new_length']:,} bytes\n"
            body += "\n"
        
        if changes_summary.get("deletions"):
            body += f"\n🗑️ PAGES REMOVED ({len(changes_summary['deletions'])}):\n"
            for item in changes_summary["deletions"]:
                body += f"  - {item['url']}\n"
                body += f"    Was: {item['old_length']:,} bytes\n"
            body += "\n"
        
        if changes_summary.get("modifications"):
            body += f"\n✏️ PAGES MODIFIED ({len(changes_summary['modifications'])}):\n"
            for item in changes_summary["modifications"]:
                diff = item['new_length'] - item['old_length']
                diff_text = f"+{diff}" if diff > 0 else str(diff)
                body += f"  ~ {item['url']}\n"
                body += f"    Before: {item['old_length']:,} bytes | After: {item['new_length']:,} bytes ({diff_text})\n"
                body += f"    Words: {item['old_words']:,} → {item['new_words']:,}\n"
                body += f"    Lines: {item['old_lines']:,} → {item['new_lines']:,}\n"
            body += "\n"
        
        body += f"""View docs: {BASE_URL}

---
⚠️ WARNING: Even a single character change (full stop, comma, word) is detected!
Baseline updated automatically after this notification.
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
    print(f"Checking 360dialog Partner Docs... {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    with open(STORAGE_FILE) as f:
        baseline = json.load(f)
    
    urls = get_urls()
    current = {}
    for url in urls:
        result = fetch_page(url)
        if "error" not in result:
            current[url] = {
                "hash": result["hash"],
                "content_length": result["content_length"],
                "word_count": result.get("word_count", 0),
                "line_count": result.get("line_count", 0),
            }
        time.sleep(0.2)
    
    changes = {"additions": [], "deletions": [], "modifications": []}
    old_urls = set(baseline["pages"].keys())
    new_urls = set(current.keys())
    
    # New pages added
    for url in new_urls - old_urls:
        changes["additions"].append({
            "url": url,
            "new_length": current[url]["content_length"],
            "new_words": current[url].get("word_count", 0),
        })
    
    # Pages removed
    for url in old_urls - new_urls:
        changes["deletions"].append({
            "url": url,
            "old_length": baseline["pages"][url].get("content_length", 0),
            "old_words": baseline["pages"][url].get("word_count", 0),
        })
    
    # Pages modified (any character change)
    for url in old_urls & new_urls:
        old_hash = baseline["pages"][url].get("hash", "")
        new_hash = current[url]["hash"]
        if old_hash != new_hash:
            changes["modifications"].append({
                "url": url,
                "old_length": baseline["pages"][url].get("content_length", 0),
                "new_length": current[url]["content_length"],
                "old_words": baseline["pages"][url].get("word_count", 0),
                "new_words": current[url].get("word_count", 0),
                "old_lines": baseline["pages"][url].get("line_count", 0),
                "new_lines": current[url].get("line_count", 0),
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