import pandas as pd
import argparse
from Bio.Blast import NCBIXML, NCBIWWW
import json
import csv
import os
import sys
import pymysql
from datetime import datetime

# --- Configuration ---
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS', 'password') 
DB_NAME = 'miRName'

parser = argparse.ArgumentParser()
parser.add_argument('-O', '--output_format', type=str, choices=['json', 'csv'], default='csv', help='Output format')
parser.add_argument('-D', '--database', type=str, default='nt', help='BLAST database')
parser.add_argument('-W', '--WRAPPER_PID', type=str, default='0', help='Wrapper Process ID')
parser.add_argument('-X', '--taxon_id', type=str, default='7070', help='Taxon ID') # Standardized argument name
args = parser.parse_args()

def log_error(connection, message):
    try:
        with connection.cursor() as cursor:
            query = "INSERT INTO mirbase_app_mirname_errors (error_message, error_date) VALUES (%s, %s)"
            cursor.execute(query, (message, datetime.now()))
        connection.commit()
    except Exception: pass

def read_fasta(path):
    with open(path, 'r') as f:
        name, seq = '', ''
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if name: yield (name, seq)
                name, seq = line[1:], ''
            else:
                seq += line
        if name: yield (name, seq)

def get_hairpin_files(directory, pid, taxon_id):
    return [f for f in os.listdir(directory) if f.startswith(f'{pid}_hairpin_seqs_{taxon_id}') and f.endswith('.fa')]

def run_blast_online(database, pid, taxon_id):
    """Executes online BLAST search against NCBI database."""
    files = get_hairpin_files(os.getcwd(), pid, taxon_id)
    if not files: return
    
    print(f"Running BLAST for {files[0]}...")
    fasta_string = open(files[0]).read()
    result_handle = NCBIWWW.qblast("blastn", database, fasta_string)
    with open(f"{pid}_{taxon_id}_online_blast_result.xml", "w") as out:
        out.write(result_handle.read())

def process_blast_results(pid, taxon_id):
    """Parses XML BLAST results and formats output."""
    xml_file = f"{pid}_{taxon_id}_online_blast_result.xml"
    if not os.path.exists(xml_file): return

    with open(xml_file) as f:
        records = NCBIXML.parse(f)
        for record in records:
            # Logic simplified: Export hit results
            output_name = f"{pid}_{taxon_id}_programme1_identified_Mirna"
            
            # Determine output paths relative to current script
            base_dir = os.path.dirname(os.path.abspath(__file__))
            dir_p2 = base_dir.replace("naming_programme1", "naming_programme2")
            dir_p3 = base_dir.replace("naming_programme1", "naming_programme3")
            
            # Create a simple mapping of ID -> Hit (Placeholder for complex GFF parsing logic)
            hits = [{'hits_id': 'alignment_id', 'mirna': 'novel'}] # Simplified for portfolio display
            df = pd.DataFrame({'id': record.query, 'hits': str(hits)}, index=[0])
            
            if args.output_format == "csv":
                df.to_csv(os.path.join(dir_p2, f"{output_name}.csv"), mode='a', header=False)
                df.to_csv(os.path.join(dir_p3, f"{output_name}.csv"), mode='a', header=False)

# --- Main ---
connection = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
try:
    # 1. Identify input files
    # Note: Logic simplified to prioritize FASTA processing for the pipeline
    files = get_hairpin_files(os.getcwd(), args.WRAPPER_PID, args.taxon_id)
    
    if files:
        # 2. Run Homology Search
        run_blast_online(args.database, args.WRAPPER_PID, args.taxon_id)
        # 3. Extract and Distribute Results
        process_blast_results(args.WRAPPER_PID, args.taxon_id)
    else:
        print("No input files found.")

finally:
    connection.close()