import time
import os
import json
import re  # Import 're' for regular expressions
import openai
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Your OpenAI API Key (from environment variable)
openai.api_key = os.getenv("OPENAI_API_KEY")

# Your Assistant ID
assistant_id = "asst_5vOUyfiGTLPdBitI9ZcFdX9g"

# Zoho OAuth2 Credentials
client_id = "1000.U7E96498LL49TB3X09CNIQGPCBA7VH"
client_secret = "1d11a1dfc83e687a0b0d73bcd497f8cdccf89362ab"
refresh_token = "1000.1593652c8a26fbd562a19d935a5883d3.279be347d79cbd2cd8f0e3fa76c0801e"

# Zoho Token URL
zoho_token_url = "https://accounts.zoho.com.au/oauth/v2/token"

# Cache the access token in memory
access_token_cache = {
    "token": None,
    "expiry_time": 0
}

def get_access_token():
    """Get the Zoho OAuth access token using the refresh token"""
    current_time = time.time()
    if access_token_cache["token"] and current_time < access_token_cache["expiry_time"]:
        return access_token_cache["token"]

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
        expires_in = tokens.get("expires_in", 3600)

        access_token_cache["token"] = access_token
        access_token_cache["expiry_time"] = current_time + int(expires_in) - 60

        return access_token
    except Exception as e:
        print(f"Error fetching access token: {e}")
        raise

@app.route("/chatbot", methods=["POST"])
def chatbot():
    try:
        user_question = request.json.get("question")

        # Log the incoming question
        print("User Question:", user_question)

        # If the user asks about available units, fetch all available units
        if "available units" in user_question.lower():
            project_name = extract_project_name(user_question)
            available_units = fetch_available_units(project_name)
            if available_units:
                reply = f"The following units are available in {project_name}: " + ", ".join(available_units)
            else:
                reply = f"No units are available in {project_name} at the moment."
            return jsonify({"reply": reply})

        # For other questions, handle them as usual (e.g., asking about specific unit availability)
        project_name = extract_project_name(user_question)
        unit_number = extract_unit_number(user_question)

        print(f"Extracted project_name: {project_name}, unit_number: {unit_number}")  # Log extracted data

        # Send request to get CRM data
        crm_response = requests.post(
            "https://innova-flask-api-1.onrender.com/get_crm_data",
            json={"project_name": project_name, "unit_number": unit_number}
        )

        if crm_response.status_code == 200:
            crm_data = crm_response.json()
            # Build a human-friendly reply based on the sales_status
            reply = generate_reply(crm_data['sales_status'], unit_number)
            return jsonify({"reply": reply})
        else:
            return jsonify({"error": "Error fetching CRM data"}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get_crm_data", methods=["POST"])
def get_crm_data():
    try:
        data = request.get_json()
        project_name = data.get('project_name')
        unit_number = data.get('unit_number')

        if not project_name or not unit_number:
            return jsonify({"error": "Both project name and unit number are required."}), 400

        # Normalize unit number to remove leading zeros
        unit_number = str(int(unit_number))  # Convert to integer and back to string to remove leading zeros

        access_token = get_access_token()  # Get Zoho access token

        crm_url = f"https://www.zohoapis.com.au/crm/v2/Properties/search?criteria=(Project_Name:equals:{project_name})and(Name:equals:{unit_number})"
        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }

        response = requests.get(crm_url, headers=headers)
        print("Raw CRM Response Status:", response.status_code)
        print("Raw CRM Response Text:", response.text)

        if not response.text:
            return jsonify({"error": "Empty response from Zoho CRM"}), 500

        response.raise_for_status()  # Will raise HTTPError for bad status codes

        crm_data = response.json()

        data = crm_data.get("data")
        if not data:
            return jsonify({"message": f"No data found for project {project_name} and unit number {unit_number}."}), 404

        sales_status = data[0].get("Sales_Status", "Not Available")

        return jsonify({
            "unit_number": unit_number,
            "project_name": project_name,
            "sales_status": sales_status
        })

    except requests.exceptions.HTTPError as http_err:
        print("HTTP Error:", http_err)
        return jsonify({"error": f"HTTP error occurred: {http_err}"}), 400
    except Exception as err:
        print("Other Error:", err)
        return jsonify({"error": f"Other error occurred: {err}"}), 500


def extract_project_name(question):
    """Extract project name from the question using regex"""
    if "Rochedale" in question:
        return "INNOVA Rochedale"
    elif "Shailer Park" in question:
        return "INNOVA Shailer Park"
    # Add more cases as needed
    return "Unknown Project"

def extract_unit_number(question):
    """Extract unit number using regex"""
    # Match phrases like "unit 12", "12", etc.
    match = re.search(r'unit\s*(\d+)|(\d+)', question)
    return match.group(1) if match else "Unknown Unit"

def fetch_available_units(project_name):
    """Fetch all available units for a given project"""
    access_token = get_access_token()  # Get Zoho access token
    crm_url = f"https://www.zohoapis.com.au/crm/v2/Properties/search?criteria=(Project_Name:equals:{project_name})and(Sales_Status:equals:Available)"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }

    response = requests.get(crm_url, headers=headers)
    print("Raw CRM Response Status for available units:", response.status_code)

    if response.status_code != 200:
        return []

    response.raise_for_status()  # Will raise HTTPError for bad status codes

    crm_data = response.json()

    data = crm_data.get("data")
    if not data:
        return []

    # Return a list of available unit numbers
    available_units = [str(unit.get("Name")) for unit in data]
    return available_units

def generate_reply(sales_status, unit_number):
    """Generate a human-friendly response based on the sales status"""
    if sales_status == "Available":
        return f"Unit {unit_number} is currently available."
    else:
        return f"Unit {unit_number} is currently unavailable."

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
