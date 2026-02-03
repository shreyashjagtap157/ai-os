"""Simple CLI to store secrets in the OS keyring for `ai-os`.

Usage:
  python -m agent.cli.secrets set-api <key>
  python -m agent.cli.secrets set-hmac <key>
"""
import argparse
import sys

try:
    import keyring
except Exception:
    keyring = None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ai-os-secrets")
    sub = parser.add_subparsers(dest="cmd")

    p1 = sub.add_parser("set-api")
    p1.add_argument("value")

    p2 = sub.add_parser("set-hmac")
    p2.add_argument("value")

    args = parser.parse_args(argv)

    if not keyring:
        print("keyring package not available; cannot store secrets", file=sys.stderr)
        return 2

    if args.cmd == "set-api":
        keyring.set_password("ai-os", "api_key", args.value)
        print("Stored api_key in system keyring")
        return 0
    if args.cmd == "set-hmac":
        keyring.set_password("ai-os", "session_hmac_key", args.value)
        print("Stored session_hmac_key in system keyring")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
