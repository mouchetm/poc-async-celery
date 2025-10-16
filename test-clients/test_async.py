"""
Asynchronous test client for the Chat API
Tests async requests using aiohttp
"""
import asyncio
import aiohttp
import json

API_BASE_URL = "http://localhost:8000"


async def test_async():
    """Test the API asynchronously"""

    async with aiohttp.ClientSession() as session:
        # 1. Create a new conversation
        print("Creating a new conversation...")
        async with session.post(
            f"{API_BASE_URL}/conversations",
            json={"title": "Async Test Conversation"}
        ) as response:
            conversation = await response.json()
            conversation_id = conversation["id"]
            print(f"Created conversation: {conversation_id}")

        # 2. Send a message and stream the response
        print("\nSending a message...")
        message_content = "Explain quantum computing in one sentence."

        async with session.post(
            f"{API_BASE_URL}/conversations/{conversation_id}/messages",
            json={"content": message_content}
        ) as response:
            print(f"User: {message_content}")
            print("Assistant: ", end="", flush=True)

            # Stream the response
            async for line in response.content:
                line = line.decode('utf-8').strip()
                if line.startswith('data: '):
                    data = json.loads(line[6:])
                    if 'content' in data:
                        print(data['content'], end="", flush=True)
                    elif 'done' in data:
                        print("\n\nResponse complete!")
                    elif 'error' in data:
                        print(f"\nError: {data['error']}")

        # 3. Get the conversation to verify messages were saved
        print(f"\nFetching conversation {conversation_id}...")
        async with session.get(
            f"{API_BASE_URL}/conversations/{conversation_id}"
        ) as response:
            conversation_data = await response.json()
            print(f"Conversation has {len(conversation_data['messages'])} messages")


if __name__ == "__main__":
    asyncio.run(test_async())
