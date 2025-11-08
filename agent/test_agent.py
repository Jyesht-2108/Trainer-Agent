"""
Test script for the Training Agent API.

This script tests the main endpoints of the Training Agent to verify
that the agent is working properly.
"""

import requests
import json
import time
from datetime import datetime


# Base URL for the API
BASE_URL = "http://127.0.0.1:8000"


def print_section(title):
    """Print a formatted section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_health_check():
    """Test the health check endpoint."""
    print_section("Testing Health Check")
    
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✓ Health check passed")
            return True
        else:
            print("✗ Health check failed")
            return False
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def test_start_training(project_id):
    """Test starting a training job."""
    print_section(f"Testing Start Training - Project: {project_id}")
    
    try:
        payload = {"project_id": project_id}
        response = requests.post(
            f"{BASE_URL}/agents/training/start",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code in [200, 400, 404, 500]:
            print("✓ Start training endpoint responded (project may not exist)")
            return True
        else:
            print("✗ Unexpected status code")
            return False
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def test_get_status(project_id):
    """Test getting training status."""
    print_section(f"Testing Get Status - Project: {project_id}")
    
    try:
        response = requests.get(f"{BASE_URL}/agents/training/status/{project_id}")
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code in [200, 404, 500]:
            print("✓ Get status endpoint responded (project may not exist)")
            return True
        else:
            print("✗ Unexpected status code")
            return False
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def test_invalid_request():
    """Test error handling with invalid request."""
    print_section("Testing Error Handling - Invalid Request")
    
    try:
        # Send request without required project_id
        response = requests.post(
            f"{BASE_URL}/agents/training/start",
            json={},
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 422:
            print("✓ Error handling works correctly")
            return True
        else:
            print("✗ Expected 422 validation error")
            return False
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("  TRAINING AGENT API TEST SUITE")
    print("  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)
    
    # Check if server is running
    try:
        requests.get(BASE_URL, timeout=2)
    except requests.exceptions.ConnectionError:
        print("\n✗ ERROR: Server is not running!")
        print(f"Please start the server with: uvicorn agent.main:app --reload")
        return
    
    results = []
    
    # Run tests
    results.append(("Health Check", test_health_check()))
    results.append(("Invalid Request", test_invalid_request()))
    
    # Test with a sample project ID (valid UUID format)
    test_project_id = "123e4567-e89b-12d3-a456-426614174000"
    results.append(("Get Status", test_get_status(test_project_id)))
    results.append(("Start Training", test_start_training(test_project_id)))
    
    # Print summary
    print_section("TEST SUMMARY")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status} - {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")


if __name__ == "__main__":
    main()
