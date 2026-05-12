import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==================== CREDENTIALS ====================
# GOOGLE_APP_PASSWORD: Generate at https://myaccount.google.com/apppasswords
#   1. Go to that URL (2FA must be enabled on your account)
#   2. Select app: "Other (Custom name)" → type "Colab Runner" → Generate
#   3. Copy the 16-char password (e.g. "abcd efgh ijkl mnop")
#   4. Store it in GitHub Secrets as GOOGLE_APP_PASSWORD (spaces are fine)
GOOGLE_EMAIL       = os.environ["GOOGLE_EMAIL"]
GOOGLE_APP_PASSWORD = os.environ["GOOGLE_APP_PASSWORD"]   # 16-char App Password
NOTEBOOK_URL       = os.environ["NOTEBOOK_URL"]


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
    # Make the browser look as real as possible
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/124.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    # Remove the webdriver flag that Google detects
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


# ==================== HELPER: find field ====================
def find_field(driver, selectors, timeout=20, label="field"):
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
    raise TimeoutError(f"Field not found: {label}")


# ==================== HELPER: type like a human ====================
def human_type(field, text):
    for char in text:
        field.send_keys(char)
        time.sleep(0.06)


# ==================== HELPER: click run anyway ====================
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
        print(f"   ℹ️  No popup ({type(e).__name__})")


# ==================== MAIN ====================
driver = None
try:
    print("🌐 Launching Headless Chrome...")
    driver = get_driver()

    # ── STEP 1: Google login page ────────────────────────────────────────────
    print("\n🔐 Step 1 — Navigating to Google login...")
    driver.get(
        "https://accounts.google.com/signin/v2/identifier"
        "?flowName=GlifWebSignIn&flowEntry=ServiceLogin"
    )
    time.sleep(4)
    driver.save_screenshot("step1_login_page.png")
    print(f"   Title: {driver.title}")
    print(f"   URL:   {driver.current_url}")

    # ── STEP 2: Enter email ──────────────────────────────────────────────────
    print("\n📧 Step 2 — Entering email...")
    email_field = find_field(driver, [
        (By.ID,           "identifierId"),
        (By.NAME,         "identifier"),
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.XPATH,        "//input[@autocomplete='username']"),
    ], timeout=20, label="email input")

    email_field.click()
    time.sleep(0.3)
    email_field.clear()
    human_type(email_field, GOOGLE_EMAIL)
    time.sleep(0.5)

    try:
        next_btn = find_field(driver, [
            (By.ID,           "identifierNext"),
            (By.CSS_SELECTOR, "#identifierNext button"),
            (By.XPATH,        "//button[.//span[contains(text(),'Next')]]"),
        ], timeout=5, label="email Next button")
        driver.execute_script("arguments[0].click();", next_btn)
    except Exception:
        print("   ⚠️  Next button not found — pressing Enter")
        email_field.send_keys(Keys.RETURN)

    time.sleep(5)
    driver.save_screenshot("step2_after_email.png")
    print(f"   URL: {driver.current_url}")

    # ── STEP 3: Enter App Password ───────────────────────────────────────────
    # Google App Passwords bypass 2FA and all security challenges.
    # The password field looks identical to the normal one — same selectors work.
    print("\n🔑 Step 3 — Entering App Password...")
    print("   ℹ️  Using Google App Password (bypasses 2FA/security challenges)")

    password_field = find_field(driver, [
        (By.CSS_SELECTOR, "input[type='password']"),
        (By.NAME,         "Passwd"),
        (By.NAME,         "password"),
        (By.XPATH,        "//input[@autocomplete='current-password']"),
        (By.XPATH,        "//input[@type='password']"),
    ], timeout=20, label="password input")

    password_field.click()
    time.sleep(0.3)
    password_field.clear()

    # App Passwords are 16 chars — strip spaces Google adds for readability
    clean_app_password = GOOGLE_APP_PASSWORD.replace(" ", "")
    human_type(password_field, clean_app_password)
    time.sleep(0.5)

    try:
        pw_next = find_field(driver, [
            (By.ID,           "passwordNext"),
            (By.CSS_SELECTOR, "#passwordNext button"),
            (By.XPATH,        "//button[.//span[contains(text(),'Next')]]"),
            (By.XPATH,        "//button[@type='submit']"),
        ], timeout=5, label="password Next button")
        driver.execute_script("arguments[0].click();", pw_next)
    except Exception:
        print("   ⚠️  Password Next not found — pressing Enter")
        password_field.send_keys(Keys.RETURN)

    print("⏳ Waiting for login redirect (12s)...")
    time.sleep(12)
    driver.save_screenshot("step3_after_login.png")
    print(f"   URL: {driver.current_url}")

    # App Passwords never trigger 2FA or "verify it's you" screens
    if "accounts.google.com" in driver.current_url:
        print("❌ Still on accounts page — possible causes:")
        print("   • App Password is wrong or expired → regenerate it")
        print("   • 2FA is not enabled on the account (required for App Passwords)")
        print("   • Account doesn't have App Passwords enabled")
        print("   Check step3_after_login.png in Actions artifacts.")
        raise Exception("Login failed with App Password — see screenshot.")

    print("✅ Logged in successfully!\n")

    # ── STEP 4: Open Colab notebook ──────────────────────────────────────────
    print("📂 Step 4 — Opening Colab notebook...")
    driver.get(NOTEBOOK_URL)
    print("⏳ Waiting 20s for notebook to fully render...")
    time.sleep(20)
    driver.save_screenshot("step4_notebook_loaded.png")
    print(f"   Title: {driver.title}")
    print(f"   URL:   {driver.current_url}")

    # ── STEP 5: Click each run button ────────────────────────────────────────
    print("\n🔍 Step 5 — Finding colab-run-button elements...")
    run_buttons = driver.find_elements(By.CSS_SELECTOR, "colab-run-button")
    print(f"   Found {len(run_buttons)} run button(s)")

    for i, btn in enumerate(run_buttons, 1):
        print(f"\n▶️  Cell {i} — attempting click...")
        clicked = False

        try:    # Method 1: shadow root inner element
            shadow = btn.shadow_root
            play   = shadow.find_element(By.CSS_SELECTOR,
                         "#filledCircle, svg, circle, span")
            driver.execute_script("arguments[0].click();", play)
            print(f"   ✅ Cell {i} — clicked via shadow root")
            clicked = True
        except Exception as e:
            print(f"   ⚠️  Shadow root failed: {e}")

        if not clicked:
            try:    # Method 2: JS click on host element
                driver.execute_script("arguments[0].click();", btn)
                print(f"   ✅ Cell {i} — clicked via JS")
                clicked = True
            except Exception as e:
                print(f"   ⚠️  JS click failed: {e}")

        if not clicked:
            try:    # Method 3: dispatchEvent
                driver.execute_script("""
                    arguments[0].dispatchEvent(new MouseEvent('click',
                        {bubbles:true, cancelable:true, view:window}));
                """, btn)
                print(f"   ✅ Cell {i} — clicked via dispatchEvent")
                clicked = True
            except Exception as e:
                print(f"   ❌ All methods failed for Cell {i}: {e}")

        driver.save_screenshot(f"step5_cell{i}_clicked.png")

        if clicked:
            click_run_anyway(driver)
        time.sleep(2)

    # ── STEP 6: Backup Run All (Ctrl+Shift+F9) ───────────────────────────────
    print("\n🔄 Step 6 — Sending Run All (Ctrl+Shift+F9)...")
    ActionChains(driver) \
        .key_down(Keys.CONTROL).key_down(Keys.SHIFT) \
        .send_keys(Keys.F9) \
        .key_up(Keys.SHIFT).key_up(Keys.CONTROL) \
        .perform()
    time.sleep(3)
    click_run_anyway(driver)
    driver.save_screenshot("step6_run_all_sent.png")
    print("✅ Run All sent!")

    time.sleep(10)
    driver.save_screenshot("step7_final_state.png")
    print("\n🟢 All done!")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    if driver:
        try:
            driver.save_screenshot("error_state.png")
            print("📸 Error screenshot saved.")
        except Exception:
            pass
    raise

finally:
    if driver:
        driver.quit()
    print("🛑 Browser closed.")
