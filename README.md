# Tesla Fleet API Logger & Savings Calculator

This project provides a lightweight, local utility to securely connect to the official **Tesla Developer Fleet API**, track your vehicle's odometer history, log Supercharging sessions, and calculate **dynamic, session-specific savings** for free Supercharging sessions—completely optimized with local, incremental caching to avoid duplicate API requests.

---

## Features

- **Official API Integration**: Uses the official Tesla Fleet API (OAuth 2.0 with Client Credentials and Authorization Code PKCE flows).
- **Dynamic Savings Computation**: Filters for free Supercharging sessions (`"pricingType": "NO_CHARGE"`) and multiplies each session's actual energy (`usageBase`) by its exact local session rate (`rateBase`) to compute true monetary savings.
- **Incremental Caching**: Saves retrieved charging events in a local cache (`dx_sessions_cache.json`) and queries only new sessions incrementally (averaging exactly 1 API call per run) to prevent rate limits or scaled API usage charges.
- **Offline Odometer Logging**: Checks vehicle connection state and cleanly wakes the vehicle to grab current odometer readings, writing them to a structured history log.
- **Zero Third-Party Database Dependencies**: All credentials, tokens, caches, and histories are stored entirely as local, human-readable files.

---

## Repository Structure

- `tesla_gem.py`: The main script that wakes the car, fetches charging history, saves logs, and displays dynamic savings.
- `register_partner.py`: A helper script that automates the regional Fleet API registration for your domain using a Machine-to-Machine client token.
- `.env.example`: Template to set up your environment variables.
- `.gitignore`: Configured to automatically prevent local secrets, tokens, cache, and logging JSON files from being pushed to public GitHub.

---

## Setup & Registration Walkthrough

Follow these steps to set up your developer account, register your vehicle integration, and run the logging script.

### Step 1: Create Your GitHub Pages Domain & Host Your Public Key
Tesla validates your developer registration by reading a hosted public key from a specific URL matching your registered domain.

1. Create a public repository on GitHub (e.g., `mylacc.github.io`).
2. Turn on **GitHub Pages** in the repository settings to host static pages.
3. Run the following standard `openssl` commands in your terminal to generate your cryptographic keys:
   ```bash
   # Generate a private EC key
   openssl ecparam -name prime256v1 -genkey -noout -out private-key.pem

   # Extract the corresponding public key
   openssl ec -in private-key.pem -pubout -out com.tesla.3p.public-key.pem
   ```
   > [!WARNING]
   > Keep `private-key.pem` secure and **never** commit it or upload it anywhere public.

4. Create a folder in your GitHub Pages repository named `.well-known/appspecific/`.
5. Upload your public key `com.tesla.3p.public-key.pem` to that directory and push it to GitHub.
6. Verify that your public key is accessible in a public web browser at:
   `https://<yourname>.github.io/.well-known/appspecific/com.tesla.3p.public-key.pem`

### Step 2: Register on the Tesla Developer Portal
1. Go to the [Tesla Developer Portal](https://developer.tesla.com/) and sign in with your Tesla account.
2. Complete your profile registration.
3. Create a new application project:
   * Select the **Authorization Code** and **Client Credentials** flows.
   * **Allowed Origin URL(s)**: Enter your GitHub Pages domain (e.g., `https://<yourname>.github.io`). **Note**: This must be a secure public domain hosting your public key; localhost is not allowed by Tesla here.
   * **Redirect URI(s)**: Enter your redirect callback URL. For personal CLI scripts, standard redirect URLs like `http://localhost:8080/callback` or `https://auth.tesla.com/void/callback` are completely fine here.
   * Note your generated **Client ID**, **Client Secret**, and **Redirect URI** will be used in the next step so keep them handy.

### Step 3: Configure the Local Environment Variables
1. Copy the example environment template to create a local `.env` file:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your details:
   ```env
   TESLA_CLIENT_ID=your_client_id_from_portal
   TESLA_CLIENT_SECRET=your_client_secret_from_portal
   TESLA_REDIRECT_URI=http://localhost:8080/callback  # Must match the redirect URI entered in the portal (localhost is fine here)
   TESLA_BASE_URL=https://fleet-api.prd.na.vn.cloud.tesla.com/  # North America regional endpoint (change if in EU or CN)
   TESLA_SCOPES=openid,offline_access,vehicle_device_data,vehicle_cmds,vehicle_charging_cmds
   ```

### Step 4: Register Your Domain with Tesla
Run the registration helper script to authenticate with Tesla and register your domain:

```bash
python3 register_partner.py
```
* The script will fetch a Machine-to-Machine token.
* Enter your GitHub Pages domain (e.g., `<yourname>.github.io`) when prompted.
* The script will submit the registration. If successful, you will see a green `SUCCESS!` confirmation.

---

## Running the Logger

Now that your account and domain are registered, you can run the logger script!

### 1. Set Up Your Virtual Environment
To install the required dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run the Main Script
```bash
python3 tesla_gem.py
```

### 3. Initial Authentication (First Run Only)
If no authenticated token is found in your system's secure keychain, the CLI will automatically initiate a standard OAuth 2.0 PKCE authorization flow:
1. Open the printed authorization URL in your web browser.
2. Sign in with your Tesla account and authorize the permissions.
3. Your browser will redirect to your registered callback URL (e.g., a blank page or redirect callback).
4. Copy the **entire redirect URL** from your browser's address bar.
5. Paste it back into the terminal prompt.
6. The script will securely exchange the code for your access and refresh tokens, store them directly in your OS-level secure credential vault (such as **macOS Keychain**, **Windows Credential Manager**, or **Linux Secret Service**), and proceed.

> [!NOTE]
> No local plaintext token files (like `tesla_token.json`) are written to disk. The tokens are encrypted at rest and protected by your operating system. Any legacy `tesla_token.json` file in the directory is automatically migrated to the secure keychain and deleted on the first run.


---

## Log Files & Cache

All data files are saved inside the directory specified by `TESLA_DATA_DIR` in your `.env` (defaults to the local project directory if not specified):

- `dx_sessions_cache.json`: The local sessions database. Stores metadata of all historical Supercharging sessions incrementally to eliminate redundant API requests.
- `super_charger_charge_history.json`: Daily/session records mapping timestamps to Supercharging energy added (in kWh).
- `all_charge_history.json`: Combined daily record including all charging categories.
- `odometer_history.json`: Historical records mapping timestamps to odometer readings.
- `home_charge_history.json`: Local home charging logs.
