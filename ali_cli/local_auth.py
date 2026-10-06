"""Visible local Playwright login. Credentials never leave Alibaba's login origin."""

import re
import time
from urllib.parse import urlsplit

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from ali_cli.config import get_email, local_credentials

LOGIN_URL = "https://login.alibaba.com/newlogin/icbuLogin.htm"
MESSENGER_URL = "https://message.alibaba.com/message/messenger.htm"


def is_login_origin(url):
    parsed = urlsplit(url)
    return parsed.scheme == "https" and parsed.hostname == "login.alibaba.com"


def login_form(page):
    for frame in page.frames:
        if is_login_origin(frame.url):
            return frame
    return None


def verification_pending(page):
    return any(
        is_login_origin(frame.url) and "/punish" in urlsplit(frame.url).path
        for frame in page.frames
    )


def unique_visible(locator):
    """Never guess between multiple form fields or submit controls."""
    visible = [item for item in locator.all() if item.is_visible()]
    return visible[0] if len(visible) == 1 else None


def authenticated(page):
    """Require an authenticated API response, not just a non-login URL."""
    if urlsplit(page.url).hostname != "message.alibaba.com":
        return False
    try:
        return page.evaluate("""async () => {
            try {
                const token = document.cookie.split(';').map(x => x.trim())
                    .find(x => x.startsWith('_tb_token_='))?.split('=')[1] || '';
                const response = await fetch(
                    'https://onetalk.alibaba.com/message/manager/unread.htm?ctoken=' + encodeURIComponent(token),
                    {credentials: 'include', signal: AbortSignal.timeout(5000)});
                const result = await response.json();
                return result?.data?.hasLogin === true;
            } catch (_) { return false; }
        }""") is True
    except PlaywrightError:
        return False


def complete_login(page, email, password, timeout=180, manual=False, log=print):
    """One automatic credential submission, then allow manual OTP/CAPTCHA handling."""
    page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
    deadline = time.monotonic() + timeout
    identifier_submitted = False
    password_submitted = False
    notified = False
    verification_notified = False
    last_probe = 0.0
    log("Local browser opened. Complete any verification/OTP manually in this window.")
    while time.monotonic() < deadline:
        if page.is_closed():
            raise RuntimeError("Login window was closed; session was not saved.")
        host = urlsplit(page.url).hostname or ""
        if host == "message.alibaba.com" and time.monotonic() - last_probe > 3:
            last_probe = time.monotonic()
            if authenticated(page):
                return
        elif host in {"www.alibaba.com", "i.alibaba.com", "myaccount.alibaba.com"}:
            page.goto(MESSENGER_URL, wait_until="domcontentloaded", timeout=30000)
            continue

        frame = login_form(page)
        if verification_pending(page) and not verification_notified:
            log("Alibaba requires verification: move the 'Please slide to verify' slider manually in the browser.")
            verification_notified = True
        if frame and not manual:
            try:
                identifier = unique_visible(frame.locator(
                    'input[type="email"], input[autocomplete="username"], '
                    'input[name="email"], '
                    'input[name="loginId"], input[name="account"], '
                    'input[placeholder*="email" i], input[placeholder*="e-mail" i]'
                ))
                if identifier and not identifier_submitted:
                    if not is_login_origin(frame.url):
                        raise RuntimeError("Login origin changed.")
                    identifier.fill(email, timeout=3000)
                    if identifier.input_value() != email or not is_login_origin(frame.url):
                        raise RuntimeError("Login identifier could not be verified.")
                    button = unique_visible(frame.get_by_role(
                        "button", name=re.compile(r"^(continue|next|dalej|kontynuuj)$", re.I)))
                    if button:
                        # Mark before clicking; never repeat a submission after a timeout.
                        identifier_submitted = True
                        button.click(timeout=3000)
                        log("Login entered; waiting for password form or verification.")
                        # React replaces the identifier form after Continue.
                        # Resolve the new DOM on the next loop, not through old locators.
                        continue
                    elif frame.locator('input[type="password"]:visible').count():
                        identifier_submitted = True

                field = unique_visible(frame.locator('input[type="password"]'))
                if field and password and identifier_submitted and not password_submitted:
                    # If the user changed the identifier, do not submit the stored password.
                    if identifier and identifier.input_value() != email:
                        raise RuntimeError("Login identifier changed; enter credentials manually.")
                    if not is_login_origin(frame.url):
                        raise RuntimeError("Password submission blocked outside Alibaba login.")
                    button = unique_visible(frame.get_by_role(
                        "button", name=re.compile(r"^(sign in|log in|login|zaloguj się|zaloguj)$", re.I)))
                    if button:
                        field.fill(password, timeout=3000)
                        if not is_login_origin(frame.url):
                            raise RuntimeError("Login origin changed before submission.")
                        password_submitted = True
                        button.click(timeout=3000)
                        log("Password submitted once. Waiting for Alibaba to confirm login.")
            except PlaywrightError:
                # Do not expose Playwright call logs (they may include form values).
                manual = True
                log("Form changed or navigation interrupted. Continue manually in the browser.")

        if not notified and (password_submitted or manual or not password):
            log("If a code or CAPTCHA appears, complete it manually. No mailbox access is used.")
            notified = True
        page.wait_for_timeout(500)
    if verification_pending(page):
        raise RuntimeError(
            "Alibaba verification is still pending. Run 'ali login --timeout 300' "
            "and move the verification slider manually in the local window. Session was not saved."
        )
    raise RuntimeError(
        "Login not confirmed before timeout. Run 'ali login --timeout 300' "
        "and complete any verification in the browser. Existing session was preserved."
    )


def local_login(email=None, timeout=180, manual=False, console=None):
    """Use a fresh local context so a different saved account cannot be reused."""
    email = get_email(email)
    configured_email, password = local_credentials()
    if email.casefold() != configured_email.casefold():
        password = ""  # Never pair another account with the .env password.
    log = console.print if console else print
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            try:
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                page = context.new_page()
                complete_login(page, email, password, timeout, manual, log)
                return context.storage_state(), context.cookies()
            finally:
                browser.close()
    except PlaywrightError:
        raise RuntimeError(
            "Local Playwright browser failed. Check the desktop/display and run "
            "'playwright install chromium'. No session was saved."
        ) from None
