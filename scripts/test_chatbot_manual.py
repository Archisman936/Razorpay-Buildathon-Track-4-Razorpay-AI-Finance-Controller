"""Simple test script for chatbot API."""

import requests
import json

def test_chat_health():
    """Test the chat health endpoint."""
    try:
        response = requests.get("http://127.0.0.1:8000/api/v1/chat/health")
        print(f"Health check status: {response.status_code}")
        print(f"Health check response: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

def test_chat_message():
    """Test the chat message endpoint."""
    try:
        response = requests.post(
            "http://127.0.0.1:8000/api/v1/chat/message",
            json={"message": "What is settlement reconciliation?"}
        )
        print(f"Chat message status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"Chat message response: {json.dumps(data, indent=2)}")
            return True
        else:
            print(f"Error response: {response.text}")
            return False
    except Exception as e:
        print(f"Chat message failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Chatbot API...")
    print("=" * 50)
    
    # Test health
    health_ok = test_chat_health()
    print()
    
    # Test chat message
    chat_ok = test_chat_message()
    print()
    
    if health_ok and chat_ok:
        print("All tests passed")
    else:
        print("Some tests failed")