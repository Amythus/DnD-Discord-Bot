import asyncio
from pathlib import Path
import httpx

""" Command to pull bestiary.json script
docker exec -it dnd_discord_bot python -m database.seed.pull_bestiary
"""

# Homebrew 5etools mirror
# https://github.com/TheGiddyLimit/homebrew/tree/master/collection


# Target Repository Parameters
REPO_OWNER = "5etools-mirror-3"
REPO_NAME = "5etools-src"
DIRECTORY_PATH = "data/bestiary"
BRANCH = "main"

LOCAL_OUTPUT_DIR = Path(__file__).resolve().parent / "bestiary"

async def fetch_bestiary_directory_manifest(client: httpx.AsyncClient) -> list:
    """Queries the GitHub API to get a list of all files in the target folder."""
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{DIRECTORY_PATH}?ref={BRANCH}"
    
    # Custom headers protect against aggressive rate limiting on anonymous API requests
    headers = {"User-Agent": "Dnd-Bot-Ingestion-Pipeline"}
    
    print(f"📡 Scanning remote repository directory layout via GitHub API...")
    response = await client.get(api_url, headers=headers, timeout=15.0)
    response.raise_for_status()
    
    return response.json()

async def download_raw_file(client: httpx.AsyncClient, file_metadata: dict) -> None:
    """Downloads an individual file directly from GitHub's raw storage CDN."""
    file_name = file_metadata["name"]
    download_url = file_metadata["download_url"]
    local_path = LOCAL_OUTPUT_DIR / file_name

    # Optimization: Filter out directory indexes, legends, or non-bestiary files
    if not file_name.startswith("bestiary-") or not file_name.endswith(".json"):
        return

    # Skip index/meta compilation files if you only want true creature arrays
    if "index" in file_name or "meta" in file_name:
        return

    try:
        print(f"📥 Downloading: {file_name}...")
        file_response = await client.get(download_url, timeout=30.0)
        file_response.raise_for_status()
        
        # Atomically write bytes into the target local directory folder
        local_path.write_bytes(file_response.content)
        print(f"✅ Saved locally: {file_name}")
        
    except Exception as e:
        print(f"❌ Failed to download reference asset {file_name}: {str(e)}")

async def sync_entire_bestiary() -> None:
    """Orchestrates directory discovery and schedules concurrent downloads."""
    LOCAL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    async with httpx.AsyncClient() as client:
        try:
            # 1. Discover what files exist on the branch
            directory_contents = await fetch_bestiary_directory_manifest(client)
            
            # 2. Filter and fire downloads concurrently to bypass I/O bottlenecks
            tasks = [
                download_raw_file(client, item) 
                for item in directory_contents 
                if item["type"] == "file"
            ]
            
            if not tasks:
                print("⚠️ No matching bestiary files discovered in the target repository layout.")
                return
                
            print(f"⚡ Batch pipeline ready. Syncing {len(tasks)} targeted bestiary targets...")
            await asyncio.gather(*tasks)
            print(f"\n🎉 Sync Complete! All source files successfully pulled to: {LOCAL_OUTPUT_DIR}")
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                print("❌ GitHub API Rate Limit Exceeded. Try authenticating or downloading later.")
            else:
                print(f"❌ HTTP Directory Scan Failure: Status {e.response.status_code}")
        except Exception as e:
            print(f"❌ Pipeline Critical Ingestion Failure: {str(e)}")

if __name__ == "__main__":
    asyncio.run(sync_entire_bestiary())