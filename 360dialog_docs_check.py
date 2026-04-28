#!/usr/bin/env python3
"""
360dialog Partner Docs - Detailed Change Detection
Detects EXACT changes at sentence level with section context
"""

import hashlib
import json
import os
import smtplib
import time
import requests
import re
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

def extract_sections(content):
    """Extract sections (headings) and their content"""
    sections = []
    lines = content.split('\n')
    current_section = "Introduction"
    current_lines = []
    
    for line in lines:
        # Check if heading (# followed by text)
        if re.match(r'^#{1,6}\s+', line):
            if current_lines:
                sections.append({
                    "section": current_section.strip(),
                    "content": ' '.join(current_lines).strip()
                })
            current_section = re.sub(r'^#{1,6}\s+', '', line).strip()
            current_lines = []
        else:
            current_lines.append(line)
    
    # Last section
    if current_lines:
        sections.append({
            "section": current_section.strip(),
            "content": ' '.join(current_lines).strip()
        })
    
    return sections

def find_sentence_changes(old_content, new_content):
    """Find exact sentence/phrase changes between old and new"""
    changes = []
    
    # Split into sentences (rough approach)
    old_sents = re.split(r'(?<=[.!?])\s+', old_content)
    new_sents = re.split(r'(?<=[.!?])\s+', new_content)
    
    # Find additions
    old_set = set(old_sents)
    new_set = set(new_sents)
    
    for sent in new_sents:
        sent = sent.strip()
        if sent and sent not in old_set:
            changes.append({"type": "added", "text": sent[:200]})
    
    for sent in old_sents:
        sent = sent.strip()
        if sent and sent not in new_set:
            changes.append({"type": "removed", "text": sent[:200]})
    
    return changes

def find_section_changes(old_content, new_content):
    """Find which section changed"""
    old_sections = extract_sections(old_content)
    new_sections = extract_sections(new_content)
    
    changes = []
    old_sect_dict = {s['section']: s['content'] for s in old_sections}
    new_sect_dict = {s['section']: s['content'] for s in new_sections}
    
    all_sections = set(old_sect_dict.keys()) | set(new_sect_dict.keys())
    
    for section in all_sections:
        old_content = old_sect_dict.get(section, "")
        new_content = new_sect_dict.get(section, "")
        
        if old_content != new_content:
            # Find what changed in this section
            sent_changes = find_sentence_changes(old_content, new_content)
            if sent_changes:
                changes.append({
                    "section": section,
                    "changes": sent_changes[:5]  # Max 5 changes per section
                })
            else:
                # Content changed but same sentences - show first difference
                if old_content and new_content:
                    changes.append({
                        "section": section,
                        "changes": [{"type": "modified", "text": "Content modified (rephrased)"}]
                    })
    
    return changes[:3]  # Max 3 sections with changes

def compare_contents(old_url, old_content, new_content):
    """Deep comparison between old and new content"""
    result = {
        "old_length": len(old_content),
        "new_length": len(new_content),
        "old_lines": len(old_content.split('\n')),
        "new_lines": len(new_content.split('\n')),
    }
    
    if old_content != new_content:
        # Find section-level changes
        section_changes = find_section_changes(old_content, new_content)
        if section_changes:
            result["section_changes"] = section_changes
        
        # Also show general sentence changes
        sent_changes = find_sentence_changes(old_content, new_content)
        if sent_changes:
            # Categorize
            added = [c for c in sent_changes if c['type'] == 'added']
            removed = [c for c in sent_changes if c['type'] == 'removed']
            
            if added:
                result["added"] = added[:3]
            if removed:
                result["removed"] = removed[:3]
    
    return result

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

✅ NO CHANGES - Every page verified.

The documentation is EXACTLY the same - no character differences.

View docs: {BASE_URL}

---
Automated check daily at 12:00 PM PKT
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
            body += "\n" + "="*50 + "\n"
            body += "📄 NEW PAGES ADDED\n"
            body += "="*50 + "\n\n"
            for item in changes_data['additions']:
                body += f"NEW PAGE:\n"
                body += f"  Link: {item['url']}\n"
                body += f"  Size: {item['new_length']:,} bytes\n\n"
        
        # Removed Pages
        if changes_data.get('deletions'):
            body += "\n" + "="*50 + "\n"
            body += "🗑️ PAGES REMOVED/DELETED\n"
            body += "="*50 + "\n\n"
            for item in changes_data['deletions']:
                body += f"REMOVED:\n"
                body += f"  Link: {item['url']}\n"
                body += f"  Was: {item['old_length']:,} bytes\n\n"
        
        # Modified Pages
        if changes_data.get('modifications'):
            body += "\n" + "="*50 + "\n"
            body += "✏️ PAGES UPDATED (With Details)\n"
            body += "="*50 + "\n\n"
            for item in changes_data['modifications']:
                body += f"UPDATED PAGE:\n"
                body += f"  Link: {item['url']}\n\n"
                
                # Show size/word/line changes
                diff = item['new_length'] - item['old_length']
                diff_text = f"+{diff}" if diff > 0 else str(diff)
                body += f"  Size: {item['old_length']:,} → {item['new_length']:,} bytes ({diff_text})\n"
                body += f"  Words: {item.get('old_words', 'N/A'):,} → {item.get('new_words', 'N/A'):,}\n"
                body += f"  Lines: {item.get('old_lines', 'N/A'):,} → {item.get('new_lines', 'N/A'):,}\n\n"
                
                # Show section changes if available
                if item.get('section_changes'):
                    body += "  Changed Sections:\n"
                    for sect in item['section_changes']:
                        body += f"    - Section: {sect['section']}\n"
                        for change in sect.get('changes', []):
                            if change['type'] == 'added':
                                body += f"      + ADDED: {change['text'][:150]}...\n"
                            elif change['type'] == 'removed':
                                body += f"      - REMOVED: {change['text'][:150]}...\n"
                            else:
                                body += f"      ~ MODIFIED: {change['text']}\n"
                    body += "\n"
                
                # Show added sentences if no section changes
                elif item.get('added'):
                    body += "  Added sentences:\n"
                    for s in item['added'][:2]:
                        body += f"    + {s['text'][:150]}...\n"
                    body += "\n"
                
                # Show removed sentences
                elif item.get('removed'):
                    body += "  Removed sentences:\n"
                    for s in item['removed'][:2]:
                        body += f"    - {s['text'][:150]}...\n"
                    body += "\n"
        
        body += f"""View docs: {BASE_URL}

---
⚠️ Baseline auto-updated after this notification.
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
    all_page_changes = []
    
    for url in urls:
        result = fetch_page(url)
        if "error" not in result:
            current[url] = {
                "hash": result["hash"],
                "content_length": result["content_length"],
            }
            
            # Check if this page has changed
            old_data = baseline["pages"].get(url, {})
            if old_data and old_data.get("hash") != result["hash"]:
                # Deep comparison
                old_content = old_data.get("_content", "")
                new_content = result["content"]
                
                comparison = compare_contents(url, old_content, new_content)
                all_page_changes.append({
                    "url": url,
                    "old_length": old_data.get("content_length", 0),
                    "new_length": result["content_length"],
                    "old_words": old_data.get("word_count", 0),
                    "new_words": len(new_content.split()),
                    "old_lines": old_data.get("line_count", 0),
                    "new_lines": len(new_content.split('\n')),
                    **comparison
                })
        time.sleep(0.2)
    
    changes = {"additions": [], "deletions": [], "modifications": []}
    old_urls = set(baseline["pages"].keys())
    new_urls = set(current.keys())
    
    # New pages added
    for url in new_urls - old_urls:
        changes["additions"].append({
            "url": url,
            "new_length": current[url]["content_length"],
        })
    
    # Pages removed
    for url in old_urls - new_urls:
        changes["deletions"].append({
            "url": url,
            "old_length": baseline["pages"][url].get("content_length", 0),
        })
    
    # Pages modified
    for item in all_page_changes:
        changes["modifications"].append(item)
    
    total = len(changes["additions"]) + len(changes["deletions"]) + len(changes["modifications"])
    
    print(f"Changes found: {total}")
    
    # Always send email
    send_detailed_email(len(urls), changes)
    
    # Update baseline after notifying of changes
    if total > 0:
        # Store full content for deep comparison next time
        for url in urls:
            result = fetch_page(url)
            if "error" not in result:
                current[url]["_content"] = result["content"]
                current[url]["word_count"] = len(result["content"].split())
                current[url]["line_count"] = len(result["content"].split('\n'))
        
        baseline["pages"] = current
        baseline["last_checked"] = datetime.now().isoformat()
        with open(STORAGE_FILE, "w") as f:
            json.dump(baseline, f, indent=2)
        print("Baseline updated with full content for next comparison")
    
    return total

if __name__ == "__main__":
    run_check()