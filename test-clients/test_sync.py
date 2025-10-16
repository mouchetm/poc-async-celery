"""
Synchronous test client for the Chat API
Tests basic request/response using requests.post
"""
import requests
import json

API_BASE_URL = "http://localhost:8000"


def test_sync():
    """Test the API synchronously"""

    # 1. Create a new conversation
    print("Creating a new conversation...")
    response = requests.post(
        f"{API_BASE_URL}/conversations",
        json={"title": "Test Conversation"}
    )
    response.raise_for_status()
    conversation = response.json()
    conversation_id = conversation["id"]
    print(f"Created conversation: {conversation_id}")

    # 2. Send a message and stream the response
    print("\nSending a message...")
    message_content = "What is the capital of France?"
    response = requests.post(
        f"{API_BASE_URL}/conversations/{conversation_id}/messages",
        json={"content": message_content},
        stream=True
    )
    response.raise_for_status()

    print(f"User: {message_content}")
    print("Assistant: ", end="", flush=True)

    # Stream the response
    for line in response.iter_lines():
        if line:
            line = line.decode('utf-8')
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
    response = requests.get(f"{API_BASE_URL}/conversations/{conversation_id}")
    response.raise_for_status()
    conversation_data = response.json()
    print(f"Conversation has {len(conversation_data['messages'])} messages")


if __name__ == "__main__":
    test_sync()
