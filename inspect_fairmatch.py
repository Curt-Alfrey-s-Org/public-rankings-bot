#!/usr/bin/env python3
"""
Debug: Print all inputs on FairMatch page
"""

import os
os.environ['CHROME_PATH'] = '/usr/bin/chromium-browser'

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

chrome_binary = '/usr/bin/chromium-browser'

print("Inspecting FairMatch inputs...")

options = Options()
options.binary_location = chrome_binary
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

try:
    driver = webdriver.Chrome(options=options)
    driver.get("https://fairmatch.fargorate.com/")
    
    # Wait for page to fully load
    wait = WebDriverWait(driver, 15)
    time.sleep(3)  # Additional wait for JS to render
    
    # Get all inputs
    inputs = driver.find_elements(By.TAG_NAME, "input")
    print(f"\nFound {len(inputs)} input elements:\n")
    
    for i, inp in enumerate(inputs):
        name = inp.get_attribute("name") or ""
        type_ = inp.get_attribute("type") or ""
        placeholder = inp.get_attribute("placeholder") or ""
        id_ = inp.get_attribute("id") or ""
        class_ = inp.get_attribute("class") or ""
        
        # Check visibility
        try:
            displayed = inp.is_displayed()
        except Exception as e:
            logger.debug("Could not determine display state for input %s: %s", i + 1, e)
            displayed = "?"
        
        print(f"Input {i+1}:")
        print(f"  type={type_}, name={name}, placeholder={placeholder}")
        print(f"  id={id_}, class={class_}")
        print(f"  displayed={displayed}")
        print()
    
    # Also check for any text that says "search" or "player"
    page_text = driver.page_source
    if "search" in page_text.lower():
        print("✓ Found 'search' in page source")
    if "player" in page_text.lower():
        print("✓ Found 'player' in page source")
    if "lookup" in page_text.lower():
        print("✓ Found 'lookup' in page source")
    
    driver.quit()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
