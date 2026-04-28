#!/usr/bin/env python3
"""
Simple webhook endpoint for cron-job.org
Upload this to your web server or use GitHub Pages with a serverless function
"""

import json
import hashlib
import requests
import smtplib
import time
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# Configuration
BASE_URL = "https://docs.360dialog.com/partner"
GMAIL = "mohdalizahoor@gmail.com"
APP_PASSWORD = "qlwblerbnwomowna"
RECIPIENT = "mohdalizahoor@gmail.com"
BASELINE_PATH = "/home/ubuntu/partner-docs/.baseline.json"  # Change this path

def fetch_page(url):
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return {"content": resp.text, "hash": hashlib.sha256(resp.text.encode()).hexdigest(), "length": len(resp.text)}
    except:
        pass
    return None

def get_urls():
    try:
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
    except:
        return []

def find_line_changes(old_content, new_content):
    old_lines = set([l.strip() for l in old_content.split('\n') if l.strip()])
    new_lines = set([l.strip() for l in new_content.split('\n') if l.strip()])
    added = new_lines - old_lines
    removed = old_lines - new_lines
    return list(added)[:5], list(removed)[:5]

def send_email(changes, total_pages):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if total_pages > 0:
        subject = f"🚨 360dialog Partner Docs - {total_pages} Change(s)!"
        body = f"Changes detected at {now}\n\n"
    else:
        subject = f"✅ 360dialog Partner Docs - No Changes ({changes.get('pages',0)} pages)"
        body = f"No changes at {now}\n\n"
    
    for url in changes.get('add', []):
        body += f"📄 NEW: {url}\n"
    for url in changes.get('del', []):
        body += f"🗑️ REMOVED: {url}\n"
    for item in changes.get('mod', []):
        body += f"✏️ UPDATED: {item['url']}\n"
        body += f"   Size: {item['old']:,} → {item['new']:,}\n"
        if item.get('added'):
            for l in item['added']:
                body += f"   + {l[:100]}\n"
        if item.get('removed'):
            for l in item['removed']:
                body += f"   - {l[:100]}\n"
    
    msg = MIMEMultipart()
    msg['From'] = GMAIL
    msg['To'] = RECIPIENT
    msg['Subject'] = subject
    msg.attach(MIMEText(body))
    
    try:
        s = smtplib.SMTP('smtp.gmail.com', 587)
        s.starttls()
        s.login(GMAIL, APP_PASSWORD)
        s.sendmail(GMAIL, RECIPIENT, msg.as_string())
        s.quit()
    except Exception as e:
        print(f"Email error: {e}")

def run_check():
    # Load baseline
    try:
        with open(BASELINE_PATH) as f:
            baseline = json.load(f)
    except:
        baseline = {"pages": {}}
    
    urls = get_urls()
    current = {}
    changes = {"add": [], "del": [], "mod": [], "pages": len(urls)}
    
    for url in urls:
        result = fetch_page(url)
        if result:
            current[url] = {"hash": result["hash"], "len": result["length"]}
            
            old_data = baseline["pages"].get(url, {})
            if old_data and old_data.get("hash") != result["hash"]:
                # Get line-level changes if we have old content
                old_content = old_data.get("_content", "")
                added, removed = find_line_changes(old_content, result["content"])
                changes["mod"].append({
                    "url": url,
                    "old": old_data.get("len", 0),
                    "new": result["length"],
                    "added": added,
                    "removed": removed
                })
            time.sleep(0.2)
    
    old_urls = set(baseline["pages"].keys())
    new_urls = set(current.keys())
    
    changes["add"] = list(new_urls - old_urls)
    changes["del"] = list(old_urls - new_urls)
    
    total = len(changes["add"]) + len(changes["del"]) + len(changes["mod"])
    
    # Always send email
    send_email(changes, total)
    
    # Update baseline if changes found
    if total > 0:
        for url in urls:
            result = fetch_page(url)
            if result:
                current[url]["_content"] = result["content"]
        
        baseline["pages"] = current
        baseline["last_checked"] = datetime.now().isoformat()
        with open(BASELINE_PATH, "w") as f:
            json.dump(baseline, f)
    
    return total

# For cron-job.org - this is the main entry point
if __name__ == "__main__":
    print("Content-Type: text/plain")
    print()
    try:
        count = run_check()
        print(f"OK - {count} changes detected and email sent")
    except Exception as e:
        print(f"Error: {e}")