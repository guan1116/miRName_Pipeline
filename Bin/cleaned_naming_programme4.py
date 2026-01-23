import pandas as pd
import argparse
import os
import sys
import jellyfish
import subprocess
import string
import ast
import json
import re
from collections import defaultdict, Counter
from sqlalchemy import create_engine
from datetime import datetime
from Bio import SeqIO
from Bio.Blast import NCBIXML
import numpy as np

# --- Configuration ---
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS', 'password') 
DB_NAME = 'miRName'

# --- 1. Load Species Map ---
def load_species_map(hairpin_file):
    """Parses hairpin.fa to map scientific names to abbreviations."""
    if not os.path.exists(hairpin_file):
        sys.exit("Error: hairpin.fa not found.")
    
    mapping = {}
    header_re = re.compile(r'>([a-z]{3,4})-[^\s]+\s+MI[0-9]+\s+([A-Z][a-z]+ [a-z]+)')
    
    with open(hairpin_file, 'r') as f:
        for line in f:
            if line.startswith('>'):
                m = header_re.search(line)
                if m: mapping.setdefault(m.group(2), m.group(1))
    return mapping

# --- 2. Arguments ---
parser = argparse.ArgumentParser()
parser.add_argument('-S', '--species', type=str, required=True)
parser.add_argument('-T', '--species_type', type=str, default='animals')
parser.add_argument('-W', '--WRAPPER_PID', type=str, default='0')
parser.add_argument('-X', '--taxon_id', type=str, default='7070')
parser.add_argument('-J', '--job_id', type=int, default=1)
args = parser.parse_args()

pid = args.WRAPPER_PID
taxon_id = args.taxon_id
species_abbr = args.species

# --- 3. Core Naming Logic ---

def cluster_and_rename(df, identical_groups, similar_groups, species_abbr, species_type):
    """
    Standard Clustering Logic.
    Groups sequences by similarity and assigns sequential suffixes (a, b, c).
    """
    print("Running standard clustering...")
    # ... (Graph traversal and grouping logic) ...
    # This function assigns provisional names like 'pae-mir-30a' based on order.
    return df

def apply_orthology_naming(df, species_abbr):
    """
    [V4.0] Orthology-Based Suffix Correction.
    
    Logic:
    1. Checks if the Top Hit identity is > 95%.
    2. If true, overrides the sequential suffix with the Top Hit's suffix.
       Example: Renames 'pae-mir-30a' to 'pae-mir-30d' if matches 'mir-30d'.
    3. Preserves gaps (e.g., 'b' and 'd' without 'a') to reflect gene loss.
    """
    print("Applying Orthology-Based Correction (>95% Identity)...")
    for idx, row in df.iterrows():
        hit_name = row.get('primary_hits_mirna_name')
        if not hit_name or pd.isna(hit_name): continue

        # Calculate Identity %
        try:
            ident = float(row.get('primary_hsp_identity', 0))
            length = abs(float(row.get('primary_hits_query_end', 0)) - float(row.get('primary_hits_query_start', 0))) + 1
            pct = (ident / length) * 100 if length > 0 else 0
        except: pct = 0

        if pct > 95.0:
            # Extract core name (e.g., 'mir-30d') from hit
            match = re.search(r'(?:mir|let)-\d+([a-z])', str(hit_name), re.IGNORECASE)
            if match:
                suffix = match.group(1).lower()
                old_name = str(row.get('suggestion', ''))
                
                # Reconstruct name with correct suffix
                base_match = re.search(r'^(.+(?:mir|let)-\d+)', old_name, re.IGNORECASE)
                if base_match:
                    new_name = f"{base_match.group(1)}{suffix}"
                    df.at[idx, 'suggestion'] = new_name
    return df

# --- 4. Main ---
if __name__ == "__main__":
    infile = f"{pid}_{taxon_id}_overall_recommended_name_Mirna.csv"
    df = pd.read_csv(infile)
    
    # ... (BLAST all-vs-all & Grouping) ...
    
    # Stage 1: Standard Naming
    # df = cluster_and_rename(df, ...)
    
    # Stage 2: Orthology Correction
    df = apply_orthology_naming(df, species_abbr)
    
    # Save to CSV
    df.to_csv(f"{pid}_{taxon_id}_final_result_for_db.csv", index=False)
    
    # Database Insert
    print("Writing results to database...")
    engine = create_engine(f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}")
    # ... (SQL Insert Logic) ...
    print("Done.")