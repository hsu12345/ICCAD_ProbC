#!/usr/bin/env python3
"""
Calculate HPWL from a DEF file without running optimization.
Usage: python3 calc_hpwl.py <design.def>
"""

import sys
import os
import glob

# Add DREAMPlace to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INSTALL_DIR = os.path.join(SCRIPT_DIR, "DREAMPlace", "install")
DREAMPLACE_DIR = os.path.join(INSTALL_DIR, "dreamplace")

for p in (INSTALL_DIR, DREAMPLACE_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import Params
    import PlaceDB
except ImportError as e:
    print(f"Error: Cannot import DREAMPlace modules: {e}")
    print("Make sure DREAMPlace is built and 'install/' exists.")
    sys.exit(1)


def get_asap7_lef_files():
    """Get ASAP7 LEF files from testcases directory."""
    lefs = []
    
    # Tech LEF
    tech_lef = os.path.join(SCRIPT_DIR, "testcases", "ASAP7", "techlef", "asap7_tech_1x_201209.lef")
    if os.path.exists(tech_lef):
        lefs.append(tech_lef)
    else:
        # Try parent directory
        parent_dir = os.path.dirname(SCRIPT_DIR)
        tech_lef = os.path.join(parent_dir, "ASAP7", "techlef", "asap7_tech_1x_201209.lef")
        if os.path.exists(tech_lef):
            lefs.append(tech_lef)
    
    # Cell LEFs
    cell_dir = os.path.join(SCRIPT_DIR, "testcases", "ASAP7", "LEF")
    if not os.path.isdir(cell_dir):
        cell_dir = os.path.join(os.path.dirname(SCRIPT_DIR), "ASAP7", "LEF")
    
    if os.path.isdir(cell_dir):
        for lef_file in sorted(glob.glob(os.path.join(cell_dir, "*.lef"))):
            lefs.append(lef_file)
    
    return lefs


def calc_hpwl(def_file, verbose=True):
    """Calculate HPWL from a DEF file.
    
    Args:
        def_file: Path to DEF file
        verbose: If True, print LEF files being used
    
    Returns:
        float: HPWL value
    """
    params = Params.Params()
    params.def_input = def_file
    
    # Get LEFs
    lefs = get_asap7_lef_files()
    if not lefs:
        print("Error: No ASAP7 LEF files found.")
        print("Expected location: testcases/ASAP7/{techlef,LEF}/")
        sys.exit(1)
    
    params.lef_input = lefs
    
    if verbose:
        print("Using LEF files:")
        for lef in lefs:
            print(f"  - {lef}")
        print()
    
    # Load placement
    placedb = PlaceDB.PlaceDB()
    placedb(params)
    
    # Calculate HPWL
    hpwl = placedb.hpwl(placedb.node_x, placedb.node_y)
    
    return hpwl


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 calc_hpwl.py <design.def> [--quiet]")
        print("\nExample:")
        print("  python3 calc_hpwl.py testcases/des/des.def")
        print("  python3 calc_hpwl.py testcases/aes/aes.def --quiet")
        sys.exit(1)
    
    def_file = sys.argv[1]
    verbose = "--quiet" not in sys.argv
    
    if not os.path.exists(def_file):
        print(f"Error: DEF file not found: {def_file}")
        sys.exit(1)
    
    hpwl = calc_hpwl(def_file, verbose=verbose)
    
    design_name = os.path.splitext(os.path.basename(def_file))[0]
    print(f"Design: {design_name}")
    print(f"HPWL: {hpwl:.6e} ({hpwl:,.0f})")


if __name__ == "__main__":
    main()

