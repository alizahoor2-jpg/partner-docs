#!/usr/bin/env python3
"""
360dialog Partner Docs Change Monitor
Monitors docs.360dialog.com/partner for any changes (additions, deletions, modifications)
Run with: python3 monitor.py [--check]
"""

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path
import requests
from urllib.parse import urljoin

BASE_URL = "https://docs.360dialog.com/partner"
SITEMAP_URL = f"{BASE_URL}/sitemap.md"
STORAGE_FILE = Path.home() / ".360dialog_docs_baseline.json"

SECTIONS = [
    "get-started",
    "onboarding",
    "partner-api",
    "partner-hub",
    "messaging",
]

def fetch_page(url):
    """Fetch a page and return content with metadata."""
    try:
        resp = requests.get(url, timeout=30)
        if resp.status_code == 200:
            return {
                "content": resp.text,
                "hash": hashlib.sha256(resp.text.encode()).hexdigest(),
                "status_code": resp.status_code,
                "content_length": len(resp.text),
            }
        else:
            return {"error": f"HTTP {resp.status_code}", "status_code": resp.status_code}
    except Exception as e:
        return {"error": str(e), "status_code": 0}


def get_sitemap_urls():
    """Parse sitemap and return all doc URLs."""
    result = fetch_page(SITEMAP_URL)
    if "error" in result:
        print(f"Failed to fetch sitemap: {result['error']}")
        return []

    urls = []
    for line in result["content"].split("\n"):
        if "(https://" in line and ".md)" in line:
            start = line.find("(https://")
            end = line.find(")", start)
            if start != -1 and end != -1:
                url = line[start+1:end]
                if url.endswith(".md"):
                    urls.append(url)

    return urls


def load_baseline():
    """Load stored baseline."""
    if STORAGE_FILE.exists():
        with open(STORAGE_FILE) as f:
            return json.load(f)
    return {}


def save_baseline(baseline):
    """Save baseline to file."""
    with open(STORAGE_FILE, "w") as f:
        json.dump(baseline, f, indent=2)


def compare_and_report(old_baseline, new_results):
    """Compare new results with baseline and report changes."""
    changes = {"additions": [], "deletions": [], "modifications": []}

    old_urls = set(old_baseline.keys())
    new_urls = set(new_results.keys())

    # Check for additions (new URLs)
    for url in new_urls - old_urls:
        changes["additions"].append({
            "url": url,
            "content_hash": new_results[url]["hash"],
            "content_length": new_results[url].get("content_length", 0),
        })

    # Check for deletions (removed URLs)
    for url in old_urls - new_urls:
        changes["deletions"].append({
            "url": url,
            "old_hash": old_baseline[url]["hash"],
        })

    # Check for modifications (changed content)
    for url in old_urls & new_urls:
        old_hash = old_baseline[url]["hash"]
        new_hash = new_results[url].get("hash", "")
        if old_hash != new_hash:
            changes["modifications"].append({
                "url": url,
                "old_hash": old_hash,
                "new_hash": new_hash,
                "old_length": old_baseline[url].get("content_length", 0),
                "new_length": new_results[url].get("content_length", 0),
            })

    return changes


def print_changes(changes, verbose=False):
    """Print detected changes."""
    if not any(changes.values()):
        print("✅ No changes detected")
        return

    print("\n" + "="*60)
    print("🚨 CHANGES DETECTED IN 360DIALOG PARTNER DOCS")
    print("="*60)

    if changes["additions"]:
        print(f"\n📝 NEW PAGES ({len(changes['additions'])}):")
        for item in changes["additions"]:
            print(f"   + {item['url']}")
            print(f"     Size: {item['content_length']:,} bytes")

    if changes["deletions"]:
        print(f"\n🗑️  DELETED PAGES ({len(changes['deletions'])}):")
        for item in changes["deletions"]:
            print(f"   - {item['url']}")

    if changes["modifications"]:
        print(f"\n✏️  MODIFIED PAGES ({len(changes['modifications'])}):")
        for item in changes["modifications"]:
            print(f"   ~ {item['url']}")
            print(f"     Size: {item['old_length']:,} → {item['new_length']:,} bytes ({'+' if item['new_length'] > item['old_length'] else '-'}{abs(item['new_length'] - item['old_length']):,})")

    total = len(changes["additions"]) + len(changes["deletions"]) + len(changes["modifications"])
    print(f"\nTotal changes: {total}")
    print("="*60)


def initialize_baseline():
    """Initialize baseline by fetching all pages."""
    print("Initializing baseline for 360dialog Partner docs...")
    print(f"Base URL: {BASE_URL}")

    baseline = {
        "initialized_at": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "pages": {}
    }

    urls = get_sitemap_urls()
    print(f"Found {len(urls)} pages in sitemap")

    for i, url in enumerate(urls):
        print(f"[{i+1}/{len(urls)}] Fetching: {url}")
        result = fetch_page(url)
        if "error" not in result:
            baseline["pages"][url] = {
                "hash": result["hash"],
                "content_length": result.get("content_length", 0),
                "fetched_at": datetime.now().isoformat(),
            }
        else:
            baseline["pages"][url] = {
                "error": result["error"],
                "fetched_at": datetime.now().isoformat(),
            }
        time.sleep(0.3)  # Be polite to the server

    save_baseline(baseline)
    print(f"\n✅ Baseline saved with {len(baseline['pages'])} pages")
    return baseline


def check_for_changes():
    """Check for changes since last baseline."""
    print("Checking for changes in 360dialog Partner docs...")

    baseline = load_baseline()
    if not baseline:
        print("No baseline found. Initializing...")
        return initialize_baseline()

    print(f"Baseline from: {baseline.get('initialized_at', 'unknown')}")

    current = {"pages": {}}
    urls = get_sitemap_urls()

    for i, url in enumerate(urls):
        print(f"[{i+1}/{len(urls)}] Checking: {url}")
        result = fetch_page(url)
        if "error" not in result:
            current["pages"][url] = {
                "hash": result["hash"],
                "content_length": result.get("content_length", 0),
            }
        time.sleep(0.3)

    changes = compare_and_report(baseline["pages"], current["pages"])
    print_changes(changes)

    if any(changes.values()):
        print("\n⚠️  Changes detected! Updating baseline...")
        baseline["pages"] = current["pages"]
        baseline["checked_at"] = datetime.now().isoformat()
        save_baseline(baseline)
        print("✅ Baseline updated")
    else:
        print("\n✓ Docs are up to date with baseline")

    return changes


if __name__ == "__main__":
    import sys

    if "--init" in sys.argv or "--initialize" in sys.argv:
        initialize_baseline()
    else:
        check_for_changes()