from flask import Flask, request, jsonify
import openai
import requests
import time
import os
import json

app = Flask(__name__)

# Your OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Your Assistant ID
assistant_id = "asst_5vOUyfiGTLPdBitI9ZcFdX9g"

# Zoho OAuth2 Credentials
client_id = "1000.U7E96498LL49TB3X09CNIQGPCBA7VH"
client_secret = "1d11a1dfc83e687a0b0d73bcd497f8cdccf89362ab"
refresh_token = "1000.1593652c8a26fbd562a19d935a5883d3.279be347d79cbd2cd8f0e3fa76c0801e"

# Zoho Token URL
zoho_token_url = "https://accounts.zoho.com.au/oauth/v2/token"

# Access token cache
access_token_cache = {
    "token": None,
    "expiry_time": 0
}

def get_access_token():
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

        thread = openai.beta.threads.create()

        openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=user_question
        )

        run = openai.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id,
            tool_choice="auto"
        )

        for _ in range(30):
            run_status = openai.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status in ["completed", "requires_action"]:
                break
            time.sleep(1)
        else:
            return jsonify({"error": "OpenAI Run Timeout"}), 504

        # Handle function calling if needed
        if run_status.status == "requires_action" and run_status.required_action and run_status.required_action.submit_tool_outputs:
            tool_calls = run_status.required_action.submit_tool_outputs.tool_calls
            outputs = []

            for tool_call in tool_calls:
                if tool_call.function.name == "get_crm_data":
                    arguments = json.loads(tool_call.function.arguments)
                    project_name = arguments.get("project_name")
                    unit_number = arguments.get("unit_number")

                    crm_response = requests.post(
                        "https://innova-flask-api-1.onrender.com/get_crm_data",
                        json={
                            "project_name": project_name,
                            "unit_number": unit_number
                        }
                    )

                    if crm_response.status_code == 200:
                        crm_data = crm_response.json()
                        outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": crm_data  # ✅ Send raw CRM data, not string
                        })
                    else:
                        outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": {"error": "Error fetching CRM data."}
                        })

            openai.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=outputs
            )

            for _ in range(30):
                final_run = openai.beta.threads.runs.retrieve(
                    thread_id=thread.id,
                    run_id=run.id
                )
                if final_run.status == "completed":
                    break
                time.sleep(1)
            else:
                return jsonify({"error": "Final Run Timeout"}), 504

        messages = openai.beta.threads.messages.list(thread_id=thread.id)

        final_reply = ""
        for message in messages.data:
            if message.role == "assistant":
                final_reply = message.content[0].text.value

        if final_reply:
            return jsonify({"reply": final_reply})
        else:
            return jsonify({"error": "Assistant did not reply properly"}), 500

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

        access_token = get_access_token()

        crm_url = f"https://www.zohoapis.com.au/crm/v2/Properties/search?criteria=(Project_Name:equals:{project_name})and(Name:equals:{unit_number})"

        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"
        }

        response = requests.get(crm_url, headers=headers)
        print("CRM Raw Response Text:", response.text)
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
