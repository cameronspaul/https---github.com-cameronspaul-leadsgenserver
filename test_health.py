import requests
import sys

def test_health_endpoint(url):
    """Test the health endpoint of the API"""
    try:
        response = requests.get(f"{url}/api/health")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            print("Health check successful!")
            return True
        else:
            print(f"Health check failed with status code {response.status_code}")
            return False
    except Exception as e:
        print(f"Error connecting to the health endpoint: {e}")
        return False

if __name__ == "__main__":
    # Use command line argument if provided, otherwise use the default URL
    url = sys.argv[1] if len(sys.argv) > 1 else "http://leadsgenserver-production-789f.up.railway.app"
    test_health_endpoint(url)
