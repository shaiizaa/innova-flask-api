from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

access_token = "1000.4f8d2dff8156468fcb6e46b189ff5910.991289242b87b754f4cbe109d37933b9"

@app.route("/get_crm_data", methods=["POST"])
def get_crm_data():
    data = request.get_json()

    project_name = data.get('project_name')
    unit_number = data.get('unit_number')

    if not project_name or not unit_number:
        return jsonify({"error": "Both project name and unit number are required."}), 400

    crm_url = f"https://www.zohoapis.com.au/crm/v2/Properties/search?criteria=(Project_Name:equals:{project_name})and(Name:equals:{unit_number})"

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }

    try:
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

if __name__ == "__main__":
    app.run(debug=True)
