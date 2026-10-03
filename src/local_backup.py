import os
import time
import subprocess
from datetime import datetime
import glob
from dotenv import load_dotenv

# ==========================================
# CONFIGURATION
# ==========================================
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")

# Configuration for backup directory.
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups")
# Configuration for backup retention time.
RETENTION_DAYS = 10
DAY_IN_SECONDS = 24 * 60 * 60

def run_backup():
    print("[LOCAL] Starting backup...")

    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)

    # Creating a timestamped filename for the backup.
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"backup_{DB_NAME}_{date_str}.sql.gz"
    backup_file_path = os.path.join(BACKUP_DIR, filename)

    # Creating the mysqldump command.
    env = os.environ.copy()
    env['MYSQL_PWD'] = DB_PASS
    dump_cmd = f"mysqldump -h {DB_HOST} -u {DB_USER} {DB_NAME} --routines | gzip > {backup_file_path}"

    # Running backup command and handling potential errors.
    try:
        print("[LOCAL] Creating and saving backup file...")
        subprocess.run(dump_cmd, shell=True, check=True)
        print(f"[LOCAL][SUCCESS] Saved to: {backup_file_path}")
    except subprocess.CalledProcessError as e:
        print(f"[LOCAL][ERROR] An error occurred while exporting: {e}")
        return

    # ==========================================
    # ROTATION OF OLD BACKUPS
    # ==========================================
    now = time.time()
    deleted_count = 0
    
    # Looping through all backup files and deleting those older than the retention period.
    for f in glob.glob(os.path.join(BACKUP_DIR, "*.sql.gz")):
        if os.stat(f).st_mtime < now - (RETENTION_DAYS * DAY_IN_SECONDS):
            os.remove(f)
            deleted_count += 1
            
    if deleted_count > 0:
        print(f"[LOCAL][SUCCESS] Deleted {deleted_count} old backup files.")

if __name__ == "__main__":
    run_backup()