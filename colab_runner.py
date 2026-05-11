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
NOTEBOOK_URL    = os.environ["NOTEBOOK_URL"]

# ==================== DRIVER ====================
def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--lang=en-US")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return driver

# ==================== HELPER: find field with fallback selectors ====================
def find_field(driver, selectors, timeout=20, label="field"):
    """Try multiple (By, value) selectors until one is visible and enabled."""
    print(f"   🔍 Looking for: {label}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        for by, val in selectors:
            try:
                el = driver.find_element(by, val)
                if el.is_displayed() and el.is_enabled():
                    print(f"   ✅ Found '{label}' via {by}='{val}'")
                    return el
            except Exception:
                pass
        time.sleep(0.5)
    driver.save_screenshot(f"timeout_{label.replace(' ', '_')}.png")
    print(f"   ❌ Could not find '{label}' — screenshot saved.")
    raise TimeoutError(f"Field not found: {label}")

# ==================== HELPER: click run anyway popup ====================
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
            host = driver.find_element(
                By.CSS_SELECTOR, "body > mwc-dialog > md-text-button:nth-child(3)")
            driver.execute_script("arguments[0].click();", host)
            print("   ✅ 'Run anyway' clicked via fallback!")
            time.sleep(2)
    except Exception as e:
        print(f"   ℹ️  No popup detected ({type(e).__name__})")

# ==================== MAIN ====================
driver = None
try:
    print("🌐 Launching Headless Chrome...")
    driver = get_driver()

    # ── STEP 1: Load Google login page ──────────────────────────────────────
    print("🔐 Navigating to Google login...")
    driver.get(
        "https://accounts.google.com/signin/v2/identifier"
        "?flowName=GlifWebSignIn&flowEntry=ServiceLogin"
    )
    time.sleep(4)
    driver.save_screenshot("step1_email_page.png")
    print(f"   Page title: {driver.title} | URL: {driver.current_url}")

    # ── STEP 2: Enter email ─────────────────────────────────────────────────
    print("📧 Entering email...")
    email_field = find_field(driver, [
        (By.ID,   "identifierId"),
        (By.NAME, "identifier"),
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.XPATH, "//input[@autocomplete='username']"),
    ], timeout=20, label="email input")

    email_field.click()
    time.sleep(0.3)
    email_field.clear()
    for char in GOOGLE_EMAIL:          # type slowly to avoid bot detection
        email_field.send_keys(char)
        time.sleep(0.05)
    time.sleep(0.5)

    # Click the "Next" button
    try:
        next_btn = find_field(driver, [
            (By.ID, "identifierNext"),
            (By.CSS_SELECTOR, "#identifierNext button"),
            (By.CSS_SELECTOR, "button.VfPpkd-LgbsSe[jsname='LgbsSe']"),
            (By.XPATH, "//button[.//span[contains(text(),'Next')]]"),
        ], timeout=5, label="email Next button")
        driver.execute_script("arguments[0].click();", next_btn)
    except Exception:
        print("   ⚠️  Next button not found — pressing Enter instead")
        email_field.send_keys(Keys.RETURN)

    time.sleep(5)
    driver.save_screenshot("step2_after_email.png")
    print(f"   URL after email: {driver.current_url}")

    # ── STEP 3: Enter password ──────────────────────────────────────────────
    print("🔑 Entering password...")
    password_field = find_field(driver, [
        (By.CSS_SELECTOR, "input[type='password']"),
        (By.NAME, "Passwd"),
        (By.NAME, "password"),
        (By.XPATH, "//input[@autocomplete='current-password']"),
        (By.XPATH, "//input[@autocomplete='new-password']"),
        (By.XPATH, "//input[@type='password']"),
    ], timeout=20, label="password input")

    password_field.click()
    time.sleep(0.3)
    password_field.clear()
    for char in GOOGLE_PASSWORD:       # type slowly
        password_field.send_keys(char)
        time.sleep(0.05)
    time.sleep(0.5)

    # Click the "Next" / "Sign in" button
    try:
        pw_next = find_field(driver, [
            (By.ID, "passwordNext"),
            (By.CSS_SELECTOR, "#passwordNext button"),
            (By.XPATH, "//button[.//span[contains(text(),'Next')]]"),
            (By.XPATH, "//button[@type='submit']"),
        ], timeout=5, label="password Next button")
        driver.execute_script("arguments[0].click();", pw_next)
    except Exception:
        print("   ⚠️  Password Next button not found — pressing Enter instead")
        password_field.send_keys(Keys.RETURN)

    print("⏳ Waiting for login redirect...")
    time.sleep(12)
    driver.save_screenshot("step3_after_password.png")
    print(f"   URL after password: {driver.current_url}")

    if "accounts.google.com" in driver.current_url:
        print("⚠️  Still on accounts page — login likely failed.")
        print("   Common causes: wrong password, 2FA/SMS challenge, Google security block.")
        print("   Check step3_after_password.png in the Actions artifacts.")
        raise Exception("Google login failed — check screenshots and use an App Password.")

    print("✅ Logged in!\n")

    # ── STEP 4: Open Colab notebook ─────────────────────────────────────────
    print("📂 Opening Colab notebook...")
    driver.get(NOTEBOOK_URL)
    print("⏳ Waiting 20s for notebook to load...")
    time.sleep(20)
    print(f"✅ Title: {driver.title}")
    driver.save_screenshot("notebook_loaded.png")

    # ── STEP 5: Click all run buttons ───────────────────────────────────────
    print("\n🔍 Finding colab-run-button elements...")
    run_buttons = driver.find_elements(By.CSS_SELECTOR, "colab-run-button")
    print(f"✅ Found {len(run_buttons)} button(s)\n")

    for i, btn in enumerate(run_buttons, 1):
        print(f"\n▶️  Clicking Cell {i}...")
        clicked = False

        try:                           # Method 1: shadow root
            shadow = btn.shadow_root
            play = shadow.find_element(By.CSS_SELECTOR, "#filledCircle, svg, circle, span")
            driver.execute_script("arguments[0].click();", play)
            print(f"   ✅ Cell {i} clicked via shadow root!")
            clicked = True
        except Exception as e:
            print(f"   ⚠️  Shadow root method failed: {e}")

        if not clicked:
            try:                       # Method 2: direct JS click
                driver.execute_script("arguments[0].click();", btn)
                print(f"   ✅ Cell {i} clicked via JS!")
                clicked = True
            except Exception as e:
                print(f"   ⚠️  JS click failed: {e}")

        if not clicked:
            try:                       # Method 3: dispatchEvent
                driver.execute_script("""
                    arguments[0].dispatchEvent(new MouseEvent('click', {
                        bubbles: true, cancelable: true, view: window
                    }));
                """, btn)
                print(f"   ✅ Cell {i} clicked via dispatchEvent!")
                clicked = True
            except Exception as e:
                print(f"   ⚠️  All click methods failed for Cell {i}: {e}")

        if clicked:
            click_run_anyway(driver)
        time.sleep(2)

    # ── STEP 6: Backup — Run All ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("🔄 Sending Run All (Ctrl+Shift+F9)...")
    print("=" * 60)
    actions = ActionChains(driver)
    actions.key_down(Keys.CONTROL).key_down(Keys.SHIFT).send_keys(Keys.F9) \
           .key_up(Keys.SHIFT).key_up(Keys.CONTROL).perform()
    time.sleep(2)
    click_run_anyway(driver)
    print("✅ Run All sent!")

    time.sleep(10)
    driver.save_screenshot("final_state.png")
    print("📸 Final screenshot saved.")
    print("\n🟢 Done!")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    if driver:
        try:
            driver.save_screenshot("error_screenshot.png")
            print("📸 Error screenshot saved.")
        except Exception:
            pass
    raise

finally:
    try:
        if driver:
            driver.quit()
        print("🛑 Browser closed.")
    except Exception:
        pass
