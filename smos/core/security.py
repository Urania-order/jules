import re

class SecretFilter:
    def __init__(self):
        # Very basic regex for common secrets
        self.patterns = [
            re.compile(r"(?:api[_-]?key|password|secret|token|passwd|auth)[_-]?(\w*)", re.IGNORECASE),
            re.compile(r"[\w.-]+@[\w.-]+\.[a-zA-Z]{2,}", re.IGNORECASE), # Emails (can be sensitive)
            # Add more patterns as needed
        ]

    def filter(self, text: str) -> str:
        if not isinstance(text, str):
            return text

        filtered_text = text
        for pattern in self.patterns:
            filtered_text = pattern.sub("[REDACTED]", filtered_text)
        return filtered_text

secret_filter = SecretFilter()
