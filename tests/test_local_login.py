"""Offline tests: Chromium routes are intercepted; no real credentials or network."""

from unittest.mock import Mock

import pytest
from click.testing import CliRunner
from playwright.sync_api import sync_playwright

from ali_cli import config, local_auth, session_manager
from ali_cli.cli import cli


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body="<html></html>"))
        page = context.new_page()
        yield page
        browser.close()


@pytest.mark.parametrize("url,expected", [
    ("https://login.alibaba.com/newlogin/icbuLogin.htm", True),
    ("http://login.alibaba.com/", False),
    ("https://login.alibaba.com.evil.test/", False),
    ("https://evil.test/login.alibaba.com", False),
])
def test_credentials_only_allowed_on_exact_https_origin(url, expected):
    assert local_auth.is_login_origin(url) is expected


def test_verification_frame_is_reported_without_solving_it():
    page = Mock(frames=[Mock(url="https://login.alibaba.com/xman/_____tmd_____/punish")])
    assert local_auth.verification_pending(page)
    assert page.mock_calls == []


def test_env_literal_password_and_no_environment_mutation(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("LOGIN", raising=False)
    monkeypatch.delenv("PASSWORD", raising=False)
    (tmp_path / ".env").write_text("LOGIN=buyer@example.test\nPASSWORD='pa${HOME} # ss'\n")
    assert config.local_credentials() == ("buyer@example.test", "pa${HOME} # ss")
    assert "PASSWORD" not in config.os.environ


def test_local_form_submission_and_authenticated_response(page):
    page.route(local_auth.LOGIN_URL, lambda route: route.fulfill(content_type="text/html", body="""
        <input type=email id=email><button onclick="
        this.remove();document.querySelector('#password').hidden=false;
        document.querySelector('#signin').hidden=false">Continue</button>
        <input hidden type=password id=password>
        <button hidden id=signin onclick="window.name=JSON.stringify({
        email:document.querySelector('#email').value,
        password:document.querySelector('#password').value});
        location.href='https://message.alibaba.com/message/messenger.htm'">Sign in</button>
    """))
    page.route("https://onetalk.alibaba.com/**", lambda route: route.fulfill(
        content_type="application/json",
        headers={"Access-Control-Allow-Origin": "https://message.alibaba.com",
                 "Access-Control-Allow-Credentials": "true"},
        body='{"data":{"hasLogin":true}}'))
    local_auth.complete_login(page, "buyer@example.test", "literal-password", timeout=8, log=lambda _: None)
    assert local_auth.authenticated(page)
    # No credentials are persisted by the form automation itself.
    assert page.url == local_auth.MESSENGER_URL


def test_non_login_url_is_not_proof_of_authentication(page):
    page.goto("https://www.alibaba.com/")
    assert not local_auth.authenticated(page)
    page.goto(local_auth.MESSENGER_URL)
    assert not local_auth.authenticated(page)


def test_redirect_does_not_receive_password(page):
    page.route(local_auth.LOGIN_URL, lambda route: route.fulfill(content_type="text/html", body="""
        <input type=email><button onclick="location.href='https://untrusted.test/'">Continue</button>
    """))
    page.route("https://untrusted.test/", lambda route: route.fulfill(content_type="text/html", body="""
        <input type=password><button>Sign in</button>
    """))
    with pytest.raises(RuntimeError, match="not confirmed"):
        local_auth.complete_login(page, "buyer@example.test", "private-password", timeout=1, log=lambda _: None)
    assert page.locator('input[type="password"]').input_value() == ""


def test_manual_mode_never_fills_credentials(page):
    page.route(local_auth.LOGIN_URL, lambda route: route.fulfill(content_type="text/html", body="""
        <input type=email><input type=password><button>Sign in</button>
    """))
    with pytest.raises(RuntimeError, match="not confirmed"):
        local_auth.complete_login(page, "buyer@example.test", "private-password", timeout=1,
                                  manual=True, log=lambda _: None)
    assert page.locator('input[type="email"]').input_value() == ""
    assert page.locator('input[type="password"]').input_value() == ""


def test_cli_browser_never_uses_saved_remote_session():
    from ali_cli.browser import BrowserManager
    with pytest.raises(RuntimeError, match="Remote browsers are disabled"):
        BrowserManager(cdp_url="wss://remote.test")


def test_failed_login_preserves_existing_session(tmp_path, monkeypatch):
    state = tmp_path / "state.json"
    state.write_text('{"cookies":[]}')
    monkeypatch.setattr(session_manager, "STATE_FILE", state)
    monkeypatch.setattr(local_auth, "local_login", Mock(side_effect=RuntimeError("verification needed")))
    with pytest.raises(RuntimeError, match="verification needed"):
        session_manager.refresh_login()
    assert state.read_text() == '{"cookies":[]}'


def test_saved_cookies_are_private(tmp_path, monkeypatch):
    monkeypatch.setattr(session_manager, "STATE_FILE", tmp_path / "state.json")
    monkeypatch.setattr(session_manager, "COOKIES_FILE", tmp_path / "cookies.json")
    session_manager.save_state({"cookies": []}, [])
    assert (tmp_path / "state.json").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "cookies.json").stat().st_mode & 0o777 == 0o600


def test_cli_email_override_reaches_local_login(monkeypatch):
    import ali_cli.cli as cli_module
    monkeypatch.setattr(cli_module, "load_config", lambda: {})
    monkeypatch.setattr(cli_module, "save_config", Mock())
    refresh = Mock()
    monkeypatch.setattr(session_manager, "refresh_login", refresh)
    result = CliRunner().invoke(cli, ["login", "--email", "other@example.test", "--manual", "--timeout", "30"])
    assert result.exit_code == 0, result.output
    assert refresh.call_args.kwargs == {"email": "other@example.test", "timeout": 30, "manual": True}


def test_alternate_account_does_not_receive_env_password(monkeypatch):
    monkeypatch.setattr(local_auth, "local_credentials", lambda: ("first@example.test", "private-password"))
    complete = Mock()
    monkeypatch.setattr(local_auth, "complete_login", complete)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        fake = Mock()
        fake.__enter__ = Mock(return_value=fake)
        fake.__exit__ = Mock(return_value=False)
        fake.chromium.launch.return_value = browser
        monkeypatch.setattr(local_auth, "sync_playwright", lambda: fake)
        local_auth.local_login(email="second@example.test")
    assert complete.call_args.args[2] == ""
