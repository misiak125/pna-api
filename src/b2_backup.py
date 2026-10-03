import os
import subprocess
import datetime
from dotenv import load_dotenv
from b2sdk.v2 import InMemoryAccountInfo, B2Api


load_dotenv()

DB_USER = os.getenv('DB_USER')
DB_PASS = os.getenv('DB_PASS')
DB_NAME = os.getenv('DB_NAME')
DB_HOST = os.getenv('DB_HOST')
B2_KEY_ID = os.getenv('B2_KEY_ID')
B2_APP_KEY = os.getenv('B2_APP_KEY')
B2_BUCKET_NAME = os.getenv('B2_BUCKET_NAME')


TMP_BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backups", "tmp")

def run_backup():
    print("[B2] Starting backup...")
    # Passing db password via enviroment 
    env = os.environ.copy()
    env['MYSQL_PWD'] = DB_PASS
    
    # Run mysqldump command and compress the output to a temporary file
    if not os.path.exists(TMP_BACKUP_DIR):
        os.makedirs(TMP_BACKUP_DIR)

    # Creating a timestamped filename for the backup
    date_str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f"backup_{DB_NAME}_{date_str}.sql.gz"
    temp_file_path = os.path.join(TMP_BACKUP_DIR, filename)

    dump_cmd = f"mysqldump -h {DB_HOST} -u {DB_USER} {DB_NAME} --routines | gzip > {temp_file_path}"
    subprocess.run(dump_cmd, shell=True, env=env, check=True)

    print("[B2] Authorising Backblaze B2...")
    info = InMemoryAccountInfo()
    b2_api = B2Api(info)
    b2_api.authorize_account("production", B2_KEY_ID, B2_APP_KEY)

    print(f"[B2] Sending file {filename}...")
    bucket = b2_api.get_bucket_by_name(B2_BUCKET_NAME)
    bucket.upload_local_file(
        local_file=temp_file_path,
        file_name=filename,
    )

    print("[B2] Cleaning up...")
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)
        
    print("[B2] Backup completed successfully.")

if __name__ == "__main__":
    run_backup()