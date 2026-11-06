#!/usr/bin/env python3
"""
Calculate Total Negative Slack (TNS) from INSTA pin features.

Usage:
  python calc_tns.py <insta_dir_or_pin_feats_csv> [--verbose] [--json] [--signed]
                     [--all-pins] [--check {setup,hold}] [--polarity {both,rise,fall}]
                     [--pin-regex REGEX]

- If a directory is provided, the script expects a file named 'pin_feats.csv' inside it.
  It will also try to read 'cell_2_libCell.csv' to better identify timing endpoints.
- If a file is provided, it must be a CSV with columns:
  For setup: 'max_rise_slack' and 'max_fall_slack'
  For hold : 'min_rise_slack' and 'min_fall_slack'

By default, the script computes TNS over timing endpoints only (not all pins),
using both polarities (min of rise/fall slack).
"""

import sys
import os
import csv
import json
import argparse
import re
from typing import Tuple, Dict, Optional


SequentialHints = ("DFF", "SDFF", "REG", "DFFQ", "FF", "LATCH")
ExcludePinSuffix = re.compile(r"(CLK|CK|CP|GATE|SET|RESET|RN|SN|CD|CLR|RST)$", re.IGNORECASE)


def load_cell2lib_map(maybe_dir: str) -> Dict[str, str]:
    """Load cell -> lib_cell map if 'cell_2_libCell.csv' exists in directory."""
    mapping: Dict[str, str] = {}
    csv_path = os.path.join(maybe_dir, "cell_2_libCell.csv")
    if not os.path.isdir(maybe_dir) or not os.path.exists(csv_path):
        return mapping
    try:
        with open(csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cell = row.get("full_name")
                lib = row.get("lib_cell.full_name", "")
                if cell:
                    mapping[cell] = lib or ""
    except Exception:
        return {}
    return mapping


def is_endpoint(full_name: str, direction: str, cell2lib: Dict[str, str], pin_regex: Optional[re.Pattern]) -> bool:
    """Heuristically determine if a pin is a timing endpoint (for setup/hold TNS).

    Rules:
    - Exclude known non-endpoint/control pins by suffix (CLK, RESET, etc.).
    - Prefer input pins ('in') of sequential cells (lib name contains SequentialHints), commonly D pins.
    - Also allow primary outputs if detectable (direction=='out' and cell name indicates a top port).
    - If pin_regex is provided, the pin name must match it.
    """
    # Parse cell and pin
    if "/" in full_name:
        cell, pin = full_name.split("/", 1)
    else:
        cell, pin = full_name, ""

    if pin and ExcludePinSuffix.search(pin):
        return False

    if pin_regex is not None and pin:
        if pin_regex.search(pin) is None:
            return False

    # Sequential input pins are treated as endpoints
    lib = cell2lib.get(cell, "")
    is_seq_cell = any(hint in lib.upper() for hint in SequentialHints)
    if direction == "in" and is_seq_cell:
        return True

    # Try to catch primary outputs (best-effort). INSTA naming varies; include top-level outputs.
    # Heuristic: if cell seems like a primary port bucket (e.g., 'PINS', 'PIN', 'PORT') and direction is 'out'
    if direction == "out" and re.match(r"^(PIN|PINS|PORT|PORTS)$", cell, re.IGNORECASE):
        return True

    return False


def compute_tns_from_csv(csv_path: str, check: str, endpoints_only: bool, cell2lib: Dict[str, str], signed: bool, polarity: str, pin_regex: Optional[str]) -> Tuple[float, int, int, float]:
    """Compute TNS and related metrics from a pin_feats.csv file.

    Args:
        csv_path: path to pin_feats.csv
        check: 'setup' uses max_*_slack; 'hold' uses min_*_slack
        endpoints_only: if True, include only timing endpoints
        cell2lib: optional cell->lib map to identify endpoints
        signed: if True, return negative TNS (sum of negative slacks), else return magnitude
        polarity: 'both' uses min(rise, fall); 'rise' uses rise only; 'fall' uses fall only
        pin_regex: optional regex to further filter endpoint pin names

    Returns:
        (tns_value, critical_pins, total_considered_pins, avg_negative_slack_magnitude)
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"pin features file not found: {csv_path}")

    tns_signed = 0.0
    neg_sum_magnitude = 0.0
    critical_pins = 0
    total_pins = 0

    compiled_pin_regex = re.compile(pin_regex) if pin_regex else None

    use_rise_col = "max_rise_slack" if check == "setup" else "min_rise_slack"
    use_fall_col = "max_fall_slack" if check == "setup" else "min_fall_slack"

    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            full_name = row.get("full_name", "")
            direction = row.get("direction", "")

            if endpoints_only and not is_endpoint(full_name, direction, cell2lib, compiled_pin_regex):
                continue

            total_pins += 1
            try:
                rise_slack = float(row.get(use_rise_col, 0))
            except Exception:
                rise_slack = 0.0
            try:
                fall_slack = float(row.get(use_fall_col, 0))
            except Exception:
                fall_slack = 0.0

            if polarity == "rise":
                selected_slack = rise_slack
            elif polarity == "fall":
                selected_slack = fall_slack
            else:
                selected_slack = min(rise_slack, fall_slack)

            if selected_slack < 0:
                tns_signed += selected_slack
                neg_sum_magnitude += abs(selected_slack)
                critical_pins += 1

    avg_negative_slack = (neg_sum_magnitude / critical_pins) if critical_pins > 0 else 0.0
    tns_value = tns_signed if signed else neg_sum_magnitude
    return tns_value, critical_pins, total_pins, avg_negative_slack


def main():
    parser = argparse.ArgumentParser(description="Compute TNS from INSTA pin features")
    parser.add_argument(
        "path",
        help="Path to INSTA directory containing pin_feats.csv, or a direct path to pin_feats.csv",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print additional metrics (critical pins, total pins, ratios)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )
    parser.add_argument(
        "--signed",
        action="store_true",
        help="Output signed TNS (sum of negative slacks, a negative value)",
    )
    parser.add_argument(
        "--all-pins",
        action="store_true",
        help="Include all pins instead of only timing endpoints",
    )
    parser.add_argument(
        "--check",
        choices=("setup", "hold"),
        default="setup",
        help="Choose which slack to use: setup uses max_*_slack; hold uses min_*_slack",
    )
    parser.add_argument(
        "--polarity",
        choices=("both", "rise", "fall"),
        default="both",
        help="Select which polarity slack to use: both=min(rise,fall)",
    )
    parser.add_argument(
        "--pin-regex",
        default=None,
        help="Regex to filter endpoint pin names (e.g., '^D(\\\\[\\\\d+\\\\])?$|^D\\\\d+$')",
    )

    args = parser.parse_args()

    input_path = os.path.abspath(args.path)
    if os.path.isdir(input_path):
        csv_path = os.path.join(input_path, "pin_feats.csv")
        cell2lib = load_cell2lib_map(input_path)
    else:
        csv_path = input_path
        # Try to infer insta dir for cell2lib by parent directory
        parent_dir = os.path.dirname(csv_path)
        cell2lib = load_cell2lib_map(parent_dir)

    try:
        tns, critical_pins, total_pins, avg_neg = compute_tns_from_csv(
            csv_path=csv_path,
            check=args.check,
            endpoints_only=not args.all_pins,
            cell2lib=cell2lib,
            signed=args.signed,
            polarity=args.polarity,
            pin_regex=args.pin_regex,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        result = {
            "tns": tns,
            "signed": args.signed,
            "mode": args.check,
            "polarity": args.polarity,
            "endpoints_only": not args.all_pins,
            "critical_pins": critical_pins,
            "total_pins": total_pins,
            "criticality_ratio": (critical_pins / total_pins) if total_pins > 0 else 0.0,
            "avg_negative_slack": avg_neg,
            "source": csv_path,
            "pin_regex": args.pin_regex,
        }
        print(json.dumps(result, separators=(",", ":")))
        return

    if args.verbose:
        print(f"TNS: {tns}")
        print(f"signed: {args.signed}")
        print(f"mode: {args.check}")
        print(f"polarity: {args.polarity}")
        print(f"endpoints_only: {not args.all_pins}")
        print(f"pin_regex: {args.pin_regex}")
        print(f"critical_pins: {critical_pins}")
        print(f"total_pins: {total_pins}")
        ratio = (critical_pins / total_pins) if total_pins > 0 else 0.0
        print(f"criticality_ratio: {ratio}")
        print(f"avg_negative_slack: {avg_neg}")
    else:
        print(tns)


if __name__ == "__main__":
    main() 