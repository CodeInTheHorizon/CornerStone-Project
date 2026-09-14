"""Run explicitly: python -m app.bootstrap_admin --email existing@example.com.

Does not run migrations or create accounts. Requires the schema already at head.
Never invoked by startup or public registration.
"""
import argparse
import logging
from app.database import SessionLocal
from app.services.account_service import bootstrap_admin

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as db:
        try:
            bootstrap_admin(db, args.email)
        except ValueError as exc:
            parser.exit(1, str(exc) + "\n")
    print("Administrator assigned. Sign in again; previous sessions were revoked.")

if __name__ == "__main__":
    main()
