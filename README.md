# miRName: The Orthology-Guided miRNA Annotation Pipeline

> **Note:**
> This repository serves as a **codebase demonstration** for the production pipeline developed at The University of Manchester.
> * **Bin/**: Contains the core algorithmic logic (Programmes 1-4).
> * **Screenshots**: Below demonstrate the deployed web interface used for high-throughput curation.
> * **Data**: Uses anonymized demo data for privacy compliance.

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

**miRName** is a specialized bioinformatics pipeline designed for the **automated, orthology-based naming** of microRNAs (miRNAs) across diverse metazoan species.

Unlike traditional tools that assign names sequentially (e.g., *mir-1*, *mir-2*) without regard for evolutionary history, **miRName prioritizes evolutionary orthology**. It employs a multi-stage analysis pipeline to cluster sequences and utilizes a strict **"Top-Hit" evidence system**, ensuring new annotations are consistent with the miRBase registry.

**Key Goal:** Facilitate the transition from raw sequencing candidates to official database entries, resolving synonym conflicts and lineage fragmentation.

---

## Naming Logic

The core naming logic is enforced by the scripts located in the `Bin/` directory.

| Criteria | Action |
| :--- | :--- |
| **Identity > 95%**<br>(to known homolog) | **Strict Top-Hit Override.**<br>Forces the name to match the homolog (e.g., *mir-30b*), overriding sequential clustering. |
| **Identity < 95%**<br>(Novel/Ambiguous) | **Sequential Assignment.**<br>Suffixes (a, b, c...) assigned based on clustering order. |
| **Novel Family** | Assigned a temporary **Novel-ID** until unified by cross-species analysis. |

---

## Project Architecture

The pipeline follows a modular architecture controlled by a master wrapper.

### Directory Structure
* **root**: Contains the wrapper runners and ingestion scripts.
* **Bin/**: Contains the core logic modules (P1 to P4).
* **TestData/**: Contains anonymized input files for demonstration.

### The Workflow Components

**1. Data Ingestion (transfers_mirsubmit2mirname.py)**
Bridges the submission interface (miRSubmit) and the SQL database. Extracts metadata and populates the processing queue.

**2. The Wrapper (naming_runner_mirbaseDB.py)**
* **Master Controller**: Monitors the database for pending tasks.
* **Concurrency**: Manages file locking to prevent race conditions on the HPC.
* **Orchestration**: Automatically calls the sub-programmes located in `Bin/`.

**3. Core Modules (Located in Bin/)**
* `naming_programme1.py`: **Identification** - Maps candidates to genome context.
* `naming_programme2_mirbaseDB.py`: **Homology Search** - Local BLAST against miRBase.
* `naming_programme3.py`: **Evidence Integration** - Defines mature/star boundaries.
* `cleaned_naming_programme4.py`: **The Naming Engine** - Clusters sequences and applies V4.0 logic.

---

## Installation & Dependencies

Recommended to run within a `conda` environment.

```text
python >= 3.9
pandas
numpy
biopython
sqlalchemy
pymysql
django
ncbi-blast+
