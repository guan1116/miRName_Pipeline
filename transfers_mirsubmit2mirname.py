import mysql.connector
from datetime import datetime
from Bio import Entrez
import time
import os
import sys
import re
import pymysql
import logging

# --- Configuration ---
# NOTE: Set these environment variables in your OS or .env file before running
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASS = os.getenv('DB_PASS', 'password') # SENSITIVE
EMAIL = os.getenv('ENTREZ_EMAIL', 'your.email@example.com') 

Entrez.email = EMAIL

# --- Helper: Load Species Map ---
def load_species_map_from_hairpin_fa(hairpin_file):
    """
    Parses 'hairpin.fa' to build a mapping from Scientific Name to Abbreviation.
    Example: "Malus domestica" -> "mdm"
    """
    if not os.path.exists(hairpin_file):
        logging.error(f"FATAL: Required file '{hairpin_file}' not found.")
        return None
        
    header_re = re.compile(r'>([a-z]{3,4})-[^\s]+\s+MI[0-9]+\s+([A-Z][a-z]+ [a-z]+)')
    species_map = {}
    
    try:
        with open(hairpin_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('>'):
                    match = header_re.search(line)
                    if match:
                        abbreviation = match.group(1)
                        scientific_name = match.group(2)
                        if scientific_name not in species_map:
                            species_map[scientific_name] = abbreviation
    except Exception as e:
        logging.error(f"FATAL: Failed to parse '{hairpin_file}': {e}")
        return None
        
    logging.info(f"Loaded {len(species_map)} species mappings from '{hairpin_file}'.")
    return species_map

# --- Database Connection ---
try:
    source_db = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database="miRSubmit"
    )
    target_db = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, database="miRName"
    )
    source_cursor = source_db.cursor()
    target_cursor = target_db.cursor()
except mysql.connector.Error as err:
    print(f"FATAL: Database connection failed: {err}")
    sys.exit(1)

# --- Data Extraction ---
def extract_mirscore_data_from_source():
    query = """
    SELECT id, name, mSeq, mLen, mStart, mStop, msSeq, msLen, msStart, msStop,
           precSeq, precLen, result, flags, mismatches, bulges, mReads, msReads,
           totReads, numLibraries, precisionScore, entry_id
    FROM entries_mirscore
    """
    source_cursor.execute(query)
    return source_cursor.fetchall()

def extract_submission_data_from_source():
    query = """
    SELECT id, mirscore_file, species, publication_state, biorxiv_doi, pmid, doi, 
           publication_url, submission_date, user_id
    FROM entries_submission
    """
    source_cursor.execute(query)
    return source_cursor.fetchall()

def extract_mirna_data_from_source():
    query = "SELECT id, miRBaseName, naming_date, notes, status, submission_id, user_id FROM entries_mirna"
    source_cursor.execute(query)
    return source_cursor.fetchall()

# --- NCBI Taxonomy Logic ---
def get_species_details(taxon_id, official_map):
    try:
        handle = Entrez.efetch(db="taxonomy", id=taxon_id, retmode="xml")
        record = Entrez.read(handle)
        handle.close()
        
        species_name = record[0]['ScientificName']
        lineage = record[0]['Lineage'].lower()
        
        species_type = 'unknown'
        if any(k in lineage for k in ['viridiplantae', 'streptophyta', 'embryophyta']):
            species_type = 'plant'
        elif any(k in lineage for k in ['metazoa', 'chordata', 'arthropoda']):
            species_type = 'animal'
        
        print(f"Taxon ID {taxon_id}: {species_name} ({species_type})")
        
        # Check against official hairpin.fa map first
        if species_name in official_map:
            abbreviation = official_map[species_name]
        else:
            # Fallback generation
            genus, species = species_name.split()[:2]
            abbreviation = (genus[0] + species[:2]).lower()
            print(f"WARNING: Species '{species_name}' not in map. Defaulting to '{abbreviation}'.")
            
        return species_name, species_type, abbreviation
    except Exception as e:
        print(f"Error fetching taxon ID {taxon_id}: {e}")
        return None, None, None

# --- Data Insertion ---
def get_organism_id(taxon_id, official_map):
    query = "SELECT organism_id FROM mirbase_app_mirname_organism WHERE taxon_id = %s"
    target_cursor.execute(query, (str(taxon_id),))
    result = target_cursor.fetchone()
    if result:
        return result[0]
    else:
        species_name, species_type, abbreviation = get_species_details(taxon_id, official_map)
        if species_name is None or species_type == 'unknown':
            return None
        
        insert_query = """
        INSERT INTO mirbase_app_mirname_organism (species, species_type, abbreviation, taxon_id)
        VALUES (%s, %s, %s, %s)
        """
        target_cursor.execute(insert_query, (species_name, species_type, abbreviation, str(taxon_id)))
        target_db.commit()
        return target_cursor.lastrowid

def insert_into_submission(mirscore_file, organism_id, publication_state, biorxiv_doi, pmid, doi, publication_url, submission_date, user_id):
    insert_query = """
    INSERT INTO mirbase_app_mirname_submission (
        mirscore_file, species, publication_state, biorxiv_doi, pmid, doi, 
        publication_url, submission_date, user_id
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        target_cursor.execute(insert_query, (
            mirscore_file, organism_id, publication_state, biorxiv_doi, pmid, doi, 
            publication_url, submission_date, user_id
        ))
        target_db.commit()
        return target_cursor.lastrowid
    except mysql.connector.Error as err:
        print(f"Error inserting submission: {err}")
        return None

def insert_into_sequence(hairpin_seq, mature_seq, mature_star, organism_id, submission_id):
    sequence_query = """
    INSERT INTO mirbase_app_mirname_sequence (hairpin_seq, mature_seq, mature_star, organism_id, submission_id)
    VALUES (%s, %s, %s, %s, %s)
    """
    try:
        target_cursor.execute(sequence_query, (hairpin_seq, mature_seq, mature_star, organism_id, submission_id))
        target_db.commit()
        return target_cursor.lastrowid
    except mysql.connector.Error as err:
        print(f"Error inserting sequence: {err}")
        return None

def insert_into_status(sequence_id, current_name, user, status, current_status):
    status_query = """
    INSERT INTO mirbase_app_mirname_status (sequence_id, current_name, user, status, current_status)
    VALUES (%s, %s, %s, %s, %s)
    """
    try:
        target_cursor.execute(status_query, (sequence_id, current_name, user, status, current_status))
        target_db.commit()
    except mysql.connector.Error as err:
        print(f"Error inserting status: {err}")

def insert_into_mirscore(sequence_id, Name, result, flags, msStart, mStart, msStop, mStop, mLen, precLen, mStarLen, mReads, msReads, totReads, mismatch, n_Libraries, precision_score):
    mirscore_query = """
    INSERT INTO miRName_miRScore (
        sequence_id, Name, result, flags, msStart, mStart, msStop, mStop, mLen, 
        precLen, mStarLen, mReads, msReads, totReads, mismatch, n_Libraries, precision_score
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        target_cursor.execute(mirscore_query, (
            sequence_id, Name, result, flags, msStart, mStart, msStop, mStop, mLen, 
            precLen, mStarLen, mReads, msReads, totReads, mismatch, n_Libraries, precision_score
        ))
        target_db.commit()
    except mysql.connector.Error as err:
        print(f"Error inserting miRScore data: {err}")

# --- Main Logic ---
def main():
    global submission_data
    cwp = os.path.dirname(os.path.abspath(__file__))
    hairpin_file = os.path.join(cwp, "hairpin.fa")
    
    OFFICIAL_SPECIES_MAP = load_species_map_from_hairpin_fa(hairpin_file)
    if OFFICIAL_SPECIES_MAP is None:
        sys.exit(1)
    
    # 1. Fetch source data
    submission_data = extract_submission_data_from_source()
    
    # 2. Process submissions and map species
    submission_map = {}
    taxon_to_organism_id = {}
    
    for row in submission_data:
        source_id, mirscore_file, taxon_id, pub_state, biorxiv, pmid, doi, url, date, uid = row
        
        if taxon_id not in taxon_to_organism_id:
            organism_id = get_organism_id(taxon_id, OFFICIAL_SPECIES_MAP)
            if not organism_id: continue
            taxon_to_organism_id[taxon_id] = organism_id
        else:
            organism_id = taxon_to_organism_id[taxon_id]
        
        target_sub_id = insert_into_submission(mirscore_file, organism_id, pub_state, biorxiv, pmid, doi, url, date, uid)
        if target_sub_id:
            submission_map[source_id] = target_sub_id
            print(f"Processed submission {source_id} -> {target_sub_id}")
        time.sleep(0.34) # Rate limiting
    
    # 3. Process miRNAs
    mirna_data = extract_mirna_data_from_source()
    mirscore_data = extract_mirscore_data_from_source()
    mirna_submission_map = {row[0]: row[5] for row in mirna_data}
    
    for row in mirscore_data:
        entry_id = row[21]
        source_sub_id = mirna_submission_map.get(entry_id)
        if not source_sub_id or source_sub_id not in submission_map: continue
        
        target_sub_id = submission_map[source_sub_id]
        taxon_id = next((r[2] for r in submission_data if r[0] == source_sub_id), None)
        if not taxon_id or taxon_id not in taxon_to_organism_id: continue
        
        organism_id = taxon_to_organism_id[taxon_id]
        
        # Insert Sequence
        seq_id = insert_into_sequence(row[10], row[2], row[6], organism_id, target_sub_id)
        if not seq_id: continue
        
        # Flag as ready for processing (Status=1)
        insert_into_status(seq_id, row[1], "system", "1", "1")
        
        # Insert Metadata
        insert_into_mirscore(seq_id, row[1], row[12], row[13], row[8], row[4], row[9], row[5], 
                             row[3], row[11], row[7], row[16], row[17], row[18], row[14], row[19], row[20])
    
    source_cursor.close()
    target_cursor.close()
    source_db.close()
    target_db.close()

if __name__ == "__main__":
    main()