import pandas as pd
import argparse
import subprocess
import logging
import sys
import os
import re
import json
from Bio.Blast import NCBIXML
from sqlalchemy import create_engine, text

# --- Configuration ---
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS', 'password') 
DB_NAME = 'miRName'

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
parser = argparse.ArgumentParser(description="P2: BLAST against miRBase hairpin database.")
parser.add_argument('-S', '--species', type=str, required=True, help='Species abbreviation')
parser.add_argument('-T', '--Threshold', type=float, default=0.05, help='E-value threshold')
parser.add_argument('-W', '--WRAPPER_PID', type=str, default='0')
parser.add_argument('-X', '--taxon_id', type=str, required=True)
args = parser.parse_args()

# --- Logic ---

def generate_mi_to_mimat_map(dat_file, json_file):
    """
    Parses miRBase 'miRNA.dat' to map Hairpin Accessions (MI*) to Mature Accessions (MIMAT*).
    """
    if os.path.exists(json_file): return True
    if not os.path.exists(dat_file):
        logging.error(f"Missing {dat_file}")
        return False

    mapping = {}
    current_ac = None
    
    with open(dat_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('AC '):
                current_ac = line.split()[1].strip(';')
            elif line.startswith('FT') and '/accession="MIMAT' in line and current_ac:
                mimat = re.search(r'MIMAT\d+', line).group(0)
                mapping.setdefault(current_ac, []).append(mimat)
    
    with open(json_file, 'w') as f: json.dump(mapping, f)
    return True

def generate_mimat_to_seq_map(fasta_file, json_file):
    """Maps MIMAT IDs to their sequences and names."""
    if os.path.exists(json_file): return True
    
    mapping = {}
    header_re = re.compile(r'>(\S+)\s+(MIMAT[0-9]+)')
    
    with open(fasta_file, 'r') as f:
        name, mimat, seq = None, None, ""
        for line in f:
            if line.startswith('>'):
                if mimat: mapping[mimat] = {'name': name, 'seq': seq.replace('T', 'U')}
                match = header_re.search(line)
                name, mimat, seq = (match.group(1), match.group(2), "") if match else (None, None, "")
            else:
                seq += line.strip()
        if mimat: mapping[mimat] = {'name': name, 'seq': seq.replace('T', 'U')}

    with open(json_file, 'w') as f: json.dump(mapping, f)
    return True

# --- Main ---

# Setup Paths
current_dir = os.getcwd()
out_dir = current_dir.replace("naming_programme2", "naming_programme3")
if not os.path.exists(out_dir): os.makedirs(out_dir)

# DB Check
engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}")
with engine.connect() as conn:
    res = conn.execute(text("SELECT species FROM mirbase_app_mirname_organism WHERE abbreviation=:abbr"), {"abbr": args.species})
    expected_species = res.fetchone()[0]

# Generate Maps
generate_mi_to_mimat_map("miRNA.dat", os.path.join(out_dir, "mi_to_mimat.json"))
generate_mimat_to_seq_map("mature.fa", os.path.join(out_dir, "mimat_to_seq.json"))

# Run BLAST
query_file = f"{args.WRAPPER_PID}_hairpin_seqs_{args.taxon_id}.fa"
db_name = "hairpin_db"
xml_out = f"{args.WRAPPER_PID}_{args.taxon_id}_programme2_blast.xml"

subprocess.run(f"makeblastdb -in hairpin.fa -dbtype nucl -out {db_name}", shell=True, check=True)
subprocess.run(f"blastn -query {query_file} -db {db_name} -out {xml_out} -outfmt 5 -evalue {args.Threshold} -task blastn-short", shell=True, check=True)

# Parse BLAST
same_hits, diff_hits = {}, {}
with open(xml_out) as f:
    for record in NCBIXML.parse(f):
        # Identify best hits for same vs different species...
        # (Logic simplified for brevity, assumes standard XML parsing)
        pass 

# Save Results
# ... CSV writing logic ...
logging.info("Programme 2 Complete.")