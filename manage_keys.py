import hashlib
import secrets
from src import db_session
from src.models import ApiKey

def add_key(username):
    raw_key = secrets.token_hex(16)
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    
    try:
        user_key = ApiKey(key=hashed_key, username=username)
        db_session.add(user_key)
        db_session.commit()
        print(f"\n[SUKCES] Utworzono klucz dla: {username}")
        print(f"Klucz: {raw_key}\n")
    except Exception as e:
        print(f"[ERROR] {e}")