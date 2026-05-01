#!/usr/bin/env python3
"""
360dialog Partner Docs - Detailed Change Detection
Shows EXACT lines added/removed with context
"""

import hashlib
import json
import os
import smtplib
import time
import requests
import re
from difflib import unified_diff
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

def find_line_changes(old_content, new_content):
    """Find EXACT lines added and removed"""
    old_lines = old_content.split('\n')
    new_lines = new_content.split('\n')
    
    added_lines = []
    removed_lines = []
    
    # Simple approach: compare line by line
    old_set = set(old_lines)
    new_set = set(new_lines)
    
    # Find added lines (in new but not in old)
    for i, line in enumerate(new_lines):
        if line not in old_set and line.strip():  # Only non-empty lines
            # Find context (previous line)
            context_start = max(0, i-1)
            context = new_lines[context_start:i+2] if i > 0 else new_lines[i:i+2]
            added_lines.append({
                "line": line.strip()[:150],  # Truncate long lines
                "line_number": i + 1,
                "context": [c.strip()[:80] for c in context if c.strip()][:3]
            })
    
    # Find removed lines (in old but not in new)
    for i, line in enumerate(old_lines):
        if line not in new_set and line.strip():
            context_start = max(0, i-1)
            context = old_lines[context_start:i+2] if i > 0 else old_lines[i:i+2]
            removed_lines.append({
                "line": line.strip()[:150],
                "line_number": i + 1,
                "context": [c.strip()[:80] for c in context if c.strip()][:3]
            })
    
    return added_lines[:5], removed_lines[:5]  # Max 5 each

def find_section_changes(old_content, new_content):
    """Find which section had changes"""
    changes = []
    lines = old_content.split('\n')
    
    # Find section headers
    sections = {}
    current_section = "Document Start"
    section_start = 0
    
    for i, line in enumerate(lines):
        if re.match(r'^#{1,6}\s+', line):
            sections[current_section] = {
                "start": section_start,
                "end": i,
                "content": '\n'.join(lines[section_start:i])
            }
            current_section = re.sub(r'^#{1,6}\s+', '', line).strip()
            section_start = i + 1
    
    # Last section
    sections[current_section] = {
        "start": section_start,
        "end": len(lines),
        "content": '\n'.join(lines[section_start:])
    }
    
    # Compare sections
    new_lines = new_content.split('\n')
    new_sections = {}
    current_section = "Document Start"
    section_start = 0
    
    for i, line in enumerate(new_lines):
        if re.match(r'^#{1,6}\s+', line):
            new_sections[current_section] = {
                "start": section_start,
                "end": i,
                "content": '\n'.join(new_lines[section_start:i])
            }
            current_section = re.sub(r'^#{1,6}\s+', '', line).strip()
            section_start = i + 1
    
    new_sections[current_section] = {
        "start": section_start,
        "end": len(new_lines),
        "content": '\n'.join(new_lines[section_start:])
    }
    
    # Find changed sections
    all_sects = set(sections.keys()) | set(new_sections.keys())
    for sect in all_sects:
        old_cont = sections.get(sect, {}).get("content", "")
        new_cont = new_sections.get(sect, {}).get("content", "")
        
        if old_cont != new_cont:
            added, removed = find_line_changes(old_cont, new_cont)
            if added or removed:
                changes.append({
                    "section": sect,
                    "added": added,
                    "removed": removed
                })
    
    return changes[:3]  # Max 3 sections

def send_detailed_email(all_pages, changes_data):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    total = len(changes_data['additions']) + len(changes_data['deletions']) + len(changes_data['modifications'])
    
    if total == 0:
        subject = f"✅ 360dialog Partner Docs - No Changes ({all_pages} pages)"
        body = f"""360dialog Partner Docs - No Changes
=========================================

Checked: {now}

Pages Monitored: {all_pages}
Changes Found: 0

✅ NO CHANGES - Every page verified - exactly the same.

View docs: {BASE_URL}

---
Automated daily check at 12:00 PM PKT
"""
    else:
        subject = f"🚨 360dialog Partner Docs - {total} Change(s) DETECTED!"
        body = f"""360dialog Partner Docs - CHANGES DETECTED!
==================================================

Checked: {now}

TOTAL CHANGES: {total}

"""
        
        # New Pages
        if changes_data.get('additions'):
            body += "\n" + "="*60 + "\n"
            body += "📄 NEW PAGES ADDED\n"
            body += "="*60 + "\n\n"
            for item in changes_data['additions']:
                body += f"NEW PAGE:\n"
                body += f"  Link: {item['url']}\n"
                body += f"  Size: {item['new_length']:,} bytes\n\n"
        
        # Removed Pages
        if changes_data.get('deletions'):
            body += "\n" + "="*60 + "\n"
            body += "🗑️ PAGES REMOVED/DELETED\n"
            body += "="*60 + "\n\n"
            for item in changes_data['deletions']:
                body += f"REMOVED:\n"
                body += f"  Link: {item['url']}\n"
                body += f"  Was: {item['old_length']:,} bytes\n\n"
        
        # Modified Pages
        if changes_data.get('modifications'):
            body += "\n" + "="*60 + "\n"
            body += "✏️ PAGES UPDATED (With EXACT LINE DETAILS)\n"
            body += "="*60 + "\n\n"
            for item in changes_data['modifications']:
                body += f"UPDATED PAGE:\n"
                body += f"  Link: {item['url']}\n\n"
                
                # Size/word/line changes
                diff = item['new_length'] - item['old_length']
                diff_text = f"+{diff}" if diff > 0 else str(diff)
                body += f"  Size: {item['old_length']:,} → {item['new_length']:,} bytes ({diff_text})\n"
                body += f"  Words: {item.get('old_words', 'N/A'):,} → {item.get('new_words', 'N/A'):,}\n"
                body += f"  Lines: {item.get('old_lines', 'N/A'):,} → {item.get('new_lines', 'N/A'):,}\n\n"
                
                # EXACT LINE CHANGES
                if item.get('exact_changes'):
                    for change in item['exact_changes']:
                        body += f"  📍 Section: {change['section']}\n\n"
                        
                        if change.get('added'):
                            body += f"     +++ LINES ADDED ({len(change['added'])}):\n"
                            for line_info in change['added']:
                                body += f"       Line {line_info['line_number']}: {line_info['line']}\n"
                            body += "\n"
                        
                        if change.get('removed'):
                            body += f"     --- LINES REMOVED ({len(change['removed'])}):\n"
                            for line_info in change['removed']:
                                body += f"       Line {line_info['line_number']}: {line_info['line']}\n"
                            body += "\n"
                            body += "\n"
                
                body += "-"*60 + "\n\n"
        
        body += f"""View docs: {BASE_URL}

---
⚠️ Baseline auto-updated after notification.
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
    all_modifications = []
    
    for url in urls:
        result = fetch_page(url)
        if "error" not in result:
            current[url] = {
                "hash": result["hash"],
                "content_length": result["content_length"],
            }
            
            old_data = baseline["pages"].get(url, {})
            if old_data and old_data.get("hash") != result["hash"]:
                mod_item = {
                    "url": url,
                    "old_length": old_data.get("content_length", 0),
                    "new_length": result["content_length"],
                    "old_words": old_data.get("word_count", 0),
                    "new_words": len(result["content"].split()),
                    "old_lines": old_data.get("line_count", 0),
                    "new_lines": len(result["content"].split('\n')),
                }
                
                # Get EXACT line changes
                old_content = old_data.get("_content", "")
                new_content = result["content"]
                
                if old_content and new_content:
                    # Find section-level exact changes
                    exact_changes = find_section_changes(old_content, new_content)
                    if exact_changes:
                        mod_item["exact_changes"] = exact_changes
                    
                    # Also add/removed lines overall
                    added, removed = find_line_changes(old_content, new_content)
                    if added:
                        mod_item["all_added"] = added
                    if removed:
                        mod_item["all_removed"] = removed
                
                all_modifications.append(mod_item)
        time.sleep(0.2)
    
    changes = {"additions": [], "deletions": [], "modifications": []}
    old_urls = set(baseline["pages"].keys())
    new_urls = set(current.keys())
    
    for url in new_urls - old_urls:
        changes["additions"].append({"url": url, "new_length": current[url]["content_length"]})
    
    for url in old_urls - new_urls:
        changes["deletions"].append({"url": url, "old_length": baseline["pages"][url].get("content_length", 0)})
    
    for item in all_modifications:
        changes["modifications"].append(item)
    
    total = len(changes["additions"]) + len(changes["deletions"]) + len(changes["modifications"])
    
    print(f"Changes found: {total}")
    
    send_detailed_email(len(urls), changes)
    
    for url in urls:
        result = fetch_page(url)
        if "error" not in result:
            current[url] = baseline["pages"].get(url, {})
            current[url]["hash"] = result["hash"]
            current[url]["content_length"] = result["content_length"]
            current[url]["word_count"] = len(result["content"].split())
            current[url]["line_count"] = len(result["content"].split('\n'))
            current[url]["_content"] = result["content"]
            current[url]["fetched_at"] = datetime.now().isoformat()
    
    baseline["pages"] = current
    baseline["last_checked"] = datetime.now().isoformat()
    with open(STORAGE_FILE, "w") as f:
        json.dump(baseline, f, indent=2)
    print("Baseline updated with full content")
    
    return total

if __name__ == "__main__":
    run_check()