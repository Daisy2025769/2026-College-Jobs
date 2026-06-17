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

# Specific role searches at financial firms
FINANCE_SECTOR_SEARCHES = [
    "bank analyst", "bank associate", "investment analyst",
    "asset management analyst", "fund operations", "trade operations",
    "treasury analyst", "risk analyst", "compliance analyst",
    "fintech analyst", "private equity analyst", "capital markets analyst",
    "wealth management analyst", "credit analyst", "equity research",
]

# Finance roles in any company
FINANCE_ROLE_SEARCHES = [
    "finance analyst", "financial analyst", "FP&A",
    "financial planning analyst", "finance operations",
    "management accounting", "corporate finance analyst",
    "finance associate", "accounts analyst",
]

ENTRY_LEVELS = {"Entry Level", "Junior Executive", "Executive"}

# Exclude titles containing these words (case-insensitive)
EXCLUDE_TITLE_KEYWORDS = [
    "insurance agent", "financial advisor", "financial consultant",
    "sales", "agent", "promoter", "freelance", "commission",
    "part-time", "part time", "temporary", "temp ", "contract staff",
]

# Must be full-time employment
EMPLOYMENT_TYPES_ALLOWED = {"Permanent", "Full Time"}


def fetch_jobs(search_term: str, limit: int = 100, max_pages: int = 3) -> list[dict]:
    jobs = []
    for page in range(max_pages):
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
    return jobs


def is_singapore(raw: dict) -> bool:
    address = raw.get("address") or {}
    country = (address.get("country") or "").lower()
    postal = address.get("postalCode") or ""
    # Singapore postal codes are 6 digits; country should be "singapore"
    if country and "singapore" not in country:
        return False
    if postal and not postal.isdigit():
        return False
    return True


def is_full_time(raw: dict) -> bool:
    types = {e.get("employmentType", "") for e in raw.get("employmentTypes", [])}
    return bool(types.intersection(EMPLOYMENT_TYPES_ALLOWED))


def has_excluded_title(title: str) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in EXCLUDE_TITLE_KEYWORDS)


def parse_job(raw: dict, category: str) -> dict | None:
    try:
        title = raw.get("title", "")

        # Exclude unwanted titles
        if has_excluded_title(title):
            return None

        # Full-time only
        if not is_full_time(raw):
            return None

        # Experience filter
        min_exp = raw.get("minimumYearsExperience") or 0
        if min_exp > MAX_EXPERIENCE_YEARS:
            return None

        # Position level filter
        levels = {p.get("position", "") for p in raw.get("positionLevels", [])}
        if levels and not levels.intersection(ENTRY_LEVELS):
            return None

        # Strict Singapore location
        if not is_singapore(raw):
            return None

        posted_str = (raw.get("metadata") or {}).get("createdAt", "")
        expiry_str = (raw.get("metadata") or {}).get("expiryDate", "")
        date_posted = datetime.fromisoformat(posted_str[:10]).date() if posted_str else date.today()
        expiry_date = datetime.fromisoformat(expiry_str[:10]).date() if expiry_str else None

        return {
            "id": raw["uuid"],
            "title": title,
            "company": (raw.get("postedCompany") or {}).get("name", ""),
            "location": "Singapore",
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
    # Upsert in batches of 500 to avoid payload limits
    for i in range(0, len(jobs), 500):
        batch = jobs[i:i + 500]
        supabase.table("sg_finance_jobs").upsert(batch, on_conflict="id").execute()


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
