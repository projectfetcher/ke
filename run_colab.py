# ====================== INSTALL ======================
# pip install selenium webdriver-manager

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# ==================== YOUR CREDENTIALS ====================
GOOGLE_EMAIL    = "calolinalindas@gmail.com"      # ← change this
GOOGLE_PASSWORD = "kate@kunda30"                # ← change this

# ==================== NOTEBOOK URL ====================
NOTEBOOK_URL = "https://colab.research.google.com/drive/1mRtVy4DOJvfP0KgCjxXgsk1yCcE3hHBG?usp=sharing"

# ==================== DRIVER (HEADLESS) ====================
def get_driver():
    options = Options()
    options.add_argument("--headless=new")                        # ← headless, no window
    options.add_argument("--no-sandbox")                          # required in CI/Linux
    options.add_argument("--disable-dev-shm-usage")               # required in CI/Linux
    options.add_argument("--disable-gpu")                         # required headless
    options.add_argument("--window-size=1920,1080")               # simulate real screen
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
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

# ==================== MAIN ====================
driver = None
try:
    print("🌐 Launching headless Chrome...")
    driver = get_driver()

    # ── LOGIN ──────────────────────────────────────────────
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
    time.sleep(8)

    # In headless mode Google may block login with a verification page.
    # If this happens you will see it in the saved screenshot below.
    driver.save_screenshot("after_login.png")
    print(f"📸 Screenshot saved → after_login.png  (current URL: {driver.current_url})")

    if "accounts.google.com" in driver.current_url:
        print("❌ Still on accounts.google.com — Google may have blocked headless login.")
        print("   Tip: run once in non-headless mode first to pass any verification,")
        print("   then re-enable headless.  Exiting.")
        raise SystemExit(1)

    print("✅ Logged in!\n")

    # ── OPEN NOTEBOOK ──────────────────────────────────────
    print("📂 Opening Colab notebook...")
    driver.get(NOTEBOOK_URL)
    print("⏳ Waiting 15 s for notebook to load...")
    time.sleep(15)
    driver.save_screenshot("after_notebook_load.png")
    print(f"✅ Title: {driver.title}")
    print("📸 Screenshot saved → after_notebook_load.png\n")

    # ── CLICK EACH CELL RUN BUTTON ─────────────────────────
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

    # ── BACKUP: RUN ALL ────────────────────────────────────
    print("\n" + "=" * 60)
    print("🔄 Sending 'Run All' (Ctrl+Shift+F9)...")
    print("=" * 60)
    ActionChains(driver) \
        .key_down(Keys.CONTROL).key_down(Keys.SHIFT) \
        .send_keys(Keys.F9) \
        .key_up(Keys.SHIFT).key_up(Keys.CONTROL) \
        .perform()
    time.sleep(2)
    click_run_anyway(driver)
    print("✅ 'Run All' sent!")

    driver.save_screenshot("after_run_all.png")
    print("📸 Screenshot saved → after_run_all.png")
    print("\n🟢 Done!")

except SystemExit as e:
    raise
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    if driver:
        driver.save_screenshot("error_screenshot.png")
        print("📸 Error screenshot saved → error_screenshot.png")

finally:
    try:
        if driver:
            driver.quit()
        print("🛑 Browser closed.")
    except:
        pass
