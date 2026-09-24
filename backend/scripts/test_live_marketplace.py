"""Manual, opt-in live collection check; never used by automated tests."""
import argparse
from app.database.session import SessionLocal
from app.services.collection_service import run_collection

parser = argparse.ArgumentParser()
parser.add_argument("--platform", choices=["amazon", "flipkart", "croma", "alibaba"], required=True)
parser.add_argument("--query", required=True)
args = parser.parse_args()
db = SessionLocal()
try:
    result = run_collection(db, platform=args.platform, keyword=args.query)
    print(f"{result.platform}: stored={result.items_collected}, received={result.items_received}, provider={result.provider}")
finally:
    db.close()
