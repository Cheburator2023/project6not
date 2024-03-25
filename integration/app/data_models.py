SEND_EMAIL_SCHEMA = {
    "type": "object",
    "required": [
        "email_from",
        "email_to",
        "subject",
        "text_content"
    ],
    "properties": {
        "email_from": {
            "type": "string"
        },
        "email_to": {
            "type": "array",
            "items": {
                "type": "string",
                "format": "email"
            }
        },
        "subject": {
            "type": "string"
        },
        "text_content": {
            "type": "string"
        }
    }
}
