from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


class SessionManager:
    def __init__(self, secret_key: str, max_age: int = 86400):
        self.serializer = URLSafeTimedSerializer(secret_key)
        self.max_age = max_age
        self.cookie_name = "mp_session"

    def create_session(self, data: dict) -> str:
        return self.serializer.dumps(data)

    def load_session(self, token: str) -> dict | None:
        try:
            return self.serializer.loads(token, max_age=self.max_age)
        except (BadSignature, SignatureExpired):
            return None
