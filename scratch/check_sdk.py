import asyncio
from google import genai
import inspect

async def main():
    client = genai.Client(api_key="EMPTY")
    # Check embed_content
    print(f"embed_content is coroutine: {inspect.iscoroutinefunction(client.aio.models.embed_content)}")
    # Check generate_content
    print(f"generate_content is coroutine: {inspect.iscoroutinefunction(client.aio.models.generate_content)}")
    # Check list
    print(f"list return type check...")
    try:
        res = client.aio.models.list()
        print(f"list returns: {type(res)}")
        # Check if it has __aiter__
        print(f"is async iterable: {hasattr(res, '__aiter__')}")
    except Exception as e:
        print(f"Error checking list: {e}")

if __name__ == "__main__":
    asyncio.run(main())
