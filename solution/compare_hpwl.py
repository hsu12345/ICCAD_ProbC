#!/usr/bin/env python3
"""
Compare HPWL between initial and optimized DEF files.
Usage: python3 compare_hpwl.py <initial.def> <optimized.def>
"""

import sys
import os

# Add current directory for calc_hpwl import
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from calc_hpwl import calc_hpwl


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 compare_hpwl.py <initial.def> <optimized.def>")
        print("\nExample:")
        print("  python3 compare_hpwl.py testcases/des/des.def des.sol.def")
        sys.exit(1)
    
    initial_def = sys.argv[1]
    optimized_def = sys.argv[2]
    
    # Check files exist
    if not os.path.exists(initial_def):
        print(f"Error: Initial DEF not found: {initial_def}")
        sys.exit(1)
    
    if not os.path.exists(optimized_def):
        print(f"Error: Optimized DEF not found: {optimized_def}")
        sys.exit(1)
    
    print("="*60)
    print("HPWL Comparison")
    print("="*60)
    print()
    
    # Calculate initial HPWL
    print(f"Calculating HPWL for: {initial_def}")
    initial_hpwl = calc_hpwl(initial_def, verbose=False)
    print(f"Initial HPWL:   {initial_hpwl:.6e} ({initial_hpwl:,.0f})")
    print()
    
    # Calculate optimized HPWL
    print(f"Calculating HPWL for: {optimized_def}")
    optimized_hpwl = calc_hpwl(optimized_def, verbose=False)
    print(f"Optimized HPWL: {optimized_hpwl:.6e} ({optimized_hpwl:,.0f})")
    print()
    
    # Calculate difference
    delta = optimized_hpwl - initial_hpwl
    ratio = optimized_hpwl / initial_hpwl if initial_hpwl > 0 else 0
    improvement = (initial_hpwl - optimized_hpwl) / initial_hpwl * 100 if initial_hpwl > 0 else 0
    
    print("="*60)
    print("Results:")
    print("="*60)
    print(f"Delta:        {delta:+.6e} ({delta:+,.0f})")
    print(f"Ratio:        {ratio:.4f}×")
    
    if improvement >= 0:
        print(f"Improvement:  {improvement:.2f}% reduction ✓")
    else:
        print(f"Improvement:  {improvement:.2f}% (increased) ✗")
    
    print("="*60)


if __name__ == "__main__":
    main()

