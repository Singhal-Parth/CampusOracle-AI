"""
Backend verification script - run this to diagnose issues.
Usage: python check_backend.py
"""

import requests
import sys

BACKEND_URL = "http://localhost:8000"

def check_port_8000():
    """Check if port 8000 is in use."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', 8000))
    sock.close()
    return result == 0

def test_health_endpoint():
    """Test /health endpoint."""
    try:
        resp = requests.get(f"{BACKEND_URL}/health", timeout=5)
        print(f"✅ /health endpoint: {resp.status_code}")
        print(f"   Response: {resp.json()}")
        return True
    except requests.exceptions.ConnectionError:
        print("❌ /health endpoint: Connection refused")
        return False
    except Exception as e:
        print(f"❌ /health endpoint: {e}")
        return False

def test_llm_status():
    """Test /llm-status endpoint."""
    try:
        resp = requests.get(f"{BACKEND_URL}/llm-status", timeout=30)
        print(f"✅ /llm-status endpoint: {resp.status_code}")
        print(f"   Response: {resp.json()}")
        return True
    except requests.exceptions.ReadTimeout:
        print("⏱️ /llm-status endpoint: Timeout (LLM initializing?)")
        return False
    except Exception as e:
        print(f"❌ /llm-status endpoint: {e}")
        return False

def main():
    print("=" * 60)
    print("Backend Connection Diagnostic")
    print("=" * 60)
    
    print("\n1. Checking if port 8000 is open...")
    if not check_port_8000():
        print("❌ Port 8000 is not open!")
        print("\n🔧 Fix: Start the backend with:")
        print("   uvicorn main:app --reload --host 0.0.0.0 --port 8000")
        sys.exit(1)
    else:
        print("✅ Port 8000 is open")
    
    print("\n2. Testing /health endpoint...")
    if not test_health_endpoint():
        print("\n❌ Backend is running but not responding correctly")
        sys.exit(1)
    
    print("\n3. Testing /llm-status endpoint...")
    test_llm_status()
    
    print("\n" + "=" * 60)
    print("✅ Backend diagnostic complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()
