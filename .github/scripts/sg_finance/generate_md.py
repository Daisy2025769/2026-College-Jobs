import os
from datetime import date
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MD_PATH = os.path.join(os.path.dirname(__file__), "../../../SG_FINANCE_OPS_GRAD.md")


def age_label(date_posted_str: str) -> str:
    posted = date.fromisoformat(date_posted_str)
    days = (date.today() - posted).days
    return f"{days}d"


def fetch(category: str) -> list[dict]:
    resp = (
        supabase.table("sg_finance_jobs")
        .select("*")
        .eq("category", category)
        .order("date_posted", desc=True)
        .execute()
    )
    return resp.data or []


def make_table(jobs: list[dict]) -> str:
    if not jobs:
        return "_No positions found._\n"
    header = "| Company | Position | Location | Posting | Age |\n|---|---|---|---|---|\n"
    rows = ""
    for j in jobs:
        apply = f'<a href="{j["url"]}"><img src="https://i.imgur.com/JpkfjIq.png" alt="Apply" width="70"/></a>'
        rows += f'| **{j["company"]}** | {j["title"]} | {j["location"]} | {apply} | {age_label(j["date_posted"])} |\n'
    return header + rows


def main():
    fin_jobs = fetch("financial_services")
    role_jobs = fetch("finance_role")

    total = len(fin_jobs) + len(role_jobs)
    today = date.today().strftime("%d %b %Y")

    content = f"""## SG Finance & Operations Jobs — New Grad / Under 3 Years Experience

> Updated daily · Last updated: {today} · **{total}** open positions

---

### Financial Services (Banks, Asset Mgmt, Insurance, FinTech)

<!-- FS_TABLE_START -->
{make_table(fin_jobs)}
<!-- FS_TABLE_END -->

---

### Finance Roles in Non-Financial Companies (FP&A, Finance Analyst, Finance Ops)

<!-- ROLE_TABLE_START -->
{make_table(role_jobs)}
<!-- ROLE_TABLE_END -->

---
<a name="bottom"></a>
*Source: [MyCareersFuture.sg](https://www.mycareersfuture.gov.sg) · Jobs expire automatically when closed*
"""

    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Written {total} jobs to SG_FINANCE_OPS_GRAD.md")


if __name__ == "__main__":
    main()
