import os
import time
import subprocess
from datetime import datetime
import glob
from os import load_dotenv
# ==========================================
# KONFIGURACJA
# ==========================================
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")

# Przechowujemy kopie w folderze 'backups' w głównym katalogu aplikacji
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups")
# Ile dni wstecz chcemy trzymać pliki
RETENTION_DAYS = 10

def run_backup():
    # Upewniamy się, że folder istnieje
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    # Tworzymy unikalną nazwę pliku z datą i godziną
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_file = os.path.join(BACKUP_DIR, f"backup_{DB_NAME}_{date_str}.sql.gz")

    # Budujemy komendę systemową: dump -> kompresja gzip -> plik
    dump_cmd = f"mysqldump -h {DB_HOST} -u {DB_USER} -p'{DB_PASS}' {DB_NAME} --routines | gzip > {backup_file}"

    try:
        print("Rozpoczynam tworzenie kopii zapasowej...")
        subprocess.run(dump_cmd, shell=True, check=True)
        print(f"[SUKCES] Zapisano w: {backup_file}")
    except subprocess.CalledProcessError as e:
        print(f"[BŁĄD] Wystąpił problem podczas eksportu: {e}")
        return

    # ==========================================
    # ROTACJA
    # ==========================================
    now = time.time()
    deleted_count = 0
    
    # Szukamy wszystkich plików .sql.gz w folderze
    for f in glob.glob(os.path.join(BACKUP_DIR, "*.sql.gz")):
        # Jeśli czas modyfikacji pliku jest starszy niż określona liczba dni
        if os.stat(f).st_mtime < now - (RETENTION_DAYS * 86400):
            os.remove(f)
            deleted_count += 1
            
    if deleted_count > 0:
        print(f"[SUKCES] Usunięto {deleted_count} starych kopii zapasowych.")

if __name__ == "__main__":
    run_backup()