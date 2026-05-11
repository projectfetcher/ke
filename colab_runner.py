import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==================== CREDENTIALS & CONFIG (from GitHub Secrets) ====================
GOOGLE_EMAIL    = os.environ["GOOGLE_EMAIL"]
GOOGLE_PASSWORD = os.environ["GOOGLE_PASSWORD"]
NOTEBOOK_URL    = os.environ["NOTEBOOK_URL"]   # Colab URL stored as a secret

# ==================== DRIVER (Headless for GitHub Actions) ====================
def get_driver():
    options = Options()
    options.add_argument("--headless=new")               # Headless mode
    options.add_argument("--no-sandbox")                  # Required in CI
    options.add_argument("--disable-dev-shm-usage")       # Required in CI
    options.add_argument("--disable-gpu")                 # Required in CI
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # GitHub Actions ships Chrome + chromedriver pre-installed
    # Use the system chromedriver instead of webdriver_manager
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver

# ==================== HELPER: CLICK RUN ANYWAY ====================
def click_run_anyway(driver):
    print("   🔍 Checking for 'Run anyway' popup...")
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "mwc-dialog"))
        )

        btn = driver.execute_script("""
            const dialog = document.querySelector('mwc-dialog');
            if (!dialog) return null;
            const mdBtn = dialog.querySelector('md-text-button:nth-child(3)');
            if (!mdBtn) return null;
            return mdBtn.shadowRoot.querySelector('#button');
        """)

        if btn:
            driver.execute_script("arguments[0].click();", btn)
            print("   ✅ 'Run anyway' clicked!")
            time.sleep(2)
        else:
            print("   ⚠️  Trying fallback — clicking host element...")
            host = driver.find_element(By.CSS_SELECTOR,
                "body > mwc-dialog > md-text-button:nth-child(3)")
            driver.execute_script("arguments[0].click();", host)
            print("   ✅ 'Run anyway' clicked via fallback!")
            time.sleep(2)

    except Exception as e:
        print(f"   ℹ️  No popup detected, continuing... ({type(e).__name__})")

driver = None
try:
    print("🌐 Launching Headless Chrome...")
    driver = get_driver()

    # ====================== LOGIN ======================
    print("🔐 Navigating to Google login...")
    driver.get("https://accounts.google.com/signin")
    time.sleep(3)

    print("📧 Entering email...")
    email_field = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.ID, "identifierId"))
    )
    email_field.click()
    email_field.send_keys(GOOGLE_EMAIL)
    email_field.send_keys(Keys.RETURN)
    time.sleep(3)

    print("🔑 Entering password...")
    password_field = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.NAME, "Passwd"))
    )
    password_field.click()
    password_field.send_keys(GOOGLE_PASSWORD)
    password_field.send_keys(Keys.RETURN)

    print("⏳ Waiting for login to complete...")
    time.sleep(10)

    # Check if login failed or got stuck on accounts page
    if "accounts.google.com" in driver.current_url:
        print(f"⚠️  Still on Google accounts page. URL: {driver.current_url}")
        # Save a screenshot for debugging
        driver.save_screenshot("login_debug.png")
        print("📸 Screenshot saved as login_debug.png")
        raise Exception("Login may have failed — check screenshot artifact and your credentials/2FA settings.")

    print(f"✅ Logged in! Current URL: {driver.current_url}\n")

    # ====================== OPEN NOTEBOOK ======================
    print("📂 Opening Colab notebook...")
    driver.get(NOTEBOOK_URL)

    print("⏳ Waiting 20 seconds for notebook to load...")
    time.sleep(20)
    print(f"✅ Title: {driver.title}\n")

    # Save screenshot of loaded notebook
    driver.save_screenshot("notebook_loaded.png")
    print("📸 Notebook screenshot saved.")

    # ====================== CLICK RUN BUTTONS ======================
    print("🔍 Finding colab-run-button elements...")
    run_buttons = driver.find_elements(By.CSS_SELECTOR, "colab-run-button")
    print(f"✅ Found {len(run_buttons)} button(s)\n")

    for i, btn in enumerate(run_buttons, 1):
        print(f"\n▶️  Clicking Cell {i}...")
        clicked = False

        # Method 1: shadow root
        try:
            shadow = btn.shadow_root
            play = shadow.find_element(By.CSS_SELECTOR, "#filledCircle, svg, circle, span")
            driver.execute_script("arguments[0].click();", play)
            print(f"   ✅ Cell {i} clicked via shadow root!")
            clicked = True
        except Exception as e:
            print(f"   ⚠️  Method 1 failed: {e}")

        # Method 2: direct JS click
        if not clicked:
            try:
                driver.execute_script("arguments[0].click();", btn)
                print(f"   ✅ Cell {i} clicked via JS!")
                clicked = True
            except Exception as e:
                print(f"   ⚠️  Method 2 failed: {e}")

        # Method 3: dispatchEvent
        if not clicked:
            try:
                driver.execute_script("""
                    arguments[0].dispatchEvent(new MouseEvent('click', {
                        bubbles: true, cancelable: true, view: window
                    }));
                """, btn)
                print(f"   ✅ Cell {i} clicked via dispatchEvent!")
                clicked = True
            except Exception as e:
                print(f"   ⚠️  All methods failed for Cell {i}: {e}")

        if clicked:
            click_run_anyway(driver)

        time.sleep(2)

    # ====================== BACKUP: Run All ======================
    print("\n" + "=" * 60)
    print("🔄 Sending 'Run All' (Ctrl + Shift + F9)...")
    print("=" * 60)
    actions = ActionChains(driver)
    actions.key_down(Keys.CONTROL).key_down(Keys.SHIFT).send_keys(Keys.F9) \
           .key_up(Keys.SHIFT).key_up(Keys.CONTROL).perform()
    time.sleep(2)
    click_run_anyway(driver)

    print("✅ 'Run All' sent!")

    # Wait a bit then screenshot final state
    time.sleep(10)
    driver.save_screenshot("final_state.png")
    print("📸 Final state screenshot saved.")
    print("\n🟢 Done!")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    if driver:
        driver.save_screenshot("error_screenshot.png")
        print("📸 Error screenshot saved.")
    raise  # Re-raise so GitHub Actions marks the run as failed

finally:
    try:
        if driver:
            driver.quit()
        print("🛑 Browser closed.")
    except:
        pass
