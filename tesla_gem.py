import os
import json
import time
import base64
import hashlib
import keyring
from requests_oauthlib import OAuth2Session
from datetime import datetime


# --- SIMPLE DOTENV PARSER ---
def load_dotenv(dotenv_path='.env'):
    if os.path.exists(dotenv_path):
        with open(dotenv_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, val = line.split('=', 1)
                        # Clean up quotes if present
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        os.environ[key] = val

# Load .env configurations if present
load_dotenv()

# Allow insecure HTTP transport for local OAuth redirects (e.g. http://localhost)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# --- CONFIGURATION & PATHS ---
TOKEN_FILE = 'tesla_token.json'
KEYCHAIN_SERVICE = 'TeslaFleetAPI'
KEYCHAIN_ACCOUNT = 'auth_token'
DATA_DIR = os.getenv('TESLA_DATA_DIR', '.')
ODOMETER_FILE = os.path.join(DATA_DIR, 'odometer_history.json')
HOME_CHARGE_FILE = os.path.join(DATA_DIR, 'home_charge_history.json')
SUPER_CHARGE_FILE = os.path.join(DATA_DIR, 'super_charger_charge_history.json')
ALL_CHARGE_FILE = os.path.join(DATA_DIR, 'all_charge_history.json')
DX_SESSIONS_CACHE_FILE = os.path.join(DATA_DIR, 'dx_sessions_cache.json')

CLIENT_ID = os.getenv('TESLA_CLIENT_ID', 'ownerapi')
CLIENT_SECRET = os.getenv('TESLA_CLIENT_SECRET', '')
REDIRECT_URI = os.getenv('TESLA_REDIRECT_URI', 'https://auth.tesla.com/void/callback')
AUTH_URL = os.getenv('TESLA_AUTH_URL', 'https://auth.tesla.com/oauth2/v3/authorize')
TOKEN_URL = os.getenv('TESLA_TOKEN_URL', 'https://auth.tesla.com/oauth2/v3/token')
BASE_URL = os.getenv('TESLA_BASE_URL', 'https://owner-api.teslamotors.com/')
SCOPES = ['openid', 'email', 'offline_access']
# Note: Official Fleet API scopes usually include: openid offline_access vehicle_device_data vehicle_cmds vehicle_charging_cmds
if os.getenv('TESLA_SCOPES'):
    SCOPES = [s.strip() for s in os.getenv('TESLA_SCOPES').split(',')]

APP_USER_AGENT = 'TeslaApp/4.10.0'

def save_token(token):
    try:
        keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, json.dumps(token))
        print("DEBUG: Token securely updated and saved in system keychain.")
    except Exception as e:
        print(f"DEBUG: Failed to save token to system keychain: {e}")
        # Fallback to local file if keyring fails (e.g. headless/non-interactive server environments)
        with open(TOKEN_FILE, 'w') as f:
            json.dump(token, f)
        print("DEBUG: Token saved to local file (fallback).")

def load_token():
    # 1. Try loading from macOS/System Keychain first
    try:
        token_data = keyring.get_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT)
        if token_data:
            return json.loads(token_data)
    except Exception as e:
        print(f"DEBUG: Failed to read from system keychain: {e}")

    # 2. Fallback to existing local file (migration flow)
    if os.path.exists(TOKEN_FILE):
        try:
            with open(TOKEN_FILE, 'r') as f:
                token = json.load(f)
            # Migrate to Keychain if possible
            try:
                keyring.set_password(KEYCHAIN_SERVICE, KEYCHAIN_ACCOUNT, json.dumps(token))
                os.remove(TOKEN_FILE)
                print("DEBUG: Successfully migrated local plaintext token file to secure system keychain.")
            except Exception as e:
                print(f"DEBUG: Failed to migrate token to system keychain: {e}")
            return token
        except Exception as e:
            print(f"DEBUG: Failed to read local token file: {e}")
    return None

def wake_vehicle(oauth, vehicle_id):
    """Checks if the car is online; if not, sends wake command and waits."""
    print("Checking vehicle state...")
    retries = 0
    max_retries = 12  # 12 * 5 seconds = 1 minute timeout

    while retries < max_retries:
        response = oauth.get(f'{BASE_URL.rstrip("/")}/api/1/vehicles/{vehicle_id}')
        state = response.json().get('response', {}).get('state')
        
        if state == 'online':
            print("Vehicle is online and ready.")
            return True
        
        if retries == 0:
            print(f"Vehicle is {state}. Sending wake command...")
            oauth.post(f'{BASE_URL.rstrip("/")}/api/1/vehicles/{vehicle_id}/wake_up')
        
        print(f"Waiting for vehicle to wake... (Attempt {retries + 1}/{max_retries})")
        time.sleep(5)
        retries += 1
    
    print("Timeout: Vehicle failed to wake up.")
    return False

def main():
    token = load_token()
    
    # Configure auto-refresh arguments. Include client_secret if official Fleet API is used.
    refresh_kwargs = {'client_id': CLIENT_ID}
    if CLIENT_SECRET:
        refresh_kwargs['client_secret'] = CLIENT_SECRET

    oauth = OAuth2Session(
        CLIENT_ID, token=token, redirect_uri=REDIRECT_URI, scope=SCOPES,
        auto_refresh_url=TOKEN_URL, auto_refresh_kwargs=refresh_kwargs,
        token_updater=save_token
    )
    oauth.headers.update({'X-Tesla-User-Agent': APP_USER_AGENT, 'User-Agent': 'Tesla/2.7.0'})

    # --- AUTHENTICATION ---
    if not token:
        print("No cached token found. Starting OAuth 2.0 authorization flow...")
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b'=')
        unencoded_digest = hashlib.sha256(code_verifier).digest()
        code_challenge = base64.urlsafe_b64encode(unencoded_digest).rstrip(b'=')
        authorization_url, _ = oauth.authorization_url(AUTH_URL, code_challenge=code_challenge, code_challenge_method='S256')
        
        print("\n" + "="*80)
        print(" OAUTH 2.0 AUTHENTICATION REQUIRED")
        print("="*80)
        print(f"1. Open the following URL in your web browser:")
        print(f"   {authorization_url}")
        print("\n2. Log in using your Tesla account and approve access permissions.")
        print("3. Once completed, your browser will redirect you to a new URL.")
        print(f"   (It might be a blank page or a redirection to: {REDIRECT_URI})")
        print("4. Copy the entire redirect URL from your browser's address bar.")
        print("="*80 + "\n")
        
        authorization_response = input('Enter the full callback/redirect URL:\n').strip()
        
        fetch_kwargs = {
            'authorization_response': authorization_response,
            'code_verifier': code_verifier,
            'include_client_id': True
        }
        if CLIENT_SECRET:
            fetch_kwargs['client_secret'] = CLIENT_SECRET
            
        token = oauth.fetch_token(TOKEN_URL, **fetch_kwargs)
        save_token(token)

    # --- VEHICLE LOGIC ---
    try:
        # Get vehicle list to find the ID
        products = oauth.get(f'{BASE_URL.rstrip("/")}/api/1/products').json()
        if not products.get('response'):
            print("No vehicles found.")
            print(f"DEBUG: Raw products response from API:\n{json.dumps(products, indent=2)}")
            return

        vehicle = products['response'][0]
        vehicle_id = str(vehicle['id'])
        display_name = vehicle.get('display_name', 'Unnamed Vehicle')
        vin = vehicle.get('vin', 'Unknown VIN')
        state = vehicle.get('state', 'Unknown State')
        
        print("\n" + "="*80)
        print(" VEHICLE IDENTIFIED")
        print("="*80)
        print(f"Name:  {display_name}")
        print(f"VIN:   {vin}")
        print(f"ID:    {vehicle_id}")
        print(f"State: {state}")
        print("="*80 + "\n")

        # WAKE UP THE CAR
        if not wake_vehicle(oauth, vehicle_id):
            return # Stop if car won't wake

        # Now that car is online, get all data
        charge_resp = oauth.post(f'{BASE_URL.rstrip("/")}/api/1/vehicles/{vehicle_id}/charge_history')
        charge_data = charge_resp.json()
        print(f"DEBUG: Raw legacy charge_history response (expect stub):\n{json.dumps(charge_data, indent=2)}")

        # Fetch using official modern endpoint (paginated and cached incrementally to avoid redundant queries)
        cached_sessions = []
        if os.path.exists(DX_SESSIONS_CACHE_FILE):
            try:
                with open(DX_SESSIONS_CACHE_FILE, 'r') as f:
                    cached_sessions = json.load(f)
                if not isinstance(cached_sessions, list):
                    cached_sessions = []
            except Exception as cache_err:
                print(f"DEBUG: Failed to load sessions cache: {cache_err}")
                cached_sessions = []

        cached_ids = {s.get('sessionId') for s in cached_sessions if s.get('sessionId')}

        sessions = []
        new_sessions = []
        try:
            page_no = 1
            page_size = 50
            found_existing = False
            while not found_existing:
                url = f'{BASE_URL.rstrip("/")}/api/1/dx/charging/history?vin={vin}&pageSize={page_size}&pageNo={page_no}'
                dx_charge_resp = oauth.get(url)
                if dx_charge_resp.status_code != 200:
                    print(f"DEBUG: Official dx/charging/history page {page_no} failed with status code {dx_charge_resp.status_code}")
                    break
                page_data = dx_charge_resp.json()
                data_list = page_data.get('data', [])
                if not data_list:
                    break
                
                for s in data_list:
                    sid = s.get('sessionId')
                    if sid in cached_ids:
                        found_existing = True
                        break
                    new_sessions.append(s)
                
                if len(data_list) < page_size or found_existing:
                    break
                page_no += 1
            
            sessions = new_sessions + cached_sessions
            print(f"DEBUG: Successfully fetched {len(new_sessions)} new Supercharger sessions from official API. Total cached: {len(sessions)}")
            
            # Save updated cache back to file
            try:
                with open(DX_SESSIONS_CACHE_FILE, 'w') as f:
                    json.dump(sessions, f, indent=4)
            except Exception as cache_err:
                print(f"DEBUG: Failed to save sessions cache: {cache_err}")
        except Exception as dx_err:
            print(f"DEBUG: Failed calling official dx charging history: {dx_err}")
            # Fall back to cached sessions if API query fails
            sessions = cached_sessions

        def load_json_file(path):
            if os.path.exists(path):
                with open(path, 'r') as f: return json.load(f)
            return {}

        home_charging = load_json_file(HOME_CHARGE_FILE)
        super_charging = load_json_file(SUPER_CHARGE_FILE)
        all_charging = load_json_file(ALL_CHARGE_FILE)
        odometer_history = load_json_file(ODOMETER_FILE)

        total_sc_savings = 0.0

        # Process official charging history sessions
        for session in sessions:
            charge_start = session.get('chargeStartDateTime')
            if not charge_start:
                continue
            
            try:
                dt = datetime.fromisoformat(charge_start)
                sec_str = str(int(dt.timestamp()))
            except Exception as ts_err:
                print(f"DEBUG: Failed to parse timestamp {charge_start}: {ts_err}")
                continue
            
            # Find the charging fee to extract usage (energy) and rate info
            charging_fee = None
            for fee in session.get('fees', []):
                if fee.get('feeType') == 'CHARGING':
                    charging_fee = fee
                    break
            
            if not charging_fee:
                continue
            
            energy = float(charging_fee.get('usageBase', 0.0))
            pricing_type = charging_fee.get('pricingType')
            rate_base = float(charging_fee.get('rateBase', 0.0))
            
            # Save parsed energy to local history
            energy_str = str(round(energy))
            super_charging[sec_str] = energy_str
            all_charging[sec_str] = energy_str

            # Update dynamic savings for free sessions
            if pricing_type == 'NO_CHARGE':
                total_sc_savings += energy * rate_base

        # Process Odometer (Guaranteed online now)
        v_data_resp = oauth.get(f'{BASE_URL.rstrip("/")}/api/1/vehicles/{vehicle_id}/vehicle_data').json()
        v_data = v_data_resp.get('response', {})
        if isinstance(v_data, str):
            try:
                v_data = json.loads(v_data)
            except Exception:
                v_data = {}

        if not isinstance(v_data, dict):
            print(f"DEBUG: Could not parse valid vehicle_data response. Raw payload:\n{json.dumps(v_data_resp, indent=2)}")
            return

        ts = str(v_data['vehicle_state']['timestamp'])
        odo = str(v_data['vehicle_state']['odometer'])
        
        # Consolidate odometer history:
        # Keep only the earliest reading in each historical month, plus the single current/most-recent reading.
        odometer_history[ts] = odo
        new_odo_history = {}
        entries = []
        for k, v in odometer_history.items():
            try:
                val = float(k)
                if val > 3 * 10**9:
                    val = val / 1000.0
                dt_entry = datetime.fromtimestamp(val)
                entries.append((dt_entry, k, v))
            except Exception:
                new_odo_history[k] = v

        if entries:
            entries.sort(key=lambda x: x[0])
            groups = {}
            for dt_entry, k, v in entries:
                ym = (dt_entry.year, dt_entry.month)
                if ym not in groups:
                    groups[ym] = []
                groups[ym].append((dt_entry, k, v))
            
            sorted_ym = sorted(groups.keys())
            for i, ym in enumerate(sorted_ym):
                month_entries = groups[ym]
                earliest = month_entries[0]
                new_odo_history[earliest[1]] = earliest[2]
                
                # If it's the current/active month:
                if i == len(sorted_ym) - 1:
                    latest = month_entries[-1]
                    if latest[1] != earliest[1]:
                        new_odo_history[latest[1]] = latest[2]

            odometer_history = new_odo_history

        # Write Files
        with open(ODOMETER_FILE, "w") as f: json.dump(odometer_history, f, indent=4, sort_keys=True)
        with open(HOME_CHARGE_FILE, "w") as f: json.dump(home_charging, f, indent=4, sort_keys=True)
        with open(SUPER_CHARGE_FILE, "w") as f: json.dump(super_charging, f, indent=4, sort_keys=True)
        with open(ALL_CHARGE_FILE, "w") as f: json.dump(all_charging, f, indent=4, sort_keys=True)

        print(f"Success. Savings: ${total_sc_savings:.2f}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()