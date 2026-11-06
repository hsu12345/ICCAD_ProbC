#!/usr/bin/env python3
"""
Run a short DREAMPlace global placement to relocate cells and reduce HPWL.
- Supports Bookshelf (.aux + .pl) or LEF/DEF (.lef + .def [+ .v])
- Prints HPWL before/after
- Writes updated DEF to results/<design>/<design>.gp.def

OPTIMIZATION SETTINGS:
- Quadratic density penalty is DISABLED for faster execution
- Density weight updates are FORCED to be based on HPWL
- This ensures consistent fast placement behavior

OVERRIDES (CLI flags or environment variables):
- --iteration INT                  | HPWL_ITERATION
- --learning-rate FLOAT            | HPWL_LEARNING_RATE
- --target-density FLOAT           | HPWL_TARGET_DENSITY
- --density-weight FLOAT           | HPWL_DENSITY_WEIGHT
- --ignore-net-degree INT          | HPWL_IGNORE_NET_DEGREE
- --enable-fillers 0|1             | HPWL_ENABLE_FILLERS
- --enable-density-weight-update 0|1 | HPWL_ENABLE_DENSITY_WEIGHT_UPDATE
"""

import sys
import os
import json
import glob
from typing import Any, Dict, Optional

# Add DREAMPlace install directory to path
ROOT = os.path.dirname(__file__)
INSTALL_DIR = os.path.join(ROOT, "install")
DREAMPLACE_DIR = os.path.join(INSTALL_DIR, "dreamplace")
for p in (INSTALL_DIR, DREAMPLACE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import Params
    import PlaceDB
    import NonLinearPlace
    import Timer
except ImportError as e:
    print(f"Error: cannot import DREAMPlace modules: {e}")
    print("Make sure DREAMPlace is built and 'install/' exists next to this script.")
    sys.exit(1)


def get_asap7_lef_files():
    """Collect ASAP7 tech + stdcell + SRAM LEFs if present locally.
    Search order:
      1) <this_dir>/ASAP7/{techlef,LEF}
      2) <repo_root>/testcases/ASAP7/{techlef,LEF}
    """
    lefs = []

    # Location 1: alongside this script
    tech1 = os.path.join(ROOT, "ASAP7", "techlef", "asap7_tech_1x_201209.lef")
    cell_dir1 = os.path.join(ROOT, "ASAP7", "LEF")

    # Location 2: sibling testcases/ASAP7 relative to DREAMPlace directory
    repo_root = os.path.abspath(os.path.join(ROOT, os.pardir))
    tech2 = os.path.join(repo_root, "testcases", "ASAP7", "techlef", "asap7_tech_1x_201209.lef")
    cell_dir2 = os.path.join(repo_root, "testcases", "ASAP7", "LEF")

    for tech_path, cell_dir in ((tech1, cell_dir1), (tech2, cell_dir2)):
        if os.path.exists(tech_path) and tech_path not in lefs:
            lefs.append(tech_path)
        if os.path.isdir(cell_dir):
            for lf in sorted(glob.glob(os.path.join(cell_dir, "*.lef"))):
                if lf not in lefs:
                    lefs.append(lf)

    return lefs


def _parse_cli_overrides(argv) -> Dict[str, Optional[str]]:
    """Parse known --flags from argv without disturbing positional inputs.
    Supports both --key=value and --key value forms.
    Returns string values; caller casts as needed.
    """
    keys = {
        "iteration": None,
        "learning-rate": None,
        "target-density": None,
        "density-weight": None,
        "ignore-net-degree": None,
        "enable-fillers": None,
        "enable-density-weight-update": None,
    }

    i = 0
    while i < len(argv):
        tok = argv[i]
        if not tok.startswith("--"):
            i += 1
            continue
        if "=" in tok:
            name, val = tok[2:].split("=", 1)
        else:
            name = tok[2:]
            val = argv[i + 1] if (i + 1) < len(argv) else None
            # If next token is another flag or missing, treat as None
            if isinstance(val, str) and val.startswith("--"):
                val = None
            else:
                i += 1  # consume value token
        if name in keys:
            keys[name] = val
        i += 1
    return keys


def _get_env_override(name: str) -> Optional[str]:
    return os.getenv(name)


def _apply_overrides(params: Any, overrides: Dict[str, Optional[str]]):
    """Apply CLI/env overrides to Params in-place."""
    # Stage-level overrides
    stage = params.global_place_stages[0] if params.global_place_stages else None
    if stage is None:
        return

    def _choose(cli_key: str, env_key: str) -> Optional[str]:
        cli_val = overrides.get(cli_key)
        if cli_val is not None:
            return cli_val
        return _get_env_override(env_key)

    v = _choose("iteration", "HPWL_ITERATION")
    if v is not None:
        try:
            stage["iteration"] = int(float(v))
        except ValueError:
            print(f"Warning: invalid iteration '{v}', ignoring")

    v = _choose("learning-rate", "HPWL_LEARNING_RATE")
    if v is not None:
        try:
            stage["learning_rate"] = float(v)
        except ValueError:
            print(f"Warning: invalid learning-rate '{v}', ignoring")

    v = _choose("target-density", "HPWL_TARGET_DENSITY")
    if v is not None:
        try:
            params.target_density = float(v)
        except ValueError:
            print(f"Warning: invalid target-density '{v}', ignoring")

    v = _choose("density-weight", "HPWL_DENSITY_WEIGHT")
    if v is not None:
        try:
            params.density_weight = float(v)
        except ValueError:
            print(f"Warning: invalid density-weight '{v}', ignoring")

    v = _choose("ignore-net-degree", "HPWL_IGNORE_NET_DEGREE")
    if v is not None:
        try:
            params.ignore_net_degree = int(float(v))
        except ValueError:
            print(f"Warning: invalid ignore-net-degree '{v}', ignoring")

    v = _choose("enable-fillers", "HPWL_ENABLE_FILLERS")
    if v is not None:
        try:
            params.enable_fillers = 1 if int(float(v)) != 0 else 0
        except ValueError:
            print(f"Warning: invalid enable-fillers '{v}', ignoring")

    v = _choose("enable-density-weight-update", "HPWL_ENABLE_DENSITY_WEIGHT_UPDATE")
    if v is not None:
        try:
            params.enable_density_weight_update = 1 if int(float(v)) != 0 else 0
        except ValueError:
            print(f"Warning: invalid enable-density-weight-update '{v}', ignoring")


def make_params_for_run(args):
    """Create and customize Params for a short wirelength-driven run."""
    params = Params.Params()

    # Detect format from args
    # Usage patterns:
    #  - minimize_hpwl.py <aux_file> [pl_file]
    #  - minimize_hpwl.py <def_file> <comma_separated_lefs> [verilog_file]
    if len(args) < 2:
        print("Usage:")
        print("  Bookshelf: python minimize_hpwl.py path/to/design.aux [path/to/design.pl]")
        print("  LEF/DEF:   python minimize_hpwl.py path/to/design.def tech.lef,cells.lef [design.v] [--flags]")
        sys.exit(1)

    in1 = args[1]
    if in1.lower().endswith(".aux"):
        # Bookshelf
        params.aux_input = in1
        if len(args) >= 3 and args[2].lower().endswith(".pl"):
            pass
        design_name = os.path.splitext(os.path.basename(in1))[0]
    elif in1.lower().endswith(".def"):
        # LEF/DEF
        params.def_input = in1
        if len(args) >= 3 and args[2].strip() and not args[2].startswith("--"):
            lefs = args[2].split(",") if "," in args[2] else [args[2]]
            params.lef_input = [lef.strip() for lef in lefs if lef.strip()]
        else:
            # Auto-detect ASAP7 LEFs
            auto_lefs = get_asap7_lef_files()
            if not auto_lefs:
                print("Error: LEF file(s) required when using DEF input and no ASAP7 LEFs were found.")
                print("Hint: provide LEFs as a comma-separated list, or place ASAP7/techlef and ASAP7/LEF under this repo root.")
                sys.exit(1)
            params.lef_input = auto_lefs
            print("Using auto-detected LEFs:")
            for lf in params.lef_input:
                print(f"  - {lf}")
        if len(args) >= 4 and args[3].lower().endswith((".v", ".verilog")):
            params.verilog_input = args[3]
        design_name = os.path.splitext(os.path.basename(in1))[0]
    else:
        print("Error: first argument must be .aux (Bookshelf) or .def (LEF/DEF)")
        sys.exit(1)

    # Minimal, fast global placement pass focused on wirelength
    # FORCE: Disable quadratic density penalty and use HPWL-based density weight updates
    params.global_place_stages = [{
        "num_bins_x": 0,
        "num_bins_y": 0,
        "iteration": 200,
        "learning_rate": 0.02,
        "wirelength": "weighted_average",
        "optimizer": "nesterov",
        "Llambda_density_weight_iteration": 1,
        "Lsub_iteration": 1
    }]
    params.target_density = 0.99
    params.density_weight = 8e-6
    params.ignore_net_degree = 100
    params.enable_fillers = 1
    
    # FORCE: Disable quadratic density penalty for faster execution
    params.quadratic_penalty = 0  # Explicitly disable quadratic penalty
    params.density_weight_update = "hpwl"  # Force HPWL-based density weight updates
    params.enable_density_weight_update = 1  # Enable density weight updates

    params.global_place_flag = 1
    params.legalize_flag = 0
    params.detailed_place_flag = 0

    params.dtype = "float32"
    params.result_dir = os.path.join("results")

    # Apply CLI/env overrides after defaults are set
    overrides = _parse_cli_overrides(args)
    _apply_overrides(params, overrides)

    return params, design_name


def hpwl_of_db(db):
    return db.hpwl(db.node_x, db.node_y)


def main():
    params, design = make_params_for_run(sys.argv)

    # Echo LEFs if any for clarity (helps diagnose missing-pin issues)
    if getattr(params, "lef_input", None):
        print("LEFs in use (order matters, tech first):")
        for lf in params.lef_input:
            print(f"  - {lf}")

    placedb = PlaceDB.PlaceDB()
    placedb(params)
    hpwl_before = hpwl_of_db(placedb)
    print(f"Initial HPWL: {hpwl_before:.6e}")

    timer = None
    placer = NonLinearPlace.NonLinearPlace(params, placedb, timer)
    _ = placer(params, placedb)

    hpwl_after = hpwl_of_db(placedb)
    print(f"Final   HPWL: {hpwl_after:.6e}")
    improvement = (hpwl_before - hpwl_after) / max(hpwl_before, 1e-9)
    print(f"Improvement: {improvement*100:.2f}%")

    out_dir = os.path.join(params.result_dir, design)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"{design}.gp.{params.solution_file_suffix()}")
    placedb.write(params, out_file)
    print(f"Wrote updated placement to: {out_file}")


if __name__ == "__main__":
    main()
