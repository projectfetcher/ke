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
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"}
    )
    return driver
 
# ==================== HELPER: FIND ELEMENT (multiple selectors) ====================
def find_any(driver, selectors, timeout=15):
    """Try multiple selectors until one is found and visible."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        for by, val in selectors:
            try:
                el = driver.find_element(by, val)
                if el.is_displayed():
                    return el
            except:
                pass
        time.sleep(0.5)
    raise TimeoutError(f"None of these selectors found in {timeout}s: {selectors}")
 
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
            host = driver.find_element(By.CSS_SELECTOR,
                "body > mwc-dialog > md-text-button:nth-child(3)")
            driver.execute_script("arguments[0].click();", host)
            print("   ✅ 'Run anyway' clicked via fallback!")
            time.sleep(2)
    except Exception as e:
        print(f"   ℹ️  No popup detected ({type(e).__name__})")
 
# ==================== MAIN ====================
driver = None
try:
    print("🌐 Launching headless Chrome...")
    driver = get_driver()
 
    # ── STEP 1: EMAIL ──────────────────────────────────────
    print("🔐 Navigating to Google login...")
    driver.get("https://accounts.google.com/signin/v2/identifier?flowName=GlifWebSignIn&flowEntry=ServiceLogin")
    time.sleep(4)
    driver.save_screenshot("step1_login_page.png")
    print(f"   URL: {driver.current_url}")
 
    print("📧 Entering email...")
    email_field = find_any(driver, [
        (By.ID,           "identifierId"),
        (By.NAME,         "identifier"),
        (By.CSS_SELECTOR, "input[type='email']"),
    ])
    email_field.click()
    time.sleep(0.5)
    email_field.send_keys(GOOGLE_EMAIL)
    time.sleep(0.5)
 
    next_btn = find_any(driver, [
        (By.ID,           "identifierNext"),
        (By.CSS_SELECTOR, "button[jsname='LgbsSe']"),
        (By.XPATH,        "//button[contains(.,'Next')]"),
        (By.XPATH,        "//span[text()='Next']/ancestor::button"),
    ])
    driver.execute_script("arguments[0].click();", next_btn)
    print("   ✅ Email submitted, waiting for password screen...")
    time.sleep(4)
    driver.save_screenshot("step2_after_email.png")
 
    # ── STEP 2: PASSWORD ───────────────────────────────────
    print("🔑 Entering password...")
    password_field = find_any(driver, [
        (By.NAME,         "Passwd"),
        (By.NAME,         "password"),
        (By.CSS_SELECTOR, "input[type='password']"),
        (By.XPATH,        "//input[@type='password']"),
    ])
    password_field.click()
    time.sleep(0.5)
    password_field.send_keys(GOOGLE_PASSWORD)
    time.sleep(0.5)
 
    signin_btn = find_any(driver, [
        (By.ID,           "passwordNext"),
        (By.CSS_SELECTOR, "button[jsname='LgbsSe']"),
        (By.XPATH,        "//button[contains(.,'Next')]"),
        (By.XPATH,        "//span[text()='Next']/ancestor::button"),
    ])
    driver.execute_script("arguments[0].click();", signin_btn)
    print("   ✅ Password submitted, waiting for redirect...")
    time.sleep(8)
    driver.save_screenshot("step3_after_password.png")
    print(f"   URL: {driver.current_url}")
 
    # ── STEP 3: CHECK LOGIN SUCCESS ────────────────────────
    if "accounts.google.com" in driver.current_url:
        print("❌ Still on Google accounts page — possible causes:")
        print("   • Wrong credentials")
        print("   • Google blocked headless login (check step3_after_password.png)")
        print("   • 2FA required")
        raise SystemExit(1)
 
    print("✅ Logged in!\n")
 
    # ── STEP 4: OPEN NOTEBOOK ──────────────────────────────
    print("📂 Opening Colab notebook...")
    driver.get(NOTEBOOK_URL)
    print("⏳ Waiting 20s for notebook to load...")
    time.sleep(20)
    driver.save_screenshot("step4_notebook.png")
    print(f"✅ Title: {driver.title}\n")
 
    # ── STEP 5: CLICK EACH CELL ────────────────────────────
    print("🔍 Finding colab-run-button elements...")
    run_buttons = driver.find_elements(By.CSS_SELECTOR, "colab-run-button")
    print(f"✅ Found {len(run_buttons)} button(s)\n")
 
    for i, btn in enumerate(run_buttons, 1):
        print(f"\n▶️  Clicking Cell {i}...")
        clicked = False
 
        try:
            shadow = btn.shadow_root
            play = shadow.find_element(By.CSS_SELECTOR, "#filledCircle, svg, circle, span")
            driver.execute_script("arguments[0].click();", play)
            print(f"   ✅ Cell {i} via shadow root!")
            clicked = True
        except Exception as e:
            print(f"   ⚠️  Method 1 failed: {e}")
 
        if not clicked:
            try:
                driver.execute_script("arguments[0].click();", btn)
                print(f"   ✅ Cell {i} via JS click!")
                clicked = True
            except Exception as e:
                print(f"   ⚠️  Method 2 failed: {e}")
 
        if not clicked:
            try:
                driver.execute_script("""
                    arguments[0].dispatchEvent(new MouseEvent('click', {
                        bubbles: true, cancelable: true, view: window
                    }));
                """, btn)
                print(f"   ✅ Cell {i} via dispatchEvent!")
                clicked = True
            except Exception as e:
                print(f"   ⚠️  All methods failed for Cell {i}: {e}")
 
        if clicked:
            click_run_anyway(driver)
        time.sleep(2)
 
    # ── STEP 6: RUN ALL fallback ───────────────────────────
    print("\n" + "=" * 60)
    print("🔄 Sending Ctrl+Shift+F9 (Run All)...")
    ActionChains(driver) \
        .key_down(Keys.CONTROL).key_down(Keys.SHIFT) \
        .send_keys(Keys.F9) \
        .key_up(Keys.SHIFT).key_up(Keys.CONTROL) \
        .perform()
    time.sleep(2)
    click_run_anyway(driver)
    print("✅ Run All sent!")
 
    driver.save_screenshot("step5_after_run.png")
    print("📸 step5_after_run.png saved")
    print("\n🟢 Done!")
 
except SystemExit:
    raise
except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    if driver:
        driver.save_screenshot("error_screenshot.png")
        print("📸 error_screenshot.png saved")
 
finally:
    try:
        if driver:
            driver.quit()
        print("🛑 Browser closed.")
    except:
        pass
