import hashlib


def hash_password_sha256(plain_password: str) -> str:
    return hashlib.sha256(plain_password.encode("utf-8")).hexdigest()


def verify_password_sha256(stored_hash: str, submitted_password: str) -> bool:
    return stored_hash == hash_password_sha256(submitted_password)
