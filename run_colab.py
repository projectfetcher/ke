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
from urllib.parse import quote

# ==================== CREDENTIALS ====================
GOOGLE_EMAIL        = os.environ["GOOGLE_EMAIL"]
GOOGLE_APP_PASSWORD = os.environ["GOOGLE_APP_PASSWORD"]
NOTEBOOK_URL        = os.environ["NOTEBOOK_URL"]

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
    options.add_argument("--lang=en-US,en;q=0.9")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Persistent profile — after first successful login, reused on every run
    profile_dir = os.path.join(os.path.expanduser("~"), ".chrome_profile_colab")
    os.makedirs(profile_dir, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_dir}")

    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)

    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins',   {get: () => [1,2,3,4,5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US','en']});
        """
    })
    return driver


# ==================== HELPERS ====================
def find_field(driver, selectors, timeout=25, label="field"):
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
        time.sleep(0.4)
    driver.save_screenshot(f"timeout_{label.replace(' ', '_')}.png")
    raise TimeoutError(f"Field not found: {label}")


def js_set_value(driver, element, value):
    """Set an input's value via JS and fire React/Angular change events."""
    driver.execute_script("arguments[0].value = arguments[1];", element, value)
    driver.execute_script("""
        var el = arguments[0];
        ['input', 'change', 'blur'].forEach(function(evt) {
            el.dispatchEvent(new Event(evt, {bubbles: true}));
        });
    """, element)


def wait_away_from(driver, fragment, timeout=25):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if fragment not in driver.current_url:
            return True
        time.sleep(0.5)
    return False


def dismiss_prompts(driver):
    xpaths = [
        "//button[.//span[contains(text(),'Not now')]]",
        "//button[.//span[contains(text(),'Skip')]]",
        "//button[.//span[contains(text(),'Cancel')]]",
        "//div[@role='button'][contains(.,'Not now')]",
    ]
    for _ in range(6):
        hit = False
        for xp in xpaths:
            try:
                btn = driver.find_element(By.XPATH, xp)
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    print("   ⏭️  Dismissed extra prompt")
                    time.sleep(2)
                    hit = True
                    break
            except Exception:
                pass
        if not hit:
            break


def click_run_anyway(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "mwc-dialog"))
        )
        btn = driver.execute_script("""
            const d = document.querySelector('mwc-dialog');
            if (!d) return null;
            const b = d.querySelector('md-text-button:nth-child(3)');
            return b ? b.shadowRoot.querySelector('#button') : null;
        """)
        target = btn or driver.find_element(
            By.CSS_SELECTOR, "body > mwc-dialog > md-text-button:nth-child(3)")
        driver.execute_script("arguments[0].click();", target)
        print("   ✅ 'Run anyway' clicked!")
        time.sleep(2)
    except Exception as e:
        print(f"   ℹ️  No popup ({type(e).__name__})")


# ==================== LOGIN ====================
def login(driver):
    encoded_email = quote(GOOGLE_EMAIL)

    # ── Phase A: email ──────────────────────────────────────────────────────
    # Load sign-in page with ?Email= pre-filled so we never type in the field.
    # This avoids the keystroke-pattern detection that causes /rejected.
    print("\n📧 Login Phase A — pre-filled email URL...")
    url = (
        "https://accounts.google.com/signin/v2/identifier"
        f"?Email={encoded_email}"
        "&flowName=GlifWebSignIn&flowEntry=ServiceLogin"
    )
    driver.get(url)
    time.sleep(random.uniform(3, 5))
    driver.save_screenshot("phaseA_loaded.png")
    print(f"   URL: {driver.current_url}")

    # If the field isn't pre-filled (some Google flows ignore ?Email=), set it via JS
    try:
        email_field = driver.find_element(By.ID, "identifierId")
        val = email_field.get_attribute("value") or ""
        if not val.strip():
            print("   📝 Field empty — setting via JS (no keystrokes)...")
            js_set_value(driver, email_field, GOOGLE_EMAIL)
            time.sleep(0.5)
        else:
            print(f"   ✅ Pre-filled with: {val}")
    except Exception:
        pass

    # Click Next
    try:
        next_btn = find_field(driver, [
            (By.ID, "identifierNext"),
            (By.CSS_SELECTOR, "#identifierNext button"),
        ], timeout=8, label="email Next")
        driver.execute_script("arguments[0].click();", next_btn)
    except Exception:
        print("   ⚠️  Next not found — pressing Enter")
        try:
            driver.find_element(By.ID, "identifierId").send_keys(Keys.RETURN)
        except Exception:
            pass

    time.sleep(random.uniform(4, 6))
    driver.save_screenshot("phaseA_after_next.png")
    print(f"   URL after email Next: {driver.current_url}")

    if "rejected" in driver.current_url:
        raise Exception(
            "Google rejected the email step — account flagged for automation.\n"
            "Fix: log in once manually in a real browser, export/commit the Chrome\n"
            "profile directory (~/.chrome_profile_colab) as a GitHub Actions cache\n"
            "or artifact, then restore it at the start of the workflow.\n"
            "See phaseA_after_next.png for details."
        )

    # ── Phase B: password ───────────────────────────────────────────────────
    print("\n🔑 Login Phase B — entering App Password via JS...")

    pw_field = find_field(driver, [
        (By.CSS_SELECTOR, "input[type='password']"),
        (By.NAME, "Passwd"),
        (By.NAME, "password"),
        (By.XPATH, "//input[@autocomplete='current-password']"),
    ], timeout=25, label="password input")

    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", pw_field)
    time.sleep(0.3)

    clean_pw = GOOGLE_APP_PASSWORD.replace(" ", "")
    js_set_value(driver, pw_field, clean_pw)
    time.sleep(random.uniform(0.5, 1.0))

    try:
        pw_next = find_field(driver, [
            (By.ID, "passwordNext"),
            (By.CSS_SELECTOR, "#passwordNext button"),
            (By.XPATH, "//button[.//span[contains(text(),'Next')]]"),
            (By.XPATH, "//button[@type='submit']"),
        ], timeout=8, label="password Next")
        driver.execute_script("arguments[0].click();", pw_next)
    except Exception:
        print("   ⚠️  Password Next not found — pressing Enter")
        pw_field.send_keys(Keys.RETURN)

    print("   ⏳ Waiting for post-password redirect (up to 25s)...")
    wait_away_from(driver, "accounts.google.com/signin", timeout=25)
    time.sleep(3)
    driver.save_screenshot("phaseB_after_password.png")
    print(f"   URL: {driver.current_url}")

    dismiss_prompts(driver)
    driver.save_screenshot("phaseB_after_prompts.png")
    print(f"   URL after prompts: {driver.current_url}")

    if "accounts.google.com" in driver.current_url:
        raise Exception(
            "Login failed — still on accounts.google.com after password.\n"
            "Check phaseB_after_password.png.\n"
            "Possible causes:\n"
            "  • App Password wrong/expired → regenerate at myaccount.google.com/apppasswords\n"
            "  • Google is showing a CAPTCHA or 'verify it's you' prompt"
        )

    print("✅ Logged in successfully!\n")


# ==================== MAIN ====================
driver = None
try:
    print("🌐 Launching Headless Chrome...")
    driver = get_driver()

    # ── Check for existing session first ────────────────────────────────────
    print("\n🔐 Checking for existing session...")
    driver.get("https://myaccount.google.com/")
    time.sleep(4)
    print(f"   URL: {driver.current_url}")

    if "myaccount.google.com" in driver.current_url:
        print("   ✅ Session already active — skipping login")
    else:
        login(driver)

    # ── Open Colab notebook ──────────────────────────────────────────────────
    print("📂 Opening Colab notebook...")
    driver.get(NOTEBOOK_URL)
    print("   ⏳ Waiting 25s for notebook to render...")
    time.sleep(25)
    driver.save_screenshot("notebook_loaded.png")
    print(f"   Title: {driver.title}")
    print(f"   URL:   {driver.current_url}")

    # ── Click individual run buttons ──────────────────────────────────────────
    print("\n🔍 Finding colab-run-button elements...")
    run_buttons = driver.find_elements(By.CSS_SELECTOR, "colab-run-button")
    print(f"   Found {len(run_buttons)} run button(s)")

    for i, btn in enumerate(run_buttons, 1):
        print(f"\n▶️  Cell {i}...")
        clicked = False
        for label, fn in [
            ("shadow root",   lambda b: driver.execute_script("arguments[0].click();",
                                b.shadow_root.find_element(By.CSS_SELECTOR,
                                "#filledCircle, svg, circle, span"))),
            ("JS click",      lambda b: driver.execute_script("arguments[0].click();", b)),
            ("dispatchEvent", lambda b: driver.execute_script("""
                arguments[0].dispatchEvent(new MouseEvent('click',
                    {bubbles:true,cancelable:true,view:window}));""", b)),
        ]:
            try:
                fn(btn)
                print(f"   ✅ Clicked via {label}")
                clicked = True
                break
            except Exception as e:
                print(f"   ⚠️  {label} failed: {e}")

        driver.save_screenshot(f"cell{i}_clicked.png")
        if clicked:
            click_run_anyway(driver)
        time.sleep(2)

    # ── Run All ──────────────────────────────────────────────────────────────
    print("\n🔄 Sending Run All (Ctrl+Shift+F9)...")
    ActionChains(driver) \
        .key_down(Keys.CONTROL).key_down(Keys.SHIFT) \
        .send_keys(Keys.F9) \
        .key_up(Keys.SHIFT).key_up(Keys.CONTROL) \
        .perform()
    time.sleep(3)
    click_run_anyway(driver)
    driver.save_screenshot("run_all_sent.png")
    print("✅ Run All sent!")

    time.sleep(10)
    driver.save_screenshot("final_state.png")
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
