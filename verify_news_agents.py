import httpx
import asyncio
import json

async def test_news_endpoints():
    base_url = "http://localhost:8000/api/news_research"
    endpoints = ["sector", "geopolitical", "national", "world"]
    
    print("Testing Parallel News Research Endpoints...")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        tasks = [client.post(f"{base_url}/{ep}") for ep in endpoints]
        responses = await asyncio.gather(*tasks)
        
        for ep, resp in zip(endpoints, responses):
            if resp.status_code == 200:
                print(f"[SUCCESS] {ep.upper()} Agent returned data.")
                data = resp.json()
                print(f"Agent: {data.get('agent')}")
                # print(f"Research Snippet: {data.get('research')[:100]}...")
            else:
                print(f"[FAILED] {ep.upper()} Agent returned status {resp.status_code}")
                print(f"Error: {resp.text}")

if __name__ == "__main__":
    asyncio.run(test_news_endpoints())
