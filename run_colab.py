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
GOOGLE_EMAIL        = os.environ["GOOGLE_EMAIL"]
GOOGLE_APP_PASSWORD = os.environ["GOOGLE_APP_PASSWORD"]   # 16-char App Password (spaces OK)
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

    # Realistic user-agent (update periodically to stay current)
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    # Suppress automation flags
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    # Use a persistent profile dir so cookies / trust carry over between runs
    profile_dir = os.path.join(os.path.expanduser("~"), ".chrome_profile_colab")
    os.makedirs(profile_dir, exist_ok=True)
    options.add_argument(f"--user-data-dir={profile_dir}")

    service = Service(ChromeDriverManager().install())
    driver  = webdriver.Chrome(service=service, options=options)

    # Patch navigator.webdriver to undefined
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
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


def human_type(field, text):
    """Type with random delays to mimic real typing."""
    for char in text:
        field.send_keys(char)
        time.sleep(random.uniform(0.05, 0.14))


def wait_for_url_change(driver, away_from, timeout=20):
    """Wait until the URL no longer contains `away_from`."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if away_from not in driver.current_url:
            return True
        time.sleep(0.5)
    return False


def handle_extra_challenges(driver):
    """
    After password submission Google may show:
    - 'Try another way' / recovery prompts  → skip / cancel
    - 'Not now' on 2-step prompts
    - Recovery email / phone prompts
    We click through them so we reach myaccount / colab.
    """
    dismiss_xpaths = [
        "//button[.//span[contains(text(),'Not now')]]",
        "//button[.//span[contains(text(),'Skip')]]",
        "//button[.//span[contains(text(),'Cancel')]]",
        "//button[contains(@aria-label,'Close')]",
        "//div[@role='button'][contains(.,'Not now')]",
    ]
    for _ in range(5):
        clicked = False
        for xp in dismiss_xpaths:
            try:
                btn = driver.find_element(By.XPATH, xp)
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    print(f"   ⏭️  Dismissed extra prompt via {xp[:50]}")
                    time.sleep(2)
                    clicked = True
                    break
            except Exception:
                pass
        if not clicked:
            break


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

    # ── STEP 1: Navigate to Google Sign-In ──────────────────────────────────
    print("\n🔐 Step 1 — Navigating to Google login...")
    driver.get(
        "https://accounts.google.com/signin/v2/identifier"
        "?flowName=GlifWebSignIn&flowEntry=ServiceLogin"
    )
    time.sleep(random.uniform(3, 5))
    driver.save_screenshot("step1_login_page.png")
    print(f"   Title: {driver.title}")
    print(f"   URL: {driver.current_url}")

    # If already logged in, jump straight to notebook
    if "myaccount.google.com" in driver.current_url or "colab" in driver.current_url:
        print("   ✅ Already logged in (profile reuse)!")
    else:
        # ── STEP 2: Email ────────────────────────────────────────────────────
        print("\n📧 Step 2 — Entering email...")
        email_field = find_field(driver, [
            (By.ID, "identifierId"),
            (By.NAME, "identifier"),
            (By.CSS_SELECTOR, "input[type='email']"),
            (By.XPATH, "//input[@autocomplete='username']"),
        ], timeout=25, label="email input")

        email_field.click()
        time.sleep(random.uniform(0.3, 0.6))
        email_field.clear()
        human_type(email_field, GOOGLE_EMAIL)
        time.sleep(random.uniform(0.4, 0.8))

        try:
            next_btn = find_field(driver, [
                (By.ID, "identifierNext"),
                (By.CSS_SELECTOR, "#identifierNext button"),
                (By.XPATH, "//button[.//span[contains(text(),'Next')]]"),
            ], timeout=5, label="email Next button")
            driver.execute_script("arguments[0].click();", next_btn)
        except Exception:
            print("   ⚠️  Next button not found — pressing Enter")
            email_field.send_keys(Keys.RETURN)

        time.sleep(random.uniform(4, 6))
        driver.save_screenshot("step2_after_email.png")
        print(f"   URL: {driver.current_url}")

        # ── STEP 3: Password ─────────────────────────────────────────────────
        print("\n🔑 Step 3 — Entering App Password...")
        print("   ℹ️  App Passwords bypass 2FA — no extra verification expected")

        password_field = find_field(driver, [
            (By.CSS_SELECTOR, "input[type='password']"),
            (By.NAME, "Passwd"),
            (By.NAME, "password"),
            (By.XPATH, "//input[@autocomplete='current-password']"),
        ], timeout=25, label="password input")

        # Scroll the field into view before interacting
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", password_field)
        time.sleep(0.3)
        password_field.click()
        time.sleep(random.uniform(0.3, 0.6))
        password_field.clear()

        clean_password = GOOGLE_APP_PASSWORD.replace(" ", "")
        human_type(password_field, clean_password)
        time.sleep(random.uniform(0.4, 0.8))

        try:
            pw_next = find_field(driver, [
                (By.ID, "passwordNext"),
                (By.CSS_SELECTOR, "#passwordNext button"),
                (By.XPATH, "//button[.//span[contains(text(),'Next')]]"),
                (By.XPATH, "//button[@type='submit']"),
            ], timeout=5, label="password Next button")
            driver.execute_script("arguments[0].click();", pw_next)
        except Exception:
            print("   ⚠️  Password Next not found — pressing Enter")
            password_field.send_keys(Keys.RETURN)

        # Wait for redirect — Google may take a few seconds
        print("   ⏳ Waiting for login redirect (up to 20s)...")
        redirected = wait_for_url_change(driver, "accounts.google.com/signin", timeout=20)
        time.sleep(3)
        driver.save_screenshot("step3_after_password.png")
        print(f"   URL: {driver.current_url}")

        # Dismiss any post-login prompts (recovery, 2-step reminders, etc.)
        handle_extra_challenges(driver)
        driver.save_screenshot("step3b_after_prompts.png")
        print(f"   URL after prompts: {driver.current_url}")

        if "accounts.google.com" in driver.current_url:
            page_source_snippet = driver.page_source[:2000]
            print("   📄 Page source snippet:")
            print(page_source_snippet)
            driver.save_screenshot("step3_login_failed.png")
            raise Exception(
                "Login failed — still on accounts.google.com.\n"
                "Possible causes:\n"
                "  • App Password is wrong / expired → regenerate at myaccount.google.com/apppasswords\n"
                "  • 2FA is not enabled on the account (required for App Passwords)\n"
                "  • Google blocked the automated sign-in (check step3_login_failed.png)"
            )

        print("✅ Logged in successfully!\n")

    # ── STEP 4: Open Colab notebook ──────────────────────────────────────────
    print("📂 Step 4 — Opening Colab notebook...")
    driver.get(NOTEBOOK_URL)
    print("   ⏳ Waiting 25s for notebook to fully render...")
    time.sleep(25)
    driver.save_screenshot("step4_notebook_loaded.png")
    print(f"   Title: {driver.title}")
    print(f"   URL: {driver.current_url}")

    # ── STEP 5: Click individual run buttons ──────────────────────────────────
    print("\n🔍 Step 5 — Finding colab-run-button elements...")
    run_buttons = driver.find_elements(By.CSS_SELECTOR, "colab-run-button")
    print(f"   Found {len(run_buttons)} run button(s)")

    for i, btn in enumerate(run_buttons, 1):
        print(f"\n▶️  Cell {i} — attempting click...")
        clicked = False

        try:                                                          # shadow root
            shadow = btn.shadow_root
            play   = shadow.find_element(By.CSS_SELECTOR,
                         "#filledCircle, svg, circle, span")
            driver.execute_script("arguments[0].click();", play)
            print(f"   ✅ Cell {i} — clicked via shadow root")
            clicked = True
        except Exception as e:
            print(f"   ⚠️  Shadow root failed: {e}")

        if not clicked:
            try:                                                      # JS click
                driver.execute_script("arguments[0].click();", btn)
                print(f"   ✅ Cell {i} — clicked via JS")
                clicked = True
            except Exception as e:
                print(f"   ⚠️  JS click failed: {e}")

        if not clicked:
            try:                                                      # dispatchEvent
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

    # ── STEP 6: Run All (Ctrl+Shift+F9) ──────────────────────────────────────
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
