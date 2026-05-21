import json
import requests
import os
from tesla_gem import load_dotenv

# Load environment variables from .env
load_dotenv()

CLIENT_ID = os.getenv('TESLA_CLIENT_ID', '')
CLIENT_SECRET = os.getenv('TESLA_CLIENT_SECRET', '')
TOKEN_URL = os.getenv('TESLA_TOKEN_URL', 'https://auth.tesla.com/oauth2/v3/token')
BASE_URL = os.getenv('TESLA_BASE_URL', 'https://fleet-api.prd.na.vn.cloud.tesla.com/')

if not CLIENT_ID or not CLIENT_SECRET:
    print("Error: Both TESLA_CLIENT_ID and TESLA_CLIENT_SECRET must be configured in your .env file.")
    exit(1)

# Step 1: Automatically fetch a Partner Token (Machine-to-Machine)
print("Requesting a Partner Authentication Token (Machine-to-Machine)...")
token_payload = {
    'grant_type': 'client_credentials',
    'client_id': CLIENT_ID,
    'client_secret': CLIENT_SECRET,
    'scope': 'openid offline_access'
}

token_resp = requests.post(TOKEN_URL, data=token_payload)
if token_resp.status_code != 200:
    print(f"Error fetching partner token: Status {token_resp.status_code}")
    print(token_resp.text)
    exit(1)

partner_token = token_resp.json().get('access_token')
print("Successfully obtained Partner Token.\n")

# Step 2: Register Domain
allowed_origin = os.getenv('TESLA_ALLOWED_ORIGIN', '')
if not allowed_origin:
    allowed_origin = input("Enter your GitHub Pages domain (e.g. yourname.github.io):\n").strip()

# Strip schema if entered
domain = allowed_origin.replace("https://", "").replace("http://", "").split("/")[0]

headers = {
    'Authorization': f'Bearer {partner_token}',
    'Content-Type': 'application/json'
}

payload = {
    'domain': domain
}

register_url = f'{BASE_URL.rstrip("/")}/api/1/partner_accounts'
print(f"Registering domain '{domain}' via endpoint: {register_url}...")

response = requests.post(register_url, headers=headers, json=payload)

print(f"\nResponse Code: {response.status_code}")
try:
    print(f"Response Body:\n{json.dumps(response.json(), indent=2)}")
except Exception:
    print(f"Response Body:\n{response.text}")

if response.status_code in [200, 201]:
    print("\nSUCCESS! Your account domain is officially registered in your region.")
    print("You can now run `tesla_gem.py` to retrieve vehicle data.")
else:
    print("\nRegistration failed. Please double-check that:")
    print(f"1. Your public key is hosted and accessible at: https://{domain}/.well-known/appspecific/com.tesla.3p.public-key.pem")
    print(f"2. You registered 'https://{domain}' in the 'Allowed Origin URL(s)' on the Tesla Developer Portal.")
