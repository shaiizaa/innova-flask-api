from flask import Flask, request, jsonify
import openai
import time
import os

app = Flask(__name__)

# Your OpenAI API Key
openai.api_key = "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"

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

        while True:
            run_status = openai.beta.threads.runs.retrieve(
                thread_id=thread.id,
                run_id=run.id
            )
            if run_status.status == "completed":
                break
            time.sleep(1)

        messages = openai.beta.threads.messages.list(thread_id=thread.id)

        final_reply = ""
        for message in messages.data:
            if message.role == "assistant":
                final_reply = message.content[0].text.value

        return jsonify({"reply": final_reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Required for Render
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
