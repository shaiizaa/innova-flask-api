from flask import Flask, request, jsonify
import openai
import time
import os

app = Flask(__name__)

# Your OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")
# Your Assistant ID
assistant_id = "asst_5vOUyfiGTLPdBitI9ZcFdX9g"


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

        # Wait with timeout
        for _ in range(30):  # Try for 30 seconds max
            run_status = openai.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status == "completed":
                break
            time.sleep(1)
        else:
            return jsonify({"error": "OpenAI Run Timeout"}), 504

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
