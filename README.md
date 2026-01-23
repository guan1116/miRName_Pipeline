# miRName: The Orthology-Guided miRNA Annotation Pipeline

**miRName** is a specialized bioinformatics pipeline and curation platform designed for the automated, orthology-based naming of microRNAs (miRNAs) across diverse metazoan species.

While traditional annotation tools often assign names sequentially (e.g., mir-1, mir-2) without regard for evolutionary history, miRName prioritizes evolutionary orthology. It employs a multi-stage analysis pipeline to cluster sequences and utilizes a strict **"Top-Hit" evidence system**. This ensures that newly annotated miRNAs are named consistently with their homologs in the miRBase registry.

> **Key Goal:** Facilitate the transition from raw sequencing candidates to official database entries, solving critical issues of synonym conflicts and lineage fragmentation.

---

## Table of Contents
- [Naming Logic](#naming-logic)
- [The Pipeline Workflow](#the-pipeline-workflow)
- [Installation](#installation)
- [Usage](#usage)
- [Web Interface](#web-interface)
- [Output](#output)

---

## Naming Logic

What constitutes a valid miRNA name in miRName is based on strict sequence identity and orthology rules encoded in the **Naming Engine (Programme 4)**.

| Naming Criteria | Resulting Nomenclature |
| :--- | :--- |
| **Identity > 95%**<br>(to a known miRBase entry) | **Strict Top-Hit Override.**<br>The suffix is forced to match the homolog (e.g., *mir-30b* becomes *mir-30b*), overriding any sequential clustering. |
| **Identity < 95%**<br>(Novel/Ambiguous) | **Sequential Assignment.**<br>Suffixes (a, b, c...) are assigned based on clustering order within the family. |
| **Absence of Isoform 'a'**<br>(e.g., only 'b' found) | **Gap Preservation.**<br>The system does not back-fill 'a'. This reflects potential gene loss or expression heterogeneity in the specific sample. |
| **Novel Family**<br>(No homologs found) | Assigned a temporary **Novel-ID** until unified by cross-species analysis. |

---

## The Pipeline Workflow

miRName is composed of a data ingestion module, a wrapper runner, and four sequential sub-programmes.

[Image of miRName bioinformatics pipeline flowchart]

### 🔹 Data Ingestion (`transfers_mirsubmit2mirname.py`)
* **Function:** Bridges the user submission interface (miRSubmit) and the core database (miRName).
* **Role:** Extracts candidate miRNA data (sequences, reads, metadata) and species information, populates the SQL database, and flags sequences for processing (`Status=1`).

### 🔹 The Wrapper Runner (`naming_runner_mirbaseDB.py`)
* **Function:** The master controller.
* **Role:** Monitors the database for pending tasks, manages file locking to prevent race conditions, and orchestrates the execution of Programmes 1 through 4. It also handles error logging and FASTA generation.

### 🔹 Programme 1: Identification (`naming_programme1.py`)
* **Function:** Pre-processing and initial identification.
* **Role:** Parses GFF3/FASTA inputs and maps candidates to the reference genome context. Prepares the dataset for homology searching.

### 🔹 Programme 2: Homology Search (`naming_programme2_mirbaseDB.py`)
* **Function:** BLAST against the miRBase database.
* **Role:** Performs local BLAST searches against `hairpin.fa`. Categorizes hits into "Same Species" (paralogs) and "Different Species" (orthologs) to establish evolutionary context.

### 🔹 Programme 3: Evidence Integration (`naming_programme3.py`)
* **Function:** Filtering and Evidence Association.
* **Role:** Integrates mature sequence data with hairpin BLAST results. Compares candidate mature sequences against known MIMAT entries to determine precise mature/star boundaries.

### 🔹 Programme 4: The Naming Engine (`cleaned_naming_programme4.py`)
* **Function:** Clustering and Final Naming.
* **Role:**
    1.  **Clustering:** Groups sequences into families based on mature sequence identity.
    2.  **Orthology Enforcement:** Applies the V4.0 logic to override names based on >95% identity matches.
    3.  **Database Commit:** Writes final suggestions and alignment statistics to SQL for web curation.

---

## Installation

miRName consists of backend Python scripts and a Django web application. It is recommended to use a **conda** environment.

### Dependencies

* python >= 3.9
* pandas
* numpy
* biopython
* sqlalchemy
* pymysql
* django
* jellyfish
* portalocker
* ncbi-blast+

> **Note regarding RNAfold:** Unlike miRScore or other prediction tools, the miRName naming pipeline **does not require** the ViennaRNA package (RNAfold) for its core naming steps. Structural validation is assumed to have been performed upstream.

---

## Usage

miRName is typically deployed as a server-side pipeline.

### 1. Data Transfer (Ingestion)
Migrate user submissions to the processing queue:
```bash
python transfers_mirsubmit2mirname.py
