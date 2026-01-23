import sys
import subprocess
import os
import time
import logging
import traceback
import portalocker
import pymysql
from sqlalchemy import create_engine, text, MetaData
from datetime import datetime

# --- Configuration ---
# Retrieve database credentials from environment variables
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS', 'password') 
DB_NAME = 'miRName'

# Configure Logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pipeline_runner.log'),
        logging.StreamHandler()
    ]
)

def acquire_lock(lock_file_path):
    """Ensure only one instance of the script runs at a time."""
    if os.path.exists(lock_file_path):
        logging.error("Another instance is running. Exiting.")
        sys.exit(1)
    else:
        with open(lock_file_path, 'w') as lock_file:
            portalocker.lock(lock_file, portalocker.LOCK_EX | portalocker.LOCK_NB)

def get_db_engine():
    connection_string = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}:3306/{DB_NAME}?charset=utf8mb4"
    return create_engine(connection_string)

def log_error_to_db(connection, sequence_id, error_message):
    """Log processing errors to the database for auditing."""
    try:
        with connection.cursor() as cursor:
            query = "INSERT INTO mirbase_app_mirname_errors (sequence_id, error_message, error_date) VALUES (%s, %s, %s)"
            cursor.execute(query, (sequence_id, error_message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        connection.commit()
    except Exception as e:
        logging.error(f"Failed to log error for seq {sequence_id}: {e}")

def run_subprocess(command, cwd):
    """Wrapper to run shell commands with logging and error handling."""
    print(f"Executing: {' '.join(command)}", flush=True)
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True)
        if result.stdout: print(result.stdout)
        if result.stderr: print(result.stderr)
        logging.info(f"Success: {command[1]}")
        return result
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed: {command[1]} (Exit Code {e.returncode})")
        if e.stderr: print(e.stderr)
        raise

def main():
    WRAPPER_PID = os.getpid()
    current_dir = os.path.dirname(os.path.abspath(__file__))
    lock_file = "script_lock.lock"
    acquire_lock(lock_file)

    engine = get_db_engine()
    
    # Direct connection for error logging
    connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4')

    # Define output directories for sub-programs
    out_dir1 = os.path.join(current_dir, "naming_programme1")
    out_dir2 = os.path.join(current_dir, "naming_programme2")
    out_dir3 = os.path.join(current_dir, "naming_programme3")
    
    for d in [out_dir1, out_dir2, out_dir3]:
        os.makedirs(d, exist_ok=True)

    try:
        # 1. Fetch pending tasks (Status=1)
        with engine.connect() as conn:
            seq_result = conn.execute(text("SELECT sequence_id FROM mirbase_app_mirname_status WHERE status=1 AND current_status=1"))
            sequence_ids = [row[0] for row in seq_result]

        if not sequence_ids:
            logging.info("No pending tasks found.")
            if os.path.exists(lock_file): os.remove(lock_file)
            return

        # 2. Fetch Metadata (Organism info)
        with engine.connect() as conn:
            species_res = conn.execute(text("SELECT organism_id, species, species_type, abbreviation, taxon_id FROM mirbase_app_mirname_organism"))
            species_dict = {r[0]: {'type': r[2], 'abbr': r[3], 'taxon': r[4]} for r in species_res}
            
            org_map_res = conn.execute(text("SELECT sequence_id, organism_id FROM mirbase_app_mirname_sequence WHERE sequence_id IN :ids"), {'ids': tuple(sequence_ids)})
            seq_org_map = {r[0]: r[1] for r in org_map_res}

        # Group sequences by species
        batch_map = {}
        for seq_id in sequence_ids:
            org_id = seq_org_map.get(seq_id)
            if org_id and org_id in species_dict:
                info = species_dict[org_id]
                abbr = info['abbr']
                if abbr not in batch_map:
                    batch_map[abbr] = {'taxon': info['taxon'], 'type': info['type'], 'ids': []}
                batch_map[abbr]['ids'].append(seq_id)
            else:
                log_error_to_db(connection, seq_id, "Missing organism metadata")

        # --- Batch Processing Loop ---
        for species_abbr, info in batch_map.items():
            taxon_id = info['taxon']
            seq_list = info['ids']
            
            print(f"\n--- Processing Species: {species_abbr} (Taxon: {taxon_id}, Count: {len(seq_list)}) ---")

            try:
                # A. Generate Input FASTA Files
                files = {
                    'hp1': os.path.join(out_dir1, f"{WRAPPER_PID}_hairpin_seqs_{taxon_id}.fa"),
                    'hp2': os.path.join(out_dir2, f"{WRAPPER_PID}_hairpin_seqs_{taxon_id}.fa"),
                    'hp3': os.path.join(out_dir3, f"{WRAPPER_PID}_hairpin_seqs_{taxon_id}.fa"),
                    'mat3': os.path.join(out_dir3, f"{WRAPPER_PID}_mature_seqs_and_stars_{taxon_id}.fa"),
                    'mat2': os.path.join(out_dir2, f"{WRAPPER_PID}_mature_seqs_and_stars_{taxon_id}.fa"),
                }
                
                with engine.connect() as conn:
                    for seq_id in seq_list:
                        # Fetch sequence data
                        hp_seq = conn.execute(text(f"SELECT hairpin_seq FROM mirbase_app_mirname_sequence WHERE sequence_id={seq_id}")).fetchone()[0]
                        name = conn.execute(text(f"SELECT current_name FROM mirbase_app_mirname_status WHERE sequence_id={seq_id}")).fetchone()[0]
                        mat_data = conn.execute(text(f"SELECT mature_seq, mature_star FROM mirbase_app_mirname_sequence WHERE sequence_id={seq_id}")).fetchone()
                        
                        # Write to files
                        for k in ['hp1', 'hp2', 'hp3']:
                            with open(files[k], 'a') as f: f.write(f">{name}\n{hp_seq}\n")
                        
                        for k in ['mat3', 'mat2']:
                            with open(files[k], 'a') as f:
                                f.write(f">{name}_mature_seq\n{mat_data[0]}\n")
                                f.write(f">{name}_mature_star\n{mat_data[1]}\n")

                # B. Execute Pipeline Stages
                # P1: Identification
                run_subprocess(['python', 'naming_programme1.py', '-O', 'csv', '-W', str(WRAPPER_PID), '-T', str(taxon_id)], out_dir1)
                
                # P2: Homology Search
                run_subprocess(['python', 'naming_programme2_mirbaseDB.py', '-S', species_abbr, '-W', str(WRAPPER_PID), '-X', str(taxon_id)], out_dir2)
                
                # P3: Integration
                std_type = 'plants' if info['type'] == 'plant' else 'animals'
                run_subprocess(['python', 'naming_programme3.py', '-S', species_abbr, '-T', std_type, '-W', str(WRAPPER_PID), '-X', str(taxon_id)], out_dir3)
                
                # P4: Naming & Orthology Assignment
                run_subprocess(['python', 'cleaned_naming_programme4.py', '-S', species_abbr, '-T', std_type, '-J', '01', '-W', str(WRAPPER_PID), '-X', str(taxon_id)], out_dir3)

            except Exception as e:
                logging.error(f"Critical error for {species_abbr}: {e}")
                print(f"Skipping {species_abbr} due to error.")
                continue

        # Final Cleanup: Update status to 'Processed'
        try:
            with engine.connect() as conn:
                conn.execute(text("UPDATE mirbase_app_mirname_status SET current_status = 0 WHERE status = 1 AND current_status = 1"))
                conn.commit()
        except Exception as e:
            logging.error(f"Failed to update final status: {e}")

    finally:
        connection.close()
        if os.path.exists(lock_file): os.remove(lock_file)

if __name__ == "__main__":
    main()