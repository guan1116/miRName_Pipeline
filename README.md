# miRName: The Orthology-Guided miRNA Annotation Pipeline

> Note:
> This repository serves as a codebase demonstration for the production pipeline developed at The University of Manchester.
> Bin/: Contains the core algorithmic logic (Programmes 1-4).
> Screenshots: Below demonstrate the deployed web interface used for high-throughput curation.
> Data: Uses anonymized demo data for privacy compliance.

---

## System Dashboard Preview

The following screenshots showcase the interactive curation interface integrated with the pipeline. This dashboard allows researchers to visualize BLAST alignments and make "Accept/Reject" decisions efficiently.

### 1. Interactive Curation Dashboard
The UI visualizes the alignment between candidate sequences and known homologs, calculating identity matrices automatically.

![Dashboard Preview](dashboard_ui_preview.png)
*(Figure 1: The curation dashboard showing alignment visualization and decision buttons.)*

### 2. Pipeline Execution Log
The backend orchestration running on the High-Performance Computing (HPC) cluster.

![Execution Log](pipeline_execution_log.png)
*(Figure 2: Execution logs showing the wrapper managing concurrent naming tasks.)*

---

## Overview

miRName is a specialized bioinformatics pipeline designed for the automated, orthology-based naming of microRNAs (miRNAs) across diverse metazoan species.

Unlike traditional tools that assign names sequentially (e.g., mir-1, mir-2) without regard for evolutionary history, miRName prioritizes evolutionary orthology. It employs a multi-stage analysis pipeline to cluster sequences and utilizes a strict "Top-Hit" evidence system, ensuring new annotations are consistent with the miRBase registry.

Key Goal: Facilitate the transition from raw sequencing candidates to official database entries, resolving synonym conflicts and lineage fragmentation, and generating strictly formatted relational batch files for final database ingestion.

---

## Naming Logic & Data Enrichment

The core naming logic is enforced by the scripts located in the Bin/ directory. 

| Criteria | Action |
| :--- | :--- |
| Identity > 95%<br>(to known homolog) | Strict Top-Hit Override.<br>Forces the name to match the homolog (e.g., mir-30b), overriding sequential clustering. |
| Identity < 95%<br>(Novel/Ambiguous) | Sequential Assignment.<br>Suffixes (a, b, c...) assigned based on clustering order. |
| Novel Family | Assigned a temporary Novel-ID until unified by cross-species analysis. |
| Mature Enrichment | Trace-Back Sequence Auditing.<br>Automatically queries external databases (e.g., MirGeneDB) to retrieve missing mature arms (5p/3p) and dynamically renames/updates existing records to maintain naming symmetry. |

---

## Technical Specifications & Usage

================================================================================
                        PIPELINE ARCHITECTURE & WORKFLOW
================================================================================

[ DIRECTORY STRUCTURE ]
  root/
   ├── naming_runner_mirbaseDB.py    # Master Wrapper (Orchestrator)
   ├── transfers_mirsubmit...py      # Data Ingestion Script
   ├── except_all_novel_families_and_migration_script_3.py  # Final Batch File Generation Script
  Bin/
   ├── naming_programme1.py          # P1: Identification & Genome Mapping
   ├── naming_programme2...py        # P2: Homology Search (BLAST+)
   ├── naming_programme3.py          # P3: Evidence Integration
   ├── cleaned_naming_programme4.py  # P4: The Naming Engine (Clustering)
  TestData/
   ├── demo_input.fa                 # Anonymized input for demonstration

[ WORKFLOW COMPONENTS ]
  1. Data Ingestion
     Extracts metadata from user submissions (miRSubmit) and populates the
     SQL database processing queue.

  2. The Wrapper (Master Controller)
     - Monitors database for pending tasks.
     - Manages file locking for HPC concurrency.
     - Automatically calls sub-programmes (P1-P4) located in Bin/.

  3. Core Logic Modules (Bin/)
     - P1: Maps candidates to genome context.
     - P2: Performs local BLAST against miRBase hairpin database.
     - P3: Defines precise mature/star boundaries based on MIMAT.
     - P4: Applies V4.0 logic to cluster sequences and assign names.

  4. Relational Batch Generation & Enrichment
     - Executes final data extraction after manual curation.
     - Scrapes MirGeneDB for coordinate validation and cross-referencing.
     - Generates isolated batch files handling ADD/UPDATE commands, cross-database
       links, and missing location data separation.

================================================================================
                                     USAGE
================================================================================

# Prerequisites
  python >= 3.9, pandas, numpy, biopython, sqlalchemy, pymysql, ncbi-blast+

# 1. Ingestion (Migrate Data)
  $ python transfers_mirsubmit2mirname.py

# 2. Execution (Run Pipeline)
  $ python naming_runner_mirbaseDB.py

# 3. Visualization (Web Server)
  $ python manage.py runserver 0.0.0.0:8000

# 4. Final Export (Generate Batches)
  $ python except_all_novel_families_and_migration_script_3.py

================================================================================
                    CUSTOMIZING BATCHES & SPECIES FILTERING
================================================================================

If you need to process a different set of species or specific submission batches, you must modify the SQL query located inside the main() function of except_all_novel_families_and_migration_script_3.py (around line 462).

The current script filters by submission_id and explicitly excludes a list of species abbreviations (e.g., 'phw', 'laf', 'bla') using the "NOT IN" operator.

[ HOW TO MODIFY ]
To process a specific target species (e.g., Homo sapiens 'hsa' and Mus musculus 'mmu') or a new submission batch, replace the WHERE clause in the SQL query:

Original Query Example (Current Logic):
  WHERE r.checked = 1 
    AND st.status = 4 
    AND st.current_status = 1
    AND (
        (s.submission_id BETWEEN 1169 AND 1287)
        AND o.abbreviation NOT IN ('phw', 'laf', 'bla', ...)
    )

Modified Query Example (For targeted processing):
  WHERE r.checked = 1 
    AND st.status = 4 
    AND st.current_status = 1
    AND s.submission_id = 9999              -- Change to your specific batch ID
    AND o.abbreviation IN ('hsa', 'mmu')    -- Change to your specific species

================================================================================
                             OUTPUT FORMAT (miRBase)
================================================================================

The final export module produces strictly formatted batch files for immediate ingestion into the miRBase database. The system automatically categorizes outputs into distinct relational files.

[ EXAMPLE OUTPUT: MASTER BATCH FILE ]
  # --- SECTION 1: UPDATES ---
  UPDATE	HAIRPIN	cja-mir-551	name	cja-mir-551a
  UPDATE	MATURE	cja-miR-551-3p	name	cja-miR-551a-3p
  
  # --- SECTION 2: ADDS ---
  ADD	HAIRPIN	hsa-mir-13167	Homo sapiens hsa-miR-13167 stem-loop	miRNA from MirGeneDB	GGCAUGCAGU...	Homo sapiens	mir-13167	chr4		75973882	75973940
  ADD	MATURE	hsa-miR-13167-5p	CAUAAACUGCAUGCCUGCACACC	hsa-mir-13167	not_experimental
  ADD	MATURE	hsa-miR-13167-3p	UGUGCAGGCAUGCAGUUUAUGUU	hsa-mir-13167	not_experimental

[ EXAMPLE OUTPUT: MIRGENEDB LINKS BATCH ]
  ADD	LINK	MirGeneDB	hsa-mir-13167	Hsa-Mir-12463
  ADD	LINK	MirGeneDB	hsa-mir-13168	Hsa-Mir-12462-v1
  ADD	LINK	MirGeneDB	cpo-mir-320	Cpo-Mir-320

[ EXAMPLE OUTPUT: MISSING LOCATION BATCH ]
  # Separates sequences lacking valid chromosome, start, or end coordinates
  # to prevent database insertion errors.
  ADD	HAIRPIN	example-mir-novel...
