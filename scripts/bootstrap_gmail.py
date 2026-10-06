"""The local Playwright edition does not request access to any mailbox."""


def main():
    print("Gmail OAuth is disabled. Run 'ali login' and enter any verification code manually.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
