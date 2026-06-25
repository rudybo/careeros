import asyncio, json
import httpx

APP_ID = "3d11c7d2"
APP_KEY = "ae138867968e6d9e0b7eb6542bfed3c3"
BASE = "https://api.adzuna.com/v1/api/jobs/it/search/1"

async def test(what: str, salary_min: int = None):
    params = {"app_id": APP_ID, "app_key": APP_KEY, "what": what, "results_per_page": 5, "sort_by": "relevance"}
    if salary_min:
        params["salary_min"] = salary_min
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(BASE, params=params)
        data = r.json()
        count = data.get("count", 0)
        results = data.get("results", [])
        print(f"\n[{r.status_code}] what='{what}' -> {count} totali")
        for j in results[:3]:
            sal = f"{j.get('salary_min','?')}-{j.get('salary_max','?')}"
            print(f"  - {j.get('title')} @ {j.get('company',{}).get('display_name','?')} | {j.get('location',{}).get('display_name','?')} | {sal}")

# Simulate queries based on CV id=1 skills
asyncio.run(test("Project Management ITIL Service Management"))
asyncio.run(test("IT Manager Project Manager"))
asyncio.run(test("ERP SAP gestione progetti"))
asyncio.run(test("IT Manager remoto"))
