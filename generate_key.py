import hashlib
import secrets
from src import db_session
from src.models import ApiKey
import sys 

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

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\n[BŁĄD] Nie podano nazwy użytkownika.")
        print("Prawidłowe użycie: python generate_key.py <nazwa_pracownika>\n")
    else:
        username = sys.argv[1]
        generate_and_save_key(username)