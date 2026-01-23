miRName: The Orthology-Guided miRNA Annotation Pipeline
Table of Contents
Overview
The Pipeline Workflow
Installation
Usage
Naming Logic
Web Interface
Output
FAQ
Overview
miRName is a specialized bioinformatics pipeline and curation platform designed for the automated, orthology-based naming of microRNAs (miRNAs) across diverse metazoan species.
While traditional annotation tools often assign names sequentially (e.g., mir-1, mir-2) without regard for evolutionary history, miRName prioritizes evolutionary orthology. It employs a multi-stage analysis pipeline to cluster sequences and utilizes a strict "Top-Hit" evidence system. This ensures that newly annotated miRNAs are named consistently with their homologs in the miRBase registry (e.g., ensuring a sequence homologous to miR-30d is named miR-30d, even if miR-30a is absent in the dataset).
miRName facilitates the transition from raw sequencing candidates to official database entries, solving the critical issues of synonym conflicts and lineage fragmentation.
Determining Naming Conventions
What constitutes a valid miRNA name in miRName is based on strict sequence identity and orthology rules encoded in the Naming Engine (Programme 4). Here is a summary of the criteria:
| Naming Criteria | Resulting Nomenclature |
| Identity > 95% to a known miRBase entry | Strict Top-Hit Override. The suffix is forced to match the homolog (e.g., mir-30b becomes mir-30b), overriding any sequential clustering. |
| Identity < 95% (Novel/Ambiguous) | Sequential Assignment. Suffixes (a, b, c...) are assigned based on clustering order within the family. |
| Absence of Isoform 'a' (e.g., only 'b' found) | Gap Preservation. The system does not back-fill 'a'. This reflects potential gene loss or expression heterogeneity in the specific sample. |
| Novel Family (No homologs found) | Assigned a temporary Novel-ID until unified by cross-species analysis. |
The Pipeline Workflow
miRName is composed of a data ingestion module, a wrapper runner, and four sequential sub-programmes.
🔹 Data Ingestion (transfers_mirsubmit2mirname.py)
Function: Bridges the user submission interface (miRSubmit) and the core database (miRName).
Role: Extracts candidate miRNA data (sequences, reads, metadata) and species information, populates the SQL database, and flags sequences for processing (Status=1).
🔹 The Wrapper Runner (naming_runner_mirbaseDB.py)
Function: The master controller. It monitors the database for pending tasks, manages file locking to prevent race conditions, and orchestrates the execution of Programmes 1 through 4.
Role: Generates necessary FASTA files and handles error logging during the pipeline execution.
🔹 Programme 1: Identification (naming_programme1.py)
Function: Pre-processing and initial identification.
Role: Parses GFF3/FASTA inputs and maps candidates to the reference genome context. It prepares the dataset for homology searching.
🔹 Programme 2: Homology Search (naming_programme2_mirbaseDB.py)
Function: BLAST against the miRBase database.
Role: Performs local BLAST searches against hairpin.fa. It categorizes hits into "Same Species" (paralogs) and "Different Species" (orthologs) to establish evolutionary context.
🔹 Programme 3: Evidence Integration (naming_programme3.py)
Function: Filtering and Evidence Association.
Role: Integrates mature sequence data with hairpin BLAST results. It compares candidate mature sequences against known MIMAT entries to determine precise mature/star boundaries and sequence identity.
🔹 Programme 4: The Naming Engine (cleaned_naming_programme4.py)
Function: Clustering and Final Naming.
Role: 1. Clustering: Groups sequences into families based on mature sequence identity.
2. Orthology Enforcement: Applies the V4.0 logic to override names based on >95% identity matches.
3. Database Commit: Writes the final suggestions and alignment statistics back to the SQL database for web curation.
Installation
miRName consists of backend Python scripts and a Django web application.
Dependencies
The following packages are required. It is recommended to use a conda environment:
python >= 3.9
pandas
numpy
biopython
sqlalchemy
pymysql
django
jellyfish
portalocker
ncbi-blast+
Note regarding RNAfold: Unlike miRScore or other prediction tools, the miRName naming pipeline does not require the ViennaRNA package (RNAfold) for its core naming and orthology assignment steps. Structural validation is assumed to have been performed upstream.
Usage
miRName is typically deployed as a server-side pipeline.
1. Data Transfer (Ingestion)
Migrate user submissions to the processing queue:
python transfers_mirsubmit2mirname.py



2. Run the Pipeline (The Wrapper)
Execute the runner to process all pending sequences in the database. This script will automatically call P1, P2, P3, and P4.
python naming_runner_mirbaseDB.py



Note: This script handles locking automatically. Ensure hairpin.fa is present in the directory.
3. Web Server (Django)
Start the Django server to access the curation interface:
python manage.py runserver 0.0.0.0:8000



Web Interface
The miRName web interface provides a powerful dashboard for manual curation and final validation.
Curation Features
Alignment Visualization: Inspect detailed BLAST alignments between the candidate hairpin and known homologs.
Smart Submit Page: Batch validate pending candidates. This function respects the algorithm's original db_decision (Input vs. Reject) unless manually overridden by the curator.
Reject Page: A dedicated button to forcefully reject all items on the current page to filter out low-quality noise quickly.
Update Species Abbreviation: A batch tool to correct species prefixes (e.g., correcting Pab- to PaE-) across the entire submission while maintaining data integrity.
Output
Once curation is complete, users can generate the final submission files directly from the web interface.
1. Validated List (miRBase Format)
Clicking "Export Validated" generates a relational text file strictly adhering to miRBase submission standards.


Example:
INSERT	FAMILY	let-7
INSERT	HAIRPIN	pae-let-7a	Pab-Let-7-P1	Predicted miRNA	UGAGGUAG...	.	pae	let-7	Chr_Un	+	10	90
INSERT	MATURE	pae-let-7a-5p	experimental	sequenced
INSERT	HAIRPIN2MATURE	5	26	pae-let-7a	pae-let-7a-5p



