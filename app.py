from flask import Flask, request, jsonify
import requests
import time

app = Flask(__name__)

# Zoho OAuth2 Credentials
client_id = "1000.U7E96498LL49TB3X09CNIQGPCBA7VH"
client_secret = "1d11a1dfc83e687a0b0d73bcd497f8cdccf89362ab"
refresh_token = "1000.1593652c8a26fbd562a19d935a5883d3.279be347d79cbd2cd8f0e3fa76c0801e"

# Zoho Token URL
zoho_token_url = "https://accounts.zoho.com.au/oauth/v2/token"

# Cache the access token in memory
access_token_cache = {
    "token": None,
    "expiry_time": 0  # Timestamp when token expires
}

# Function to get a fresh access token
def get_access_token():
    current_time = time.time()
    # If token is still valid, return it
    if access_token_cache["token"] and current_time < access_token_cache["expiry_time"]:
        return access_token_cache["token"]

    # Otherwise, fetch a new one
    payload = {
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token"
    }
    try:
        response = requests.post(zoho_token_url, data=payload)
        response.raise_for_status()
        tokens = response.json()

        access_token = tokens.get("access_token")
        expires_in = tokens.get("expires_in", 3600)  # Usually 3600 seconds (1 hour)

        # Update cache
        access_token_cache["token"] = access_token
        access_token_cache["expiry_time"] = current_time + int(expires_in) - 60  # Refresh 1 min early

        return access_token
    except Exception as e:
        print(f"Error fetching access token: {e}")
        raise

@app.route("/get_crm_data", methods=["POST"])
def get_crm_data():
    data = request.get_json()

    project_name = data.get('project_name')
    unit_number = data.get('unit_number')

    if not project_name or not unit_number:
        return jsonify({"error": "Both project name and unit number are required."}), 400

    try:
        # Always get a valid access token
        access_token = get_access_token()

        crm_url = f"https://www.zohoapis.com.au/crm/v2/Properties/search?criteria=(Project_Name:equals:{project_name})and(Name:equals:{unit_number})"

        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }

        response = requests.get(crm_url, headers=headers)
        response.raise_for_status()

        data = response.json().get("data")
        if not data:
            return jsonify({"message": f"No data found for project {project_name} and unit number {unit_number}."}), 404

        sales_status = data[0].get("Sales_Status", "Not Available")

        return jsonify({
            "unit_number": unit_number,
            "project_name": project_name,
            "sales_status": sales_status
        })
    except requests.exceptions.HTTPError as http_err:
        return jsonify({"error": f"HTTP error occurred: {http_err}"}), 400
    except Exception as err:
        return jsonify({"error": f"Other error occurred: {err}"}), 500

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)

