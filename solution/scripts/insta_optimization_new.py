#!/usr/bin/env python3
"""
INSTA-based Gate Sizing and Buffer Insertion Optimization Script

This script uses INSTA timing data to perform intelligent gate sizing and buffer insertion
to reduce TNS (Total Negative Slack) while managing power consumption.

Usage: python insta_optimization.py <def_file> <insta_inputs_dir> <timing_weight> <power_weight>
"""

import sys
import csv
import os
import re
import argparse
from collections import defaultdict, namedtuple
from typing import Dict, List, Tuple, Set
import random

# Data structures
PinInfo = namedtuple('PinInfo', ['full_name', 'min_rise_slack', 'min_fall_slack', 'max_rise_slack', 'max_fall_slack', 
                                'fanout', 'direction', 'x_coord', 'y_coord'])
CellInfo = namedtuple('CellInfo', ['full_name', 'lib_cell', 'function_id'])
NetArc = namedtuple('NetArc', ['from_pin', 'to_pin', 'delay_rise', 'delay_fall'])
CellArc = namedtuple('CellArc', ['from_pin', 'to_pin', 'sense', 'delay_rise', 'delay_fall'])

class InstaOptimizer:
    def __init__(self, def_file: str, insta_dir: str, timing_weight: float = 1.0, power_weight: float = 1.0):
        self.def_file = def_file
        self.insta_dir = insta_dir
        self.timing_weight = timing_weight
        self.power_weight = power_weight
        
        # Data storage
        self.pin_features = {}
        self.cell_to_lib = {}
        self.available_lib_cells = defaultdict(set)
        self.net_arcs = []
        self.cell_arcs = []
        self.def_cells = set()
        
        # Load all data
        self.load_data()
    
    def load_data(self):
        """Load all INSTA data files"""
        # print("Loading INSTA data...", file=sys.stderr)
        
        # Load pin features
        pin_feats_file = os.path.join(self.insta_dir, 'pin_feats.csv')
        if os.path.exists(pin_feats_file):
            self.load_pin_features(pin_feats_file)
        
        # Load cell to library mapping
        cell2lib_file = os.path.join(self.insta_dir, 'cell_2_libCell.csv')
        if os.path.exists(cell2lib_file):
            self.load_cell_to_lib(cell2lib_file)
        
        # Load available library cells
        lib_cells_file = os.path.join(self.insta_dir, 'all_available_lib_cells.csv')
        if os.path.exists(lib_cells_file):
            self.load_available_lib_cells(lib_cells_file)
        
        # Load net arcs
        net_arcs_file = os.path.join(self.insta_dir, 'net_arcs.csv')
        if os.path.exists(net_arcs_file):
            self.load_net_arcs(net_arcs_file)
        
        # Load cell arcs
        cell_arcs_file = os.path.join(self.insta_dir, 'cell_arcs.csv')
        if os.path.exists(cell_arcs_file):
            self.load_cell_arcs(cell_arcs_file)
        
        # Load DEF file
        self.load_def_cells()
        

        
        # print(f"Loaded {len(self.pin_features)} pins, {len(self.cell_to_lib)} cells, {len(self.net_arcs)} net arcs, {len(self.def_cells)} DEF cells", file=sys.stderr)
    
    def load_pin_features(self, filename: str):
        """Load pin features from CSV"""
        try:
            with open(filename, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pin_name = row['full_name']
                    self.pin_features[pin_name] = PinInfo(
                        full_name=pin_name,
                        min_rise_slack=float(row.get('min_rise_slack', 0)),
                        min_fall_slack=float(row.get('min_fall_slack', 0)),
                        max_rise_slack=float(row.get('max_rise_slack', 0)),
                        max_fall_slack=float(row.get('max_fall_slack', 0)),
                        fanout=float(row.get('fanout_load', 0)),
                        direction=row.get('direction', ''),
                        x_coord=float(row.get('x_coordinate', 0)),
                        y_coord=float(row.get('y_coordinate', 0))
                    )
        except Exception as e:
            print(f"Warning: Could not load pin features: {e}", file=sys.stderr)
    
    def load_cell_to_lib(self, filename: str):
        """Load cell to library mapping"""
        try:
            with open(filename, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cell_name = row['full_name']
                    lib_cell = row['lib_cell.full_name']
                    func_id = row.get('lib_cell.function_id', '')
                    self.cell_to_lib[cell_name] = CellInfo(
                        full_name=cell_name,
                        lib_cell=lib_cell,
                        function_id=func_id
                    )
        except Exception as e:
            print(f"Warning: Could not load cell to lib mapping: {e}", file=sys.stderr)
    
    def load_available_lib_cells(self, filename: str):
        """Load available library cells"""
        try:
            with open(filename, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cell_name = row['full_name']
                    func_id = row.get('function_id', '')
                    if func_id:
                        self.available_lib_cells[func_id].add(cell_name)
        except Exception as e:
            print(f"Warning: Could not load available lib cells: {e}", file=sys.stderr)
    
    def load_net_arcs(self, filename: str):
        """Load net arcs for interconnect analysis"""
        try:
            with open(filename, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    from_pin = row['from_pin.full_name']
                    to_pin = row['to_pin.full_name']
                    delay_rise = float(row.get('delay_max_rise', 0))
                    delay_fall = float(row.get('delay_max_fall', 0))
                    self.net_arcs.append(NetArc(from_pin, to_pin, delay_rise, delay_fall))
        except Exception as e:
            print(f"Warning: Could not load net arcs: {e}", file=sys.stderr)
    
    def load_cell_arcs(self, filename: str):
        """Load cell arcs for internal timing analysis"""
        try:
            with open(filename, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    from_pin = row['from_pin.full_name']
                    to_pin = row['to_pin.full_name']
                    sense = row.get('sense', '')
                    delay_rise = float(row.get('delay_max_rise', 0))
                    delay_fall = float(row.get('delay_max_fall', 0))
                    self.cell_arcs.append(CellArc(from_pin, to_pin, sense, delay_rise, delay_fall))
        except Exception as e:
            print(f"Warning: Could not load cell arcs: {e}", file=sys.stderr)
    
    def load_def_cells(self):
        """Load cells from DEF file"""
        try:
            with open(self.def_file, 'r') as f:
                lines = f.readlines()
            
            in_components = False
            for line in lines:
                if line.strip().startswith('COMPONENTS'):
                    in_components = True
                    continue
                if in_components and line.strip().startswith('END COMPONENTS'):
                    break
                if in_components and line.strip().startswith('- '):
                    # Match the actual DEF format: "- cell_name lib_cell + SOURCE TIMING + PLACED ( x y ) orientation"
                    # More flexible regex to handle extra spaces and variations
                    m = re.match(r'\s*-\s+([^\s]+)\s+(\S+)\s*\+\s*SOURCE\s+TIMING\s*\+\s*PLACED\s*\(\s*(\d+)\s+(\d+)\s*\)\s*(\S+)', line)
                    if m:
                        cell_name = m.group(1)
                        self.def_cells.add(cell_name)
                    else:
                        # Try alternative format in case the regex is too strict
                        parts = line.strip().split()
                        if len(parts) >= 2 and parts[0] == '-':
                            cell_name = parts[1]
                        self.def_cells.add(cell_name)
        except Exception as e:
            print(f"Warning: Could not load DEF cells: {e}", file=sys.stderr)
    

    
    def analyze_cell_timing_impact(self, cell_name: str) -> Dict:
        """Analyze timing impact of a specific cell"""
        if cell_name not in self.cell_to_lib:
            return None
        
        # Find all pins belonging to this cell
        cell_pins = [pin for pin in self.pin_features.keys() if pin.startswith(f"{cell_name}/")]
        if not cell_pins:
            return None
        
        # Calculate worst slack for this cell
        worst_slack = float('inf')
        input_slack = float('inf')
        output_slack = float('inf')
        
        for pin in cell_pins:
            pin_info = self.pin_features[pin]
            min_slack = min(pin_info.min_rise_slack, pin_info.min_fall_slack)
            
            if pin_info.direction == 'in':
                input_slack = min(input_slack, min_slack)
            elif pin_info.direction == 'out':
                output_slack = min(output_slack, min_slack)
            
            worst_slack = min(worst_slack, min_slack)
        
        # Calculate slack difference (cell contribution)
        slack_diff = output_slack - input_slack if input_slack != float('inf') and output_slack != float('inf') else 0
        
        return {
            'cell_name': cell_name,
            'worst_slack': worst_slack,
            'input_slack': input_slack,
            'output_slack': output_slack,
            'slack_diff': slack_diff,
            'fanout': max([self.pin_features[pin].fanout for pin in cell_pins if pin in self.pin_features], default=0.0),
            'cell_pins': cell_pins
        }
    
    def find_gate_sizing_candidates(self) -> List[Dict]:
        """Find cells that are good candidates for gate sizing"""
        candidates = []
        
        # print(f"DEBUG: Checking {len(self.def_cells)} cells for gate sizing", file=sys.stderr)
        # print(f"DEBUG: Found {len(self.cell_to_lib)} cells in cell_to_lib mapping", file=sys.stderr)
        # print(f"DEBUG: Found {len(self.available_lib_cells)} function IDs with available cells", file=sys.stderr)
        
        for cell_name in self.def_cells:
            if cell_name not in self.cell_to_lib:
                continue
            
            analysis = self.analyze_cell_timing_impact(cell_name)
            if analysis is None:
                continue
            
            # Adjust slack threshold based on timing weight
            if self.timing_weight > 1.5:
                # Very aggressive: consider all cells with negative slack
                slack_threshold = 0
            elif self.timing_weight > 1.0:
                # Aggressive: consider cells with significant negative slack
                slack_threshold = -50
            else:
                # Conservative: only consider cells with very negative slack
                slack_threshold = -100
            
            # Only consider cells below the slack threshold
            if analysis['worst_slack'] >= slack_threshold:
                continue
            
            # Calculate optimization score
            score = abs(analysis['worst_slack']) * self.timing_weight
            if analysis['slack_diff'] < 0:  # Cell is degrading timing
                score *= 2  # Higher priority
            
            # Consider fanout impact
            if analysis['fanout'] > 10.0:
                score *= 1.5  # High fanout cells affect more paths
            
            analysis['score'] = score
            candidates.append(analysis)
        
        # print(f"DEBUG: Found {len(candidates)} cells that meet slack threshold", file=sys.stderr)
        
        # Sort by score (highest first)
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Make max_candidates weight-dependent
        base_limit = len(self.def_cells) // 10
        if self.timing_weight > 1.0:
            max_candidates = int(base_limit * self.timing_weight)
        elif self.timing_weight < 1.0:
            max_candidates = int(base_limit * self.timing_weight)
        else:
            max_candidates = base_limit
        
        # Ensure reasonable bounds
        max_candidates = max(100, min(max_candidates, len(candidates)))
        
        # print(f"Gate sizing: base_limit={base_limit}, timing_weight={self.timing_weight}, max_candidates={max_candidates}", file=sys.stderr)
        return candidates[:max_candidates]
    
    def find_buffer_insertion_candidates(self) -> List[Dict]:
        """Find nets that are good candidates for buffer insertion"""
        candidates = []
        
        # Consider all nets regardless of delay threshold
        # Analyze all net arcs for optimization opportunities
        total_nets = len(self.net_arcs)
        skipped_cells = 0
        skipped_pins = 0
        
        # Debug: show some sample cell names from both sources
        sample_def_cells = list(self.def_cells)[:5]
        sample_pin_cells = []
        for i, net_arc in enumerate(self.net_arcs[:5]):
            from_cell = net_arc.from_pin.split('/')[0]
            to_cell = net_arc.to_pin.split('/')[0]
            sample_pin_cells.extend([from_cell, to_cell])
        
        # print(f"Sample DEF cells: {sample_def_cells}", file=sys.stderr)
        # print(f"Sample pin cells: {sample_pin_cells[:10]}", file=sys.stderr)
        
        # Debug: check for common patterns in cell names
        def_cell_patterns = set()
        pin_cell_patterns = set()
        
        for cell in list(self.def_cells)[:20]:  # Check first 20 DEF cells
            if cell.startswith('FE_'):
                def_cell_patterns.add('FE_*')
            elif cell.startswith('g'):
                def_cell_patterns.add('g*')
            elif '[' in cell:
                def_cell_patterns.add('array_notation')
            else:
                def_cell_patterns.add('other')
        
        for i, net_arc in enumerate(self.net_arcs[:100]):  # Check first 100 net arcs
            from_cell = net_arc.from_pin.split('/')[0]
            to_cell = net_arc.to_pin.split('/')[0]
            for cell in [from_cell, to_cell]:
                if cell.startswith('FE_'):
                    pin_cell_patterns.add('FE_*')
                elif cell.startswith('g'):
                    pin_cell_patterns.add('g*')
                elif '[' in cell:
                    pin_cell_patterns.add('array_notation')
                else:
                    pin_cell_patterns.add('other')
        
        # print(f"DEF cell patterns: {def_cell_patterns}", file=sys.stderr)
        # print(f"Pin cell patterns: {pin_cell_patterns}", file=sys.stderr)
        
        # Debug: analyze the missing cells more systematically
        missing_cells = set()
        missing_pins = set()
        for net_arc in self.net_arcs[:1000]:  # Check first 1000 nets
            from_cell = net_arc.from_pin.split('/')[0]
            to_cell = net_arc.to_pin.split('/')[0]
            if from_cell not in self.def_cells:
                missing_cells.add(from_cell)
            if to_cell not in self.def_cells:
                missing_cells.add(to_cell)
            
            # Check if pins exist in pin features
            if net_arc.from_pin not in self.pin_features:
                missing_pins.add(net_arc.from_pin)
            if net_arc.to_pin not in self.pin_features:
                missing_pins.add(net_arc.to_pin)
        
        # print(f"Sample missing cells (first 10): {list(missing_cells)[:10]}", file=sys.stderr)
        # print(f"Total unique missing cells found: {len(missing_cells)}", file=sys.stderr)
        # print(f"Sample missing pins (first 10): {list(missing_pins)[:10]}", file=sys.stderr)
        # print(f"Total unique missing pins found: {len(missing_pins)}", file=sys.stderr)
        
        # Debug: check if there's a data loading issue
        # print(f"DEBUG: pin_features loaded {len(self.pin_features)} pins", file=sys.stderr)
        # print(f"DEBUG: net_arcs loaded {len(self.net_arcs)} nets", file=sys.stderr)
        
        # Check if the first few pins from net_arcs exist in pin_features
        for i, net_arc in enumerate(self.net_arcs[:5]):
            from_exists = net_arc.from_pin in self.pin_features
            to_exists = net_arc.to_pin in self.pin_features
            # print(f"DEBUG: Net {i}: {net_arc.from_pin} exists: {from_exists}, {net_arc.to_pin} exists: {to_exists}", file=sys.stderr)
        
        # Create a mapping from unescaped to escaped cell names
        # This handles the mismatch between INSTA data (unescaped) and DEF file (escaped)
        cell_name_mapping = {}
        for def_cell in self.def_cells:
            # Convert escaped brackets back to unescaped for matching
            unescaped_name = def_cell.replace('\\[', '[').replace('\\]', ']')
            cell_name_mapping[unescaped_name] = def_cell
        
        # print(f"Created cell name mapping for {len(cell_name_mapping)} cells", file=sys.stderr)
        
        for net_arc in self.net_arcs:
            from_cell = net_arc.from_pin.split('/')[0]
            to_cell = net_arc.to_pin.split('/')[0]
            
            # Use cell name mapping to handle escaped vs unescaped names
            from_cell_mapped = cell_name_mapping.get(from_cell, from_cell)
            to_cell_mapped = cell_name_mapping.get(to_cell, to_cell)
            
            # Skip if either cell is not in our design (after mapping)
            if from_cell_mapped not in self.def_cells or to_cell_mapped not in self.def_cells:
                skipped_cells += 1
                # Debug: show first few mismatches
                if skipped_cells <= 3:
                    missing_cell = from_cell if from_cell_mapped not in self.def_cells else to_cell
                    # print(f"DEBUG: Skipping net {net_arc.from_pin} -> {net_arc.to_pin}, missing cell: {missing_cell}", file=sys.stderr)
                continue
            
            # Note: Pin features are optional - use default values if missing
            # This allows processing all nets even if pin_feats.csv is incomplete
            
            # Calculate score based on delay and fanout
            delay_score = max(net_arc.delay_rise, net_arc.delay_fall)
            
            # Use fanout from pin features if available, otherwise use default
            if net_arc.from_pin in self.pin_features:
                fanout_score = self.pin_features[net_arc.from_pin].fanout
            else:
                fanout_score = 1.0  # Default fanout value
            
            score = delay_score * self.timing_weight + fanout_score * 0.1
            
            # Store both original and mapped pin names for proper DEF output
            candidates.append({
                'from_pin': net_arc.from_pin,
                'to_pin': net_arc.to_pin,
                'from_pin_def': net_arc.from_pin.replace(from_cell, from_cell_mapped),
                'to_pin_def': net_arc.to_pin.replace(to_cell, to_cell_mapped),
                'delay_rise': net_arc.delay_rise,
                'delay_fall': net_arc.delay_fall,
                'score': score
            })
        
        # print(f"Buffer insertion analysis: total_nets={total_nets}, skipped_cells={skipped_cells}, skipped_pins={skipped_pins}, valid_candidates={len(candidates)}", file=sys.stderr)
        
        # Sort by score and limit candidates
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Calculate percentage based on timing criticality (TNS analysis)
        percentage = self._calculate_buffer_insertion_percentage()
        max_candidates = int(len(candidates) * percentage)
        
        # Ensure reasonable bounds
        max_candidates = max(50, min(max_candidates, len(candidates)))
        
        # print(f"Buffer insertion: total_candidates={len(candidates)}, timing_weight={self.timing_weight}, percentage={percentage:.1%}, max_candidates={max_candidates}", file=sys.stderr)
        
        # Debug: show first few and last few candidates to verify selection
        # if candidates:
        #     print(f"First candidate: {candidates[0]['from_pin']} -> {candidates[0]['to_pin']} (score: {candidates[0]['score']:.2f})", file=sys.stderr)
        #     if len(candidates) > 1:
        #         print(f"Last candidate: {candidates[-1]['from_pin']} -> {candidates[-1]['to_pin']} (score: {candidates[-1]['score']:.2f})", file=sys.stderr)
        
        return candidates[:max_candidates]
    
    def _calculate_buffer_insertion_percentage(self) -> float:
        """Calculate what percentage of nets need buffer insertion based on TNS analysis"""
        if not self.pin_features:
            # Fallback to timing weight if no pin features available
            return min(1.0, self.timing_weight / 20.0)
        
        # Calculate TNS (Total Negative Slack) from pin features
        total_negative_slack = 0.0
        critical_pins = 0
        total_pins = 0
        
        for pin_info in self.pin_features.values():
            total_pins += 1
            # Get worst slack (rise or fall)
            worst_slack = min(pin_info.min_rise_slack, pin_info.min_fall_slack)
            
            if worst_slack < 0:
                total_negative_slack += abs(worst_slack)
                critical_pins += 1
        
        if total_pins == 0:
            return min(1.0, self.timing_weight / 20.0)
        
        # Calculate timing criticality metrics
        criticality_ratio = critical_pins / total_pins
        avg_negative_slack = total_negative_slack / max(critical_pins, 1)
        
        # print(f"TNS Analysis: total_pins={total_pins}, critical_pins={critical_pins}, "
        #       f"criticality_ratio={criticality_ratio:.3f}, avg_negative_slack={avg_negative_slack:.3f}", file=sys.stderr)
        
        # Determine buffer insertion percentage based on timing criticality
        # More aggressive approach for large TNS designs
        if criticality_ratio > 0.8:  # More than 80% of pins have negative slack
            base_percentage = 0.95  # 95% of nets need buffers
        elif criticality_ratio > 0.6:  # More than 60% of pins have negative slack
            base_percentage = 0.85  # 85% of nets need buffers
        elif criticality_ratio > 0.4:  # More than 40% of pins have negative slack
            base_percentage = 0.75  # 75% of nets need buffers
        elif criticality_ratio > 0.2:  # More than 20% of pins have negative slack
            base_percentage = 0.65  # 65% of nets need buffers
        else:  # Less than 20% of pins have negative slack
            base_percentage = 0.45  # 45% of nets need buffers (much higher than before)
        
        # Adjust based on average negative slack severity
        # Much more aggressive for large TNS designs
        if avg_negative_slack > 10000:  # Extremely severe timing violations (like pci_bridge32)
            slack_multiplier = 1.8
        elif avg_negative_slack > 5000:  # Very severe timing violations (like ac97_top)
            slack_multiplier = 1.6
        elif avg_negative_slack > 2000:  # Severe timing violations (like aes_cipher_top)
            slack_multiplier = 1.4
        elif avg_negative_slack > 1000:  # High timing violations
            slack_multiplier = 1.3
        elif avg_negative_slack > 500:  # Moderate-high timing violations
            slack_multiplier = 1.2
        elif avg_negative_slack > 100:  # Moderate timing violations
            slack_multiplier = 1.1
        elif avg_negative_slack > 50:  # Minor timing violations
            slack_multiplier = 1.0
        else:  # Very minor timing violations
            slack_multiplier = 0.95  # Still aggressive
        
        # Apply timing weight as a modifier
        # More aggressive scaling for timing weight
        weight_multiplier = min(3.0, self.timing_weight / 5.0)  # Max 3x multiplier, scales faster
        
        final_percentage = base_percentage * slack_multiplier * weight_multiplier
        final_percentage = max(0.3, min(1.0, final_percentage))  # Bound between 30% and 100% (much higher minimum)
        
        # print(f"Buffer insertion: base_percentage={base_percentage:.1%}, "
        #       f"slack_multiplier={slack_multiplier:.2f}, weight_multiplier={weight_multiplier:.2f}, "
        #       f"final_percentage={final_percentage:.1%}", file=sys.stderr)
        
        return final_percentage
    
    def generate_gate_sizing_commands(self, candidates: List[Dict]) -> List[str]:
        """Generate OpenROAD commands for gate sizing"""
        commands = []
        
        # print(f"DEBUG: Generating gate sizing commands for {len(candidates)} candidates", file=sys.stderr)
        
        for candidate in candidates:
            cell_name = candidate['cell_name']
            if cell_name not in self.cell_to_lib:
                # print(f"DEBUG: Cell {cell_name} not in cell_to_lib mapping", file=sys.stderr)
                continue
            
            current_lib_cell = self.cell_to_lib[cell_name].lib_cell
            func_id = self.cell_to_lib[cell_name].function_id
            
            # print(f"DEBUG: Cell {cell_name} has func_id '{func_id}' and current lib_cell '{current_lib_cell}'", file=sys.stderr)
            
            if func_id not in self.available_lib_cells:
                # print(f"DEBUG: Function ID '{func_id}' not found in available_lib_cells", file=sys.stderr)
                continue
            
            # Find better library cell
            available_cells = list(self.available_lib_cells[func_id])
            # print(f"DEBUG: Found {len(available_cells)} available cells for func_id '{func_id}'", file=sys.stderr)
            
            if len(available_cells) <= 1:
                # print(f"DEBUG: Only {len(available_cells)} available cells, skipping", file=sys.stderr)
                continue
            
            # For aggressive timing optimization, prefer larger cells
            if self.timing_weight > 1.0:
                # Sort by size (larger cells typically have better drive strength)
                size_order = ['x1', 'x2', 'x3', 'x4', 'x5', 'x6', 'x8', 'x10', 'x12', 'x16', 'x24']
                available_cells.sort(key=lambda x: max([size_order.index(size) if size in x else -1 for size in size_order]), reverse=True)
            
            # Find a different cell than current
            better_cell = None
            for cell in available_cells:
                if cell != current_lib_cell:
                    better_cell = cell
                    break
            
            if better_cell:
                commands.append(f"size_cell {cell_name} {better_cell}")
                # print(f"DEBUG: Will size cell {cell_name} from {current_lib_cell} to {better_cell}", file=sys.stderr)
            else:
                # print(f"DEBUG: No better cell found for {cell_name}", file=sys.stderr)
                pass
        
        # print(f"DEBUG: Generated {len(commands)} gate sizing commands", file=sys.stderr)
        return commands
    
    def extract_buffer_size(self, buffer_name: str) -> int:
        """Extract numerical size from buffer name (e.g., 'BUFx16f' -> 16)"""
        import re
        match = re.search(r'BUFx(\d+)', buffer_name)
        if match:
            return int(match.group(1))
        return 1  # Default to x1 if can't parse
    
    def select_optimal_buffer(self, net_delay: float, fanout: float, power_weight: float, available_buffers: List[str], 
                            from_pin: str = None, to_pin: str = None) -> str:
        """Select optimal buffer based on simple delay and power weight"""
        if not available_buffers:
            return None
        
        # Parse buffer sizes and create size-to-buffer mapping
        buffer_by_size = {}
        for buf in available_buffers:
            size = self.extract_buffer_size(buf)
            if size not in buffer_by_size:
                buffer_by_size[size] = []
            buffer_by_size[size].append(buf)
        
        if not buffer_by_size:
            return None
        
        # Simple buffer strength calculation based on delay
        if net_delay > 5.0:
            required_strength = 16
        elif net_delay > 2.0:
            required_strength = 8
        elif net_delay > 0.5:
            required_strength = 4
        else:
            required_strength = 1
        
        # Find available buffer sizes
        available_sizes = sorted(buffer_by_size.keys())
        
        # Find buffer with sufficient strength
        sufficient_buffers = [size for size in available_sizes if size >= required_strength]
        
        if sufficient_buffers:
            # Power-aware selection: prefer smaller buffers if power weight is high
            if power_weight > 1.0:
                best_size = min(sufficient_buffers)  # Smallest sufficient buffer
            else:
                best_size = min(sufficient_buffers, key=lambda x: abs(x - required_strength))  # Closest to required
            
            return buffer_by_size[best_size][0]
        
        # No sufficient buffer, use largest available
        largest_size = max(available_sizes)
        print(f"Warning: No buffer strong enough for net {from_pin} -> {to_pin} "
              f"(required: {required_strength}, using: {largest_size})", file=sys.stderr)
        return buffer_by_size[largest_size][0]
    

    

    

    
    
    
    def generate_buffer_insertion_commands(self, candidates: List[Dict]) -> List[str]:
        """Generate OpenROAD commands for buffer insertion"""
        commands = []
        
        # Find buffer cells
        buffer_cells = []
        for func_id, cells in self.available_lib_cells.items():
            for cell in cells:
                if 'BUF' in cell and 'ASAP7' in cell:
                    buffer_cells.append(cell)
        
        if not buffer_cells:
            print("Warning: No buffer cells found in library", file=sys.stderr)
            return commands
        
        # print(f"Found {len(buffer_cells)} total buffer types", file=sys.stderr)
        
        # Filter buffers based on power weight (more intelligent filtering)
        # Always ensure we have access to a range of buffer sizes for critical nets
        if self.power_weight > 1.5:
            # Very aggressive power optimization: prefer smaller buffers but keep some larger ones
            preferred_buffers = [buf for buf in buffer_cells if self.extract_buffer_size(buf) <= 4]
            # Add a few larger buffers for critical nets
            larger_buffers = [buf for buf in buffer_cells if self.extract_buffer_size(buf) > 4 and self.extract_buffer_size(buf) <= 16]
            if larger_buffers:
                # Take top 3 largest buffers to handle critical cases
                larger_buffers.sort(key=lambda x: self.extract_buffer_size(x), reverse=True)
                preferred_buffers.extend(larger_buffers[:3])
        elif self.power_weight > 1.0:
            # Aggressive power optimization: prefer smaller buffers but keep medium ones
            preferred_buffers = [buf for buf in buffer_cells if self.extract_buffer_size(buf) <= 8]
            # Add some larger buffers for critical nets
            larger_buffers = [buf for buf in buffer_cells if self.extract_buffer_size(buf) > 8 and self.extract_buffer_size(buf) <= 24]
            if larger_buffers:
                # Take top 5 largest buffers to handle critical cases
                larger_buffers.sort(key=lambda x: self.extract_buffer_size(x), reverse=True)
                preferred_buffers.extend(larger_buffers[:5])
        elif self.power_weight < 0.8:
            # Conservative power optimization: allow larger buffers
            preferred_buffers = [buf for buf in buffer_cells if self.extract_buffer_size(buf) <= 16]
        else:
            # Balanced approach: prefer smaller buffers but ensure coverage
            preferred_buffers = [buf for buf in buffer_cells if self.extract_buffer_size(buf) <= 12]
            # Add some larger buffers for critical nets
            larger_buffers = [buf for buf in buffer_cells if self.extract_buffer_size(buf) > 12]
            if larger_buffers:
                # Take top 8 largest buffers to handle critical cases
                larger_buffers.sort(key=lambda x: self.extract_buffer_size(x), reverse=True)
                preferred_buffers.extend(larger_buffers[:8])
        
        if preferred_buffers:
            buffer_cells = preferred_buffers
            # print(f"Buffer selection: power_weight={self.power_weight}, selected {len(buffer_cells)} buffer types", file=sys.stderr)
            
            # Show buffer size distribution for debugging
            # size_distribution = {}
            # for buf in buffer_cells:
            #     size = self.extract_buffer_size(buf)
            #     size_distribution[size] = size_distribution.get(size, 0) + 1
            # print(f"Buffer size distribution: {dict(sorted(size_distribution.items()))}", file=sys.stderr)
        
        # Group candidates by delay ranges for better buffer selection
        high_delay_candidates = []  # delay > 0.2
        medium_delay_candidates = []  # 0.05 < delay <= 0.2
        low_delay_candidates = []  # delay <= 0.05
        
        for candidate in candidates:
            max_delay = max(candidate['delay_rise'], candidate['delay_fall'])
            if max_delay > 0.2:
                high_delay_candidates.append(candidate)
            elif max_delay > 0.05:
                medium_delay_candidates.append(candidate)
            else:
                low_delay_candidates.append(candidate)
        
        # print(f"Buffer insertion candidates: {len(high_delay_candidates)} high-delay, {len(medium_delay_candidates)} medium-delay, {len(low_delay_candidates)} low-delay", file=sys.stderr)
        
        # Process candidates in order of priority (high delay first)
        all_candidates = high_delay_candidates + medium_delay_candidates + low_delay_candidates
        
        processed_count = 0
        successful_count = 0
        
        for i, candidate in enumerate(all_candidates):
            processed_count += 1
            max_delay = max(candidate['delay_rise'], candidate['delay_fall'])
            fanout = self.pin_features.get(candidate['from_pin'], PinInfo('', 0, 0, 0, 0, 0, '', 0, 0)).fanout
            
            # Select optimal buffer for this net with pin information for intelligent sizing
            optimal_buffer = self.select_optimal_buffer(max_delay, fanout, self.power_weight, buffer_cells, 
                                                      candidate['from_pin'], candidate['to_pin'])
            
            if optimal_buffer:
                successful_count += 1
                # Use DEF-formatted pin names for the changelist
                from_pin_def = candidate['from_pin_def']
                to_pin_def = candidate['to_pin_def']
                
                # Generate unique names
                buffer_name = f"BUF_opt_{i:06d}"
                net_name = f"NET_BUF_opt_{i:06d}"
                
                commands.append(f"insert_buffer {{{from_pin_def}}} {optimal_buffer} {buffer_name} {net_name}")
                
                # Debug output for first few insertions (show both original and DEF names)
                # if i < 5:
                #     buffer_size = self.extract_buffer_size(optimal_buffer)
                #     print(f"DEBUG: Net {candidate['from_pin']} -> {candidate['to_pin']} (delay: {max_delay:.3f}, fanout: {fanout:.1f}) -> {optimal_buffer} (size: x{buffer_size})", file=sys.stderr)
                #     print(f"DEBUG: DEF format: {from_pin_def} -> {to_pin_def}", file=sys.stderr)
            else:
                print(f"Warning: No suitable buffer found for net {candidate['from_pin']} -> {candidate['to_pin']}", file=sys.stderr)
        
        # print(f"Buffer insertion processing: processed {processed_count} candidates, successful {successful_count}, generated {len(commands)} commands", file=sys.stderr)
        

        
        return commands
    

    

    
    def optimize(self) -> Tuple[List[str], List[str]]:
        """Main optimization function"""
        # print(f"Starting optimization analysis with timing_weight={self.timing_weight}, power_weight={self.power_weight}", file=sys.stderr)
        
        # Skip gate sizing - only do buffer insertion
        gate_sizing_candidates = []  # Empty list - no gate sizing
        buffer_candidates = self.find_buffer_insertion_candidates()
        
        # print(f"Gate sizing: DISABLED", file=sys.stderr)
        # print(f"Found {len(buffer_candidates)} buffer insertion candidates", file=sys.stderr)
        
        # Show timing weight impact
        expected_percentage = min(1.0, self.timing_weight / 20.0)
        # print(f"Timing weight {self.timing_weight} should optimize {expected_percentage:.1%} of available nets", file=sys.stderr)
        
        # Show weight impact on candidate selection
        # if buffer_candidates:
        #     print(f"Top buffer candidate: {buffer_candidates[0]['from_pin']} -> {buffer_candidates[0]['to_pin']} (score: {buffer_candidates[0]['score']:.2f}, delay: {max(buffer_candidates[0]['delay_rise'], buffer_candidates[0]['delay_fall']):.3f})", file=sys.stderr)
        
        # Generate commands
        gate_sizing_commands = []  # No gate sizing commands
        buffer_commands = self.generate_buffer_insertion_commands(buffer_candidates)
        
        # print(f"Generated 0 gate sizing commands", file=sys.stderr)
        # print(f"Generated {len(buffer_commands)} buffer insertion commands", file=sys.stderr)
        
        return gate_sizing_commands, buffer_commands
    
    def write_changelist(self, gate_commands: List[str], buffer_commands: List[str], output_file: str):
        """Write optimization commands to changelist file"""
        with open(output_file, 'w') as f: 
            if gate_commands:
                f.write("# Gate Sizing Commands\n")
                for cmd in gate_commands:
                    f.write(f"{cmd}\n")
                f.write("\n")
            
            if buffer_commands:
                f.write("# Buffer Insertion Commands\n")
                for cmd in buffer_commands:
                    f.write(f"{cmd}\n")
                f.write("\n")
        
        # print(f"Changelist written to {output_file}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description='INSTA-based Gate Sizing and Buffer Insertion Optimization')
    parser.add_argument('def_file', help='Input DEF file')
    parser.add_argument('insta_dir', help='INSTA inputs directory')
    parser.add_argument('--timing-weight', type=float, default=1.0, help='Timing optimization weight (default: 1.0)')
    parser.add_argument('--power-weight', type=float, default=1.0, help='Power optimization weight (default: 1.0)')
    parser.add_argument('--output', default='insta_optimization.changelist', help='Output changelist file')
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.def_file):
        print(f"Error: DEF file {args.def_file} not found", file=sys.stderr)
        sys.exit(1)
    
    if not os.path.exists(args.insta_dir):
        print(f"Error: INSTA directory {args.insta_dir} not found", file=sys.stderr)
        sys.exit(1)
    
    # Create optimizer
    optimizer = InstaOptimizer(
        def_file=args.def_file,
        insta_dir=args.insta_dir,
        timing_weight=args.timing_weight,
        power_weight=args.power_weight
    )
    
    # Run optimization
    gate_commands, buffer_commands = optimizer.optimize()
    
    # Write results
    optimizer.write_changelist(gate_commands, buffer_commands, args.output)
    
    # Print summary
    # print(f"\nOptimization Summary:", file=sys.stderr)
    # print(f"  Gate sizing commands: {len(gate_commands)}", file=sys.stderr)
    # print(f"  Buffer insertion commands: {len(buffer_commands)}", file=sys.stderr)
    # print(f"  Total commands: {len(gate_commands) + len(buffer_commands)}", file=sys.stderr)

if __name__ == "__main__":
    main()
