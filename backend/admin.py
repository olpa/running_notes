import argparse
import json
import sys

from database import initialize_database
from users import (
    AmbiguousUserError,
    InvalidEmailError,
    UserAlreadyExistsError,
    UserNotFoundError,
    create_user,
    reset_imap_password,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Running Notes administration commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_user_parser = subparsers.add_parser(
        "create-user",
        help="Create an application user and provision their mailbox",
    )
    create_user_parser.add_argument("email", help="User email address")

    reset_password_parser = subparsers.add_parser(
        "reset-imap-password",
        help="Generate a new IMAP password for a user",
    )
    reset_password_parser.add_argument(
        "identifier",
        help="User email address or IMAP username",
    )

    args = parser.parse_args()

    if args.command == "create-user":
        initialize_database()
        try:
            user = create_user(args.email)
        except InvalidEmailError:
            print("invalid email", file=sys.stderr)
            return 2
        except UserAlreadyExistsError:
            print("user already exists", file=sys.stderr)
            return 1

        print(json.dumps(user, indent=2))
        return 0

    if args.command == "reset-imap-password":
        initialize_database()
        try:
            user = reset_imap_password(args.identifier)
        except UserNotFoundError:
            print("user not found", file=sys.stderr)
            return 1
        except AmbiguousUserError:
            print(
                "email belongs to multiple users; use the IMAP username",
                file=sys.stderr,
            )
            return 2

        print(json.dumps(user, indent=2))
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
