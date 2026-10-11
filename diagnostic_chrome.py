#!/usr/bin/env python3
"""
Diagnostic test for Chrome/Selenium setup
"""

import os
import sys
import shutil
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

print("=" * 70)
print("Chrome/Selenium Diagnostic")
print("=" * 70)

# Check Chrome binaries
print("\n1. Checking Chrome binaries...")
print("-" * 70)

chrome_paths = [
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/snap/bin/chromium",
    "/usr/bin/google-chrome",
]

found_chrome = None
for path in chrome_paths:
    exists = Path(path).exists()
    status = "✓" if exists else "✗"
    print(f"{status} {path}")
    if exists and not found_chrome:
        found_chrome = path

# Check PATH
print("\n2. Checking Chrome in PATH...")
print("-" * 70)

for cmd in ["chromium-browser", "chromium", "google-chrome"]:
    path = shutil.which(cmd)
    if path:
        print(f"✓ {cmd} -> {path}")
        if not found_chrome:
            found_chrome = path
    else:
        print(f"✗ {cmd} not in PATH")

# Check chromedriver
print("\n3. Checking chromedriver...")
print("-" * 70)

for path in ["/usr/bin/chromedriver", shutil.which("chromedriver")]:
    if path and Path(path).exists():
        print(f"✓ Found: {path}")
    elif path:
        print(f"✗ {path} does not exist")

# Try to run chrome --version
print("\n4. Testing Chrome binary functionality...")
print("-" * 70)

if found_chrome:
    print(f"Using: {found_chrome}")
    import subprocess
    try:
        result = subprocess.run(
            [found_chrome, "--version"],
            capture_output=True,
            timeout=5,
            text=True
        )
        if result.returncode == 0:
            print(f"✓ {result.stdout.strip()}")
        else:
            print(f"✗ Error: {result.stderr}")
    except subprocess.TimeoutExpired:
        print(f"⏱ Timeout - Chrome took too long to respond")
    except Exception as e:
        print(f"✗ Exception: {e}")
else:
    print("✗ No Chrome binary found!")

# Check Selenium
print("\n5. Checking Selenium installation...")
print("-" * 70)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    print("✓ Selenium is installed")
    
    # Try to list Chrome services
    print("\n6. Testing Selenium Chrome initialization...")
    print("-" * 70)
    
    if found_chrome:
        options = Options()
        options.binary_location = found_chrome
        options.add_argument("--version")
        print(f"Creating webdriver with binary_location={found_chrome}")
        try:
            driver = webdriver.Chrome(options=options)
            print("✓ Webdriver created successfully!")
            driver.quit()
        except Exception as e:
            print(f"✗ Webdriver creation failed: {e}")
    else:
        print("✗ No Chrome binary to test with")
        
except ImportError as e:
    print(f"✗ Selenium not installed: {e}")

print("\n" + "=" * 70)
print("Diagnostic complete")
print("=" * 70)
