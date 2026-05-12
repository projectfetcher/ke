import time
import os
import random
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
GOOGLE_EMAIL = os.environ["GOOGLE_EMAIL"]
GOOGLE_APP_PASSWORD = os.environ["GOOGLE_APP_PASSWORD"]
NOTEBOOK_URL = os.environ["NOTEBOOK_URL"]

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
    options.add_argument("--lang=en-US")
    
    # Strong anti-detection
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36")
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--disable-web-security")
    options.add_argument("--allow-running-insecure-content")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    # Hide automation flags
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ["en-US", "en"]});
            Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
        """
    })
    return driver


# ==================== HELPERS ====================
def find_field(driver, selectors, timeout=20, label="field"):
    print(f" 🔍 Looking for: {label}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        for by, val in selectors:
            try:
                el = driver.find_element(by, val)
                if el.is_displayed() and el.is_enabled():
                    print(f" ✅ Found '{label}' via {by}='{val}'")
                    return el
            except:
                pass
        time.sleep(0.5)
    driver.save_screenshot(f"timeout_{label.replace(' ', '_')}.png")
    raise TimeoutError(f"Field not found: {label}")


def human_type(field, text):
    for char in text:
        field.send_keys(char)
        time.sleep(random.uniform(0.05, 0.12))


def click_run_anyway(driver):
    print(" 🔍 Checking for 'Run anyway' popup...")
    try:
        WebDriverWait(driver, 6).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "mwc-dialog"))
        )
        driver.execute_script("""
            const btns = document.querySelectorAll('md-text-button');
            for (let btn of btns) {
                if (btn.textContent.includes('Run anyway') || btn.textContent.includes('Continue')) {
                    btn.click();
                    return true;
                }
            }
        """)
        print(" ✅ 'Run anyway' clicked!")
        time.sleep(3)
    except:
        print(" ℹ️ No 'Run anyway' popup detected")


# ==================== MAIN ====================
driver = None
try:
    print("🌐 Launching Headless Chrome...")
    driver = get_driver()

    # ── STEP 1: Go to Google Login ─────────────────────────────────────
    print("\n🔐 Step 1 — Navigating to Google login...")
    driver.get("https://accounts.google.com/signin/v2/identifier?flowName=GlifWebSignIn&flowEntry=ServiceLogin")
    time.sleep(5)

    # ── STEP 2: Enter Email ────────────────────────────────────────────
    print("\n📧 Step 2 — Entering email...")
    email_field = find_field(driver, [
        (By.ID, "identifierId"),
        (By.CSS_SELECTOR, "input[type='email']"),
        (By.NAME, "identifier")
    ], timeout=15, label="email input")

    email_field.click()
    time.sleep(0.5)
    email_field.clear()
    human_type(email_field, GOOGLE_EMAIL)
    time.sleep(1)

    try:
        next_btn = find_field(driver, [(By.ID, "identifierNext"), (By.CSS_SELECTOR, "#identifierNext button")], 
                            timeout=8, label="email Next")
        driver.execute_script("arguments[0].click();", next_btn)
    except:
        email_field.send_keys(Keys.RETURN)

    time.sleep(6)

    # ── STEP 3: Enter App Password ─────────────────────────────────────
    print("\n🔑 Step 3 — Entering App Password...")
    password_field = find_field(driver, [
        (By.CSS_SELECTOR, "input[type='password']"),
        (By.NAME, "Passwd"),
        (By.NAME, "password")
    ], timeout=20, label="password input")

    password_field.click()
    time.sleep(0.8)
    password_field.clear()
    
    clean_password = GOOGLE_APP_PASSWORD.replace(" ", "")
    human_type(password_field, clean_password)
    time.sleep(1.2)

    try:
        pw_next = find_field(driver, [
            (By.ID, "passwordNext"),
            (By.CSS_SELECTOR, "#passwordNext button"),
            (By.XPATH, "//button[contains(., 'Next')]")
        ], timeout=10, label="password Next")
        driver.execute_script("arguments[0].click();", pw_next)
    except:
        password_field.send_keys(Keys.RETURN)

    print("⏳ Waiting for login redirect (18 seconds)...")
    time.sleep(18)
    driver.save_screenshot("after_login.png")

    if "accounts.google.com" in driver.current_url and "/challenge/" in driver.current_url:
        print("❌ Still on Google challenge page. Login failed.")
        print("   Try regenerating App Password and make sure 2FA is enabled.")
        raise Exception("Login failed - still on challenge page")
    
    print("✅ Logged in successfully!\n")

    # ── STEP 4: Open Colab Notebook ────────────────────────────────────
    print("📂 Step 4 — Opening Colab notebook...")
    driver.get(NOTEBOOK_URL)
    print("⏳ Waiting 25s for notebook to load...")
    time.sleep(25)
    driver.save_screenshot("notebook_loaded.png")

    # ── STEP 5: Click Run buttons ──────────────────────────────────────
    print("\n🔍 Step 5 — Running all cells...")
    run_buttons = driver.find_elements(By.CSS_SELECTOR, "colab-run-button")
    print(f" Found {len(run_buttons)} run button(s)")

    for i, btn in enumerate(run_buttons, 1):
        print(f"▶️ Running cell {i}...")
        try:
            driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
            click_run_anyway(driver)
        except:
            print(f" ⚠️ Failed to click cell {i}")
        time.sleep(3)

    # ── STEP 6: Run All as backup ──────────────────────────────────────
    print("\n🔄 Sending Run All (Ctrl + Shift + F9)...")
    ActionChains(driver)\
        .key_down(Keys.CONTROL).key_down(Keys.SHIFT)\
        .send_keys(Keys.F9)\
        .key_up(Keys.SHIFT).key_up(Keys.CONTROL)\
        .perform()
    
    time.sleep(8)
    click_run_anyway(driver)
    driver.save_screenshot("final_state.png")

    print("\n🟢 All done! Notebook execution started.")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    if driver:
        try:
            driver.save_screenshot("error_screenshot.png")
            print("📸 Error screenshot saved.")
        except:
            pass
    raise

finally:
    if driver:
        driver.quit()
    print("🛑 Browser closed.")
