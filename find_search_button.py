#!/usr/bin/env python3
"""
Debug: Find buttons/links to access search
"""

import os
os.environ['CHROME_PATH'] = '/usr/bin/chromium-browser'

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

chrome_binary = '/usr/bin/chromium-browser'

options = Options()
options.binary_location = chrome_binary
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

try:
    driver = webdriver.Chrome(options=options)
    driver.get("https://fairmatch.fargorate.com/")
    time.sleep(3)
    
    # Get buttons
    buttons = driver.find_elements(By.TAG_NAME, "button")
    print(f"Found {len(buttons)} buttons:\n")
    for i, btn in enumerate(buttons):
        text = btn.text.strip()
        id_ = btn.get_attribute("id") or ""
        class_ = btn.get_attribute("class") or ""
        print(f"Button {i+1}: text='{text}', id={id_}, class={class_}")
    
    # Get links
    links = driver.find_elements(By.TAG_NAME, "a")
    print(f"\n\nFound {len(links)} links:\n")
    for i, link in enumerate(links[:20]):  # First 20
        text = link.text.strip()
        href = link.get_attribute("href") or ""
        id_ = link.get_attribute("id") or ""
        print(f"Link {i+1}: text='{text}', href='{href}', id={id_}")
    
    # Get all visible elements with "search" or "lookup" text
    page_source = driver.page_source
    print(f"\n\nLooking for visible elements with 'search' or 'lookup' text...")
    
    # Try to find elements with onclick or data-* attributes
    all_elements = driver.find_elements(By.XPATH, "//*[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'lookup') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'player')]")
    
    print(f"Found {len(all_elements)} elements with search/player/lookup text\n")
    for i, el in enumerate(all_elements[:15]):
        text = el.text.strip()[:50]
        tag = el.tag_name
        try:
            displayed = el.is_displayed()
        except Exception as e:
            logger.debug("Could not determine display state for element %s: %s", i + 1, e)
            displayed = "?"
        print(f"  {i+1}. <{tag}> displayed={displayed}: {text}")
    
    driver.quit()
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
