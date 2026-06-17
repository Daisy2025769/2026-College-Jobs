import os
import requests
from datetime import date, datetime
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MCF_API = "https://api.mycareersfuture.gov.sg/v2/jobs"
HEADERS = {"User-Agent": "Mozilla/5.0"}
MAX_EXPERIENCE_YEARS = 3

FINANCE_SECTOR_SEARCHES = [
    "banking", "investment", "asset management", "insurance", "fintech",
    "private equity", "hedge fund", "wealth management", "capital markets",
]

FINANCE_ROLE_SEARCHES = [
    "finance analyst", "financial analyst", "FP&A", "financial planning",
    "finance operations", "financial operations", "management accounting",
    "business finance", "corporate finance",
]

ENTRY_LEVELS = {"Entry Level", "Junior Executive", "Executive"}


def fetch_jobs(search_term: str, limit: int = 100) -> list[dict]:
    jobs = []
    page = 0
    while True:
        params = {
            "search": search_term,
            "limit": limit,
            "page": page,
            "sortBy": "new_posting_date",
        }
        resp = requests.get(MCF_API, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            break
        jobs.extend(results)
        if len(results) < limit:
            break
        page += 1
    return jobs


def parse_job(raw: dict, category: str) -> dict | None:
    try:
        # Experience filter
        min_exp = raw.get("minimumYearsExperience") or 0
        if min_exp > MAX_EXPERIENCE_YEARS:
            return None

        # Position level filter
        levels = {p.get("position", "") for p in raw.get("positionLevels", [])}
        if levels and not levels.intersection(ENTRY_LEVELS):
            return None

        # Location — Singapore only
        address = raw.get("address", {}) or {}
        location = address.get("streetName") or "Singapore"
        if "singapore" not in (raw.get("address", {}) or {}).get("country", "Singapore").lower():
            return None

        posted_str = (raw.get("metadata") or {}).get("createdAt", "")
        expiry_str = (raw.get("metadata") or {}).get("expiryDate", "")
        date_posted = datetime.fromisoformat(posted_str[:10]).date() if posted_str else date.today()
        expiry_date = datetime.fromisoformat(expiry_str[:10]).date() if expiry_str else None

        return {
            "id": raw["uuid"],
            "title": raw.get("title", ""),
            "company": (raw.get("postedCompany") or {}).get("name", ""),
            "location": location,
            "url": f"https://www.mycareersfuture.gov.sg/job/{raw['uuid']}",
            "category": category,
            "date_posted": date_posted.isoformat(),
            "expiry_date": expiry_date.isoformat() if expiry_date else None,
            "experience_max": raw.get("minimumYearsExperience"),
        }
    except Exception:
        return None


def upsert_jobs(jobs: list[dict]):
    if not jobs:
        return
    supabase.table("sg_finance_jobs").upsert(jobs, on_conflict="id").execute()


def remove_expired():
    today = date.today().isoformat()
    supabase.table("sg_finance_jobs").delete().lt("expiry_date", today).execute()


def main():
    all_jobs: dict[str, dict] = {}

    print("Fetching financial services jobs...")
    for term in FINANCE_SECTOR_SEARCHES:
        for raw in fetch_jobs(term):
            parsed = parse_job(raw, "financial_services")
            if parsed:
                all_jobs[parsed["id"]] = parsed

    print("Fetching finance role jobs...")
    for term in FINANCE_ROLE_SEARCHES:
        for raw in fetch_jobs(term):
            parsed = parse_job(raw, "finance_role")
            if parsed:
                all_jobs[parsed["id"]] = parsed

    print(f"Upserting {len(all_jobs)} jobs...")
    upsert_jobs(list(all_jobs.values()))

    print("Removing expired jobs...")
    remove_expired()
    print("Done.")


if __name__ == "__main__":
    main()
