from .openai_service import generate_response
import json

def generate_invoice_from_text(user_input):
    prompt = f"""
    Convert this into structured invoice JSON.

    Input: "{user_input}"

    Output format:
    {{
        "customer_name": "",
        "items": [
            {{"name": "", "quantity": 0, "price": 0}}
        ],
        "due_date": ""
    }}

    Return ONLY JSON.
    """

    response = generate_response(prompt)

    try:
        return json.loads(response)
    except:
        return {"error": "Invalid AI response", "raw": response}

