# ali-cli — local Playwright edition

This installation runs Chromium on this computer. Login and RFQ posting use a
visible local window. Other operations load the saved local session.
Browser Use accounts/API keys and Gmail API access are not used.

## Install and run

```bash
cd /home/jakub/Dokumenty/OgólnieRepaNasze/MCP_Alibaba_z_githuba
python3 -m venv venv
venv/bin/python -m pip install -e '.[dev]'
venv/bin/playwright install chromium
venv/bin/ali login --timeout 300
venv/bin/ali status --json
```

The project's existing `.env` is read automatically, regardless of the current
working directory. It should contain your **Alibaba** account credentials:

```dotenv
LOGIN=your-alibaba-login
PASSWORD=your-alibaba-password
```

Any mailbox provider supported by your Alibaba account can be used.
If Alibaba requests an email/SMS code or CAPTCHA, complete it yourself in the
visible browser. The program never reads your mailbox. Credentials are sent only
to the HTTPS login.alibaba.com form. The password is attempted once per login run.

Use `venv/bin/ali login --manual --timeout 300` to enter all credentials yourself.
`--email` overrides the configured login; the .env password will not be used for
a different account. A graphical desktop is required for login.
A timeout or closed window does not replace an existing saved session.

## Local files

The default state directory is `.ali-cli/` in this project, not a global home
directory. Override it with `ALI_CLI_HOME` if desired. Login saves `state.json`,
`cookies.json` and `login-status.json`; cookie files have permissions 0600.
The .env password is not copied into config.json.

A login is considered successful only after Alibaba's authenticated messenger
API reports `hasLogin: true`. Reaching a home page alone is not success.
No automatic switch to a remote browser is performed.

## Commands

- `ali login`: local login, manual code/CAPTCHA if required.
- `ali status --json`, `ali health --quick --json`: session diagnostics.
- `ali messages`, `ali conversations`, `ali read`: read buyer communications.
- `ali rfqs`, `ali rfq ID`, `ali rfq-quotes ID`: read RFQs and quotes.
- `ali keepalive`: refresh an authenticated local session.
- `ali logout`: remove local saved session/cookies.
- `ali post-rfq ... --dry-run`: run the existing RFQ flow with local Playwright.
  Actual posting/sending still changes your Alibaba account and is not part of
  installation tests. Local RFQ posting has not been verified against Alibaba.
- `ali browser status`: report local mode; there is no background cloud session.
- `ali otp-watch`: explains manual code entry; it does not access email.

Use `venv/bin/ali --help` for the full command list. Historical documents in
`docs/` describe the upstream cloud version and may not match this local edition.

## Verification

```bash
venv/bin/python -m pytest -q tests/test_local_login.py
venv/bin/python -m pip check
```

The local login tests use intercepted Playwright routes and fake credentials.
They test successful form submission, origin restrictions, session verification,
credential selection, and preservation of saved sessions after failed login.
The upstream `tests/test_e2e.py` is a separate live-account script, not an offline
pytest suite.
