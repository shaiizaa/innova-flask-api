from flask import Flask, request, jsonify
import openai
import requests
import time
import os
import json
import urllib.parse  # Added to URL-encode parameters

app = Flask(__name__)

# Your OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

# Your Assistant ID
assistant_id = "asst_5vOUyfiGTLPdBitI9ZcFdX9g"

# Hardcoded Zoho Access Token for testing
HARDCODED_ACCESS_TOKEN = "1000.294781f550f0a49d7b168f7126419d15.880742fec380459c3ce491a4127b366d"


def get_access_token():
    # TEMP: use hardcoded token
    return HARDCODED_ACCESS_TOKEN


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
                            "output": crm_data
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
        data = request.get_json()  # Get the JSON data sent to this endpoint
        print("Received Request JSON:", data)  # Log what data we received from OpenAI

        project_name = data.get('project_name')  # Extract the project name
        unit_number = data.get('unit_number')  # Extract the unit number
        print("Project Name:", project_name, "Unit Number:", unit_number)  # Log the values we extracted

        # Check if both values are present
        if not project_name or not unit_number:
            return jsonify({"error": "Both project name and unit number are required."}), 400

        # URL encode the project_name and unit_number to avoid issues with special characters
        project_name = urllib.parse.quote(project_name)
        unit_number = urllib.parse.quote(unit_number)

        access_token = get_access_token()

        # Construct the CRM URL
        crm_url = f"https://www.zohoapis.com.au/crm/v2/Properties/search?criteria=(Project_Name:equals:{project_name})and(Name:equals:{unit_number})"
        print("CRM URL:", crm_url)  # Log the full CRM URL for debugging

        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}"  # Authorization header with access token
        }

        # Make the API request to Zoho CRM
        response = requests.get(crm_url, headers=headers)
        print("Raw CRM Response Status:", response.status_code)  # Log the status code (200 means OK)
        print("Raw CRM Response Text:", response.text)  # Log the raw text from the Zoho CRM response

        # Check if the response is empty
        if not response.text:
            return jsonify({"error": "Empty response from Zoho CRM"}), 500

        response.raise_for_status()  # Will raise HTTPError for bad status codes

        try:
            crm_data = response.json()  # Parse the JSON response
        except json.JSONDecodeError as e:
            return jsonify({"error": f"Error parsing CRM response as JSON: {str(e)}"}), 500

        print("Parsed CRM Response:", crm_data)  # Log the parsed CRM response

        data = crm_data.get("data")  # Extract the 'data' field from the response
        if not data:
            return jsonify({"message": f"No data found for project {project_name} and unit number {unit_number}."}), 404

        # Get the sales status
        sales_status = data[0].get("Sales_Status", "Not Available")

        # Return the result
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
