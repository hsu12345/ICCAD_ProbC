# ICCAD 2025 CAD Contest — Problem C

**Incremental Placement Optimization Beyond Detailed Placement: Simultaneous Gate Sizing, Buffering, and Cell Relocation** (NVIDIA)

This repository holds our submission for Problem C, which received an Honorable Mention in the domestic round of the 2025 CAD Contest.

- **Project report:** [`Report.pdf`](Report.pdf). It covers the method, results and project timeline.
- **Problem statement:** [`C_20250903.pdf`](C_20250903.pdf) (revision 2025-09-03).

Ting-Yao Huang and Cheng-Jui Hsu, advised by Prof. Wai-Kei Mak (National Tsing Hua University, Department of Electrical Engineering).

## Problem summary

We start from a legal seed placement of an ASAP7 design and improve power, performance and area (PPA) with three kinds of change:

1. **Cell relocation**: moving standard cells and macros.
2. **Gate sizing**: `size_cell <cellName> <libCellName>`. The new cell must have the same logic function.
3. **Buffering**: `insert_buffer {<load pins>} <lib buffer> <new cell> <new net>`, or the `-inverter_pairs` form. These follow PrimeTime syntax.

The result must stay legal: every cell on a valid site, no overlaps, and IO ports and fixed cells unmoved.

**Score per design:** `S = 1000·P − 50·D − 30·R`

| Term | Meaning |
|---|---|
| `P` | `α·TNS_norm + β·Power_norm + γ·WL_norm`, measured with OpenROAD. The weights change per testcase. |
| `D` | Average Manhattan displacement per cell, in site units |
| `R` | Runtime, normalised against a reference |

All three terms are normalised against the *seed*, which is the average of all teams' legal solutions.

**Evaluation machine:** Docker on Ubuntu 20.04, 8 vCPUs, 32 GB RAM, 1× A100 40 GB, CUDA 11.8, conda env `probC_env` (Python 3.9).

## Repository layout

```
ICCAD_ProbC/
├── C_20250903.pdf            # Official problem statement
├── Report.pdf                # Project report
├── ASAP7/                    # ASAP7 libraries: LIB/ (.lib), LEF/, techlef/, setRC.tcl
├── ICCAD25_testcases/        # Official testcases (same content as solution/testcases/)
├── ICCAD_ProbC_ENV/          # Official Dockerfile, Mambaforge installer, probC_env.yaml
├── openRoad_eval_script/
│   └── eval_def.tcl          # OpenROAD script: report_tns / report_wns / report_power
└── solution/                 # Submission root (packed as solution.tar.gz)
    ├── setup_environment.sh  # Run first by the organisers: system deps + DREAMPlace build
    ├── run.sh                # Run second: ./run.sh <design> <α> <β> <γ>
    ├── run_buffer_insertion.sh  # Same as run.sh but never runs DREAMPlace
    ├── run_hpwl.sh           # Runs only the DREAMPlace HPWL pass on an existing <design>.sol.def
    ├── scripts/
    │   ├── insta_optimization_new.py   # Builds the changelist from INSTA timing data
    │   ├── apply_changelist_to_def.py  # Applies the changelist, legalises new cells, writes .sol.def
    │   └── calc_tns.py                 # Setup TNS over timing endpoints, from pin_feats.csv
    ├── DREAMPlace/           # Vendored DREAMPlace source plus minimize_hpwl.py
    ├── calc_hpwl.py          # HPWL of a DEF file (uses DREAMPlace's PlaceDB)
    ├── compare_hpwl.py       # HPWL of seed DEF vs. optimised DEF
    ├── calc_all_initial_hpwl.sh  # Seed HPWL for all six designs → results/initial_hpwl/
    ├── testcases/            # Testcases + ASAP7, in the layout the organisers provide
    └── <design>.sol.{def,changelist}  # Latest outputs for each design
```

### Testcases

| Design | Cells (seed DEF) |
|---|---|
| des | 2,317 |
| aes | 4,393 |
| ac97_top | 7,750 |
| aes_cipher_top | 11,630 |
| pci_bridge32 | 12,091 |
| ariane | 105,730 |

Each design folder has the netlist (`.v`), the placement (`.def`), Bookshelf files (`.aux/.nodes/.nets/.pl/.scl/.wts`), SDC constraints, SPEF parasitics and an `INSTA_<design>_*/insta_inputs/` folder. That folder holds the timing features the optimiser reads: `pin_feats.csv`, `net_arcs.csv`, `cell_arcs.csv`, `cell_2_libCell.csv`, `all_available_lib_cells.csv` and others.

> `ariane.spef` and `cell_arcs.csv` are larger than GitHub's 100 MB limit, so `.gitignore` leaves them out. Copy them in separately.

## Setup

```bash
# Build and enter the official container
cd ICCAD_ProbC/ICCAD_ProbC_ENV
docker build -t iccad25_probc_env .
docker run --gpus all -it -v <path>/ICCAD_ProbC:/workspace -w /workspace iccad25_probc_env:latest bash

# Inside the container
cd /workspace/solution
bash setup_environment.sh     # apt deps, pip deps, builds DREAMPlace into DREAMPlace/install/
```

`setup_environment.sh` expects the DREAMPlace source at `/workspace/solution/DREAMPlace`, and it runs `git submodule update` for OpenTimer, munkres-cpp, cub and pybind11.

## Running

```bash
cd solution
./run.sh <design_name> <TNS_weight α> <power_weight β> <WL_weight γ>
# e.g.
./run.sh aes 5.0 1.0 1.0
```

The outputs, `<design>.sol.def` and `<design>.sol.changelist`, are written to `solution/`. Intermediate DREAMPlace results go to `solution/results/`.

To score a result, edit the `read_def` and `read_sdc` paths in `openRoad_eval_script/eval_def.tcl` and run it with OpenROAD.

## Pipeline

`run.sh` has three stages.

### 1. Choose a branch

`calc_tns.py` computes the signed setup TNS over timing endpoints. Then `ratio = #cells / |TNS|`.

| Condition | INSTA optimiser | DREAMPlace HPWL pass |
|---|---|---|
| ratio > 10 and α > 10·(β+γ) (timing dominates) | `--timing-weight 1 --power-weight 1` | skipped |
| ratio > 10 and 3α < β+γ (power and WL dominate) | skipped (empty changelist) | default settings |
| ratio > 10, any other weights | `--timing-weight 1 --power-weight 1` | gentle: 1 iteration, lr 5e-4, density 0.70, fillers off |
| ratio ≤ 10, or TNS unavailable | `--timing-weight 5 --power-weight 1` | default settings |

### 2. Build the changelist: `scripts/insta_optimization_new.py`

- Loads the INSTA CSVs and the DEF component list. It maps escaped DEF names such as `reg\[0\]` to the unescaped INSTA names.
- **Gate sizing is disabled.** `optimize()` returns an empty sizing list. The helpers that pick sizing candidates (`find_gate_sizing_candidates`, `generate_gate_sizing_commands`) are still in the file.
- **Buffer insertion:**
  - Every net arc (driver → sink) is a candidate, scored as `max(delay_rise, delay_fall)·timing_weight + 0.1·fanout`.
  - The fraction of candidates kept (30–100%) is set by `_calculate_buffer_insertion_percentage()`. It is driven by the share of pins with negative slack, the average negative slack and the timing weight.
  - The buffer drive strength (x1/x4/x8/x16) depends on net delay. A power weight above 1 makes it prefer smaller buffers.
  - Each kept arc becomes `insert_buffer {<driver pin>} <BUF> BUF_opt_NNNNNN NET_BUF_opt_NNNNNN`.

### 3. Apply and legalise: `scripts/apply_changelist_to_def.py`

- Parses the DEF (rows, sites, DIEAREA, COMPONENTS, NETS) and the LEF macro sizes. NETS and LEF parsing run in parallel.
- Places each new buffer near its target using per-row occupancy intervals: same row first, then the bounding box, then anywhere in the design. It updates the NETS section and the COMPONENTS count.
- Rewrites the changelist so that it keeps only the commands that were placed successfully.
- Environment flags: `FAST` (default 1), `SKIP_HPWL` (default 1), `NETS_WORKERS`, `LEF_WORKERS` (default: all CPUs).

### 4. Optional HPWL pass: `DREAMPlace/minimize_hpwl.py`

A short DREAMPlace global placement: Nesterov optimiser, weighted-average wirelength, 200 iterations, target density 0.99, quadratic density penalty off. Its output `results/<design>.sol/<design>.sol.gp.def` replaces `<design>.sol.def`. You can override settings with CLI flags or environment variables: `--iteration`/`HPWL_ITERATION`, `--learning-rate`, `--target-density`, `--density-weight`, `--ignore-net-degree`, `--enable-fillers`, `--enable-density-weight-update`.

## Results

These come from [`Report.pdf`](Report.pdf), §4. They were measured with OpenROAD with equal weights (α = β = γ = 1), against the original seed placement. Positive numbers are improvements.

| Design | TNS | Power | HPWL |
|---|---|---|---|
| ac97_top | 95.9% | −15.9% | 14.5% |
| aes | 100% | 80.0% | 7.9% |
| aes_cipher_top | 98.3% | 91.3% | 35.0% |
| ariane | 91.8% | −61.2% | 75.2% |
| des | 100% | 84.9% | 38.4% |
| pci_bridge32 | 94.1% | −51.0% | 19.5% |

TNS and HPWL improve on every design. Power gets worse on ac97_top and pci_bridge32, which had by far the worst seed TNS, and on ariane, the largest design. See the report for the raw values and a discussion.

## Current outputs

These are the `<design>.sol.*` files currently in `solution/`:

| Design | Seed cells | Solution cells | `insert_buffer` | `size_cell` |
|---|---|---|---|---|
| des | 2,317 | 4,275 | 1,958 | 0 |
| aes | 4,393 | 14,935 | 10,542 | 0 |
| ac97_top | 7,750 | 22,637 | 14,887 | 0 |
| aes_cipher_top | 11,630 | 29,484 | 17,854 | 0 |
| pci_bridge32 | 12,091 | 39,962 | 27,871 | 0 |
| ariane | 105,730 | 191,304 | 85,574 | 0 |
