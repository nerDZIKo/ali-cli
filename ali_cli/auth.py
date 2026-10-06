"""Compatibility entry point for the local login implementation.

The former Browser Use/Gmail integration has been removed in this installation.
"""

from ali_cli.local_auth import local_login


def browser_login(cdp_url=None, email=None, console=None):
    if cdp_url:
        raise RuntimeError("Remote browsers are disabled. Run 'ali login' locally.")
    return local_login(email=email, console=console)


def get_gmail_service():
    raise RuntimeError("Mailbox access is disabled. Enter verification codes in the local browser.")
