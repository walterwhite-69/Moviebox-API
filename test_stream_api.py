import asyncio
from api import get_stream_sources

async def run():
    detail_path = "attack-on-titan-hindi-kGWQOIx0d4"
    subject_id = "56988683026712168"
    
    print(f"Testing stream for {detail_path} (subject: {subject_id})")
    try:
        res = await get_stream_sources(subject_id, detail_path, se=1, ep=1)
        import json
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run())
