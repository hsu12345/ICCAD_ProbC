import sys
import re
import os
import csv
from collections import defaultdict
import multiprocessing as mp
import time

# Prefer 'fork' start method on Unix-like systems for better performance and memory sharing
try:
	mp.set_start_method('fork')
except Exception:
	pass

# Args: keep compatibility with the original interface
if len(sys.argv) != 3:
	print(f"Usage: {sys.argv[0]} <input.def> <changelist>", file=sys.stderr)
	sys.exit(1)




def_file = sys.argv[1]
changelist_file = sys.argv[2]

# Output file name in current directory, same as before
design_name = os.path.basename(def_file).replace('.def', '')
output_def = f"./{design_name}.sol.def"

# Track changelist commands to update the changelist after applying actions
commands_in_order = []  # list of tuples: ('insert'|'size', dict)
insert_cmds = []  # dict keys: new_cell, raw, success
size_cmds = []    # dict keys: cell, raw, success

# Precompiled regexes
RE_COMPONENT = re.compile(r"\s*-\s+(\S+)\s+(\S+)\s*\+\s*PLACED\s*\(\s*(\d+)\s+(\d+)\s*\)\s*(\S+)")
RE_INSERT_BUFFER = re.compile(r"insert_buffer \{([^}]+)\} (\S+) (\S+) (\S+)")
RE_SIZE_CELL = re.compile(r"size_cell (\S+) (\S+)")
RE_PIN_REF = re.compile(r"\(\s*(\S+)\s+(\S+)\s*\)")
RE_NETS_COUNT = re.compile(r"NETS\s+(\d+)\s*;")
# DEF helpers
RE_DEF_UNITS = re.compile(r"UNITS\s+DISTANCE\s+MICRONS\s+(\d+)\s*;")
RE_DEF_DIEAREA = re.compile(r"DIEAREA\s*\(\s*(\d+)\s+(\d+)\s*\)\s*\(\s*(\d+)\s+(\d+)\s*\)")
RE_DEF_ROW = re.compile(r"ROW\s+\S+\s+\S+\s+(\d+)\s+(\d+)\s+\S+\s+DO\s+(\d+)\s+BY\s+(\d+)\s+STEP\s+(\d+)\s+(\d+)")
RE_NET_NAME = re.compile(r"^\s*-\s+(\S+)")
# LEF helpers
RE_LEF_MACRO = re.compile(r"^\s*MACRO\s+(\S+)")
RE_LEF_SIZE = re.compile(r"^\s*SIZE\s+([0-9]+(?:\.[0-9]+)?)\s+BY\s+([0-9]+(?:\.[0-9]+)?)\s*;")

# Env flags for speed control (defaults: FAST=True, SKIP_HPWL=True)
_env_fast = os.getenv('FAST')
_env_skip = os.getenv('SKIP_HPWL')
FAST = True if _env_fast is None else (_env_fast not in {'0', 'false', 'False', 'NO', 'no'})
SKIP_HPWL = True if _env_skip is None else (_env_skip not in {'0', 'false', 'False', 'NO', 'no'})

# Env workers config (defaults: use all CPUs)
_env_nets_workers = os.getenv('NETS_WORKERS')
_env_lef_workers = os.getenv('LEF_WORKERS')
NETS_WORKERS = None
LEF_WORKERS = None
try:
	NETS_WORKERS = int(_env_nets_workers) if _env_nets_workers else mp.cpu_count()
except Exception:
	NETS_WORKERS = mp.cpu_count()
try:
	LEF_WORKERS = int(_env_lef_workers) if _env_lef_workers else mp.cpu_count()
except Exception:
	LEF_WORKERS = mp.cpu_count()
NETS_WORKERS = max(1, min(NETS_WORKERS, mp.cpu_count()))
LEF_WORKERS = max(1, min(LEF_WORKERS, mp.cpu_count()))
# print(f"Using workers: NETS_WORKERS={NETS_WORKERS}, LEF_WORKERS={LEF_WORKERS}")

# Timing instrumentation
TIMING = os.getenv('TIMING') in {'1', 'true', 'True', 'YES', 'yes'}
def t_now():
	return time.time()
def t_log(tag, t0):
	if TIMING:
		print(f"[timing] {tag}: {time.time() - t0:.3f}s")

# Preview changelist to collect relevant targets/macros in FAST mode

def collect_changelist_targets(chg_path):
	"""Return (target_pin_pairs, target_cells, needed_macro_names) from changelist.
	Only a lightweight scan; avoids heavy parsing."""
	target_pin_pairs = []
	target_cells = set()
	needed_macros = set()
	t0 = t_now()
	try:
		with open(chg_path, 'r') as fchg:
			for raw in fchg:
				line = raw.strip()
				if line.startswith('insert_buffer'):
					m = RE_INSERT_BUFFER.match(line)
					if not m:
						continue
					pins_blob = m.group(1)
					lib_cell_full = m.group(2)
					lib_cell = lib_cell_full.split('/')[-1]
					needed_macros.add(lib_cell)
					# Keep compatibility: use the first pin token if multiple provided
					first_pin = pins_blob.strip().split()[0] if pins_blob.strip().split() else ''
					if '/' in first_pin:
						cell = first_pin.split('/')[0]
						pin = first_pin.split('/')[1]
						target_cells.add(cell)
						target_pin_pairs.append((cell, pin))
				elif line.startswith('size_cell'):
					m2 = RE_SIZE_CELL.match(line)
					if not m2:
						continue
					cell = m2.group(1)
					target_cells.add(cell)
	except Exception as e:
		print(f"Warning: FAST preview failed: {e}", file=sys.stderr)
	t_log('scan changelist', t0)
	return target_pin_pairs, target_cells, needed_macros

def _collect_net_blocks(lines, nets_start, nets_end):
	blocks = []
	i = nets_start + 1
	while i < nets_end:
		if lines[i].lstrip().startswith('- '):
			start = i
			i += 1
			while i < nets_end and ';' not in lines[i]:
				i += 1
			if i < nets_end:
				end = i
				blocks.append((start, end))
		else:
			i += 1
	return blocks

def _parse_blocks_worker(args):
	lines, blocks, target_cells = args
	local_pin_to_occurs = {}
	local_net_to_pins = {}
	local_pin_to_net = {}
	for (start, end) in blocks:
		header = lines[start]
		mname = RE_NET_NAME.match(header)
		net_name = mname.group(1) if mname else None
		if net_name is None:
			continue
		pins = []
		record = True
		if target_cells is not None:
			record = False
		for i in range(start, end + 1):
			for m in RE_PIN_REF.finditer(lines[i]):
				cell_ref, pin_ref = m.group(1), m.group(2)
				pins.append((i, m.start(), m.end(), cell_ref, pin_ref))
				if target_cells is not None and (not record) and (cell_ref in target_cells):
					record = True
		if not pins:
			continue
		if target_cells is not None and not record:
			continue
		for (i, s, e, cell_ref, pin_ref) in pins:
			local_pin_to_occurs.setdefault((cell_ref, pin_ref), []).append((i, s, e))
			local_net_to_pins.setdefault(net_name, []).append((cell_ref, pin_ref))
			local_pin_to_net[(cell_ref, pin_ref)] = net_name
	return local_pin_to_occurs, local_net_to_pins, local_pin_to_net

def build_net_index_parallel(lines, nets_start, nets_end, target_cells=None):
	blocks = _collect_net_blocks(lines, nets_start, nets_end)
	if not blocks:
		return {}, {}, {}
	num_workers = max(1, min(NETS_WORKERS, mp.cpu_count()))
	chunk_size = (len(blocks) + num_workers - 1) // num_workers
	chunks = [blocks[i:i+chunk_size] for i in range(0, len(blocks), chunk_size)]
	args_list = [(lines, ch, target_cells) for ch in chunks]
	# print(f"NETS parse: blocks={len(blocks)} chunks={len(chunks)} workers={num_workers}")
	if num_workers == 1:
		results = [_parse_blocks_worker(args_list[0])] if args_list else []
	else:
		ctx = mp.get_context('fork')
		with ctx.Pool(processes=num_workers) as pool:
			results = pool.map(_parse_blocks_worker, args_list, chunksize=1)
	# merge
	pin_to_occurs = {}
	net_to_pins = {}
	pin_to_net = {}
	for p_occ, n_pins, p_net in results:
		for k, v in p_occ.items():
			pin_to_occurs.setdefault(k, []).extend(v)
		for k, v in n_pins.items():
			net_to_pins.setdefault(k, []).extend(v)
		for k, v in p_net.items():
			pin_to_net[k] = v
	return pin_to_occurs, net_to_pins, pin_to_net


HPWL_LOG_LIMIT = 50
hpwl_log_count = 0

# Fast preview (for FAST mode)
fast_target_pin_pairs, fast_target_cells, fast_needed_macros = collect_changelist_targets(changelist_file) if FAST else ([], set(), set())


def load_net_arcs_for_hpwl_optimization(def_file_path):
	"""Load net_arcs.csv to map target pin -> source pin for HPWL stats.
	Supports both 'from_pin'/'to_pin' and 'from_pin.full_name'/'to_pin.full_name' columns.
	Searches alongside DEF and under any INSTA_*/*/insta_inputs directory."""
	net_arcs = {}
	def_dir = os.path.dirname(def_file_path)
	net_arcs_path = os.path.join(def_dir, "net_arcs.csv")
	if not os.path.exists(net_arcs_path):
		for item in os.listdir(def_dir):
			item_path = os.path.join(def_dir, item)
			if os.path.isdir(item_path) and item.startswith("INSTA_"):
				insta_inputs_path = os.path.join(item_path, "insta_inputs")
				if os.path.exists(insta_inputs_path):
					potential = os.path.join(insta_inputs_path, "net_arcs.csv")
					if os.path.exists(potential):
						net_arcs_path = potential
						break
	if os.path.exists(net_arcs_path):
		try:
			with open(net_arcs_path, 'r') as f:
				reader = csv.DictReader(f)
				for row in reader:
					# Support multiple column name variants
					from_pin = row.get('from_pin') or row.get('from_pin.full_name') or ''
					to_pin = row.get('to_pin') or row.get('to_pin.full_name') or ''
					if from_pin and to_pin:
						net_arcs[to_pin] = from_pin
			# print(f"Loaded {len(net_arcs)} net arcs for HPWL stats from {net_arcs_path}")
		except Exception as e:
			print(f"Warning: Could not load net_arcs.csv: {e}", file=sys.stderr)
	else:
		print(f"Warning: net_arcs.csv not found for HPWL stats", file=sys.stderr)
	return net_arcs


def get_original_def_cells():
	original_def_cells = set()
	try:
		with open(def_file, 'r') as f:
			lines_local = f.readlines()
		in_components = False
		for line in lines_local:
			if line.strip().startswith('COMPONENTS'):
				in_components = True
				continue
			if in_components and line.strip().startswith('END COMPONENTS'):
				break
			if in_components:
				if line.strip().startswith('- '):
					parts = line.strip().split()
					if len(parts) >= 2:
						cell_name = parts[1]
						original_def_cells.add(cell_name)
	except Exception as e:
		print(f"Warning: Could not read original DEF file: {e}", file=sys.stderr)
	return original_def_cells


with open(def_file, 'r') as f:
	lines = f.readlines()

# Parse DEF units, DIEAREA and ROWs
t0 = t_now()
units_per_micron = 1000
_die = (0, 0, 1 << 30, 1 << 30)
row_ys = set()
site_step_x = None
for line in lines:
	m_u = RE_DEF_UNITS.search(line)
	if m_u:
		try:
			units_per_micron = int(m_u.group(1))
		except Exception:
			units_per_micron = 1000
	m_d = RE_DEF_DIEAREA.search(line)
	if m_d:
		try:
			xl, yl, xh, yh = int(m_d.group(1)), int(m_d.group(2)), int(m_d.group(3)), int(m_d.group(4))
			_die = (xl, yl, xh, yh)
		except Exception:
			pass
	m_r = RE_DEF_ROW.search(line)
	if m_r:
		try:
			ry = int(m_r.group(2))
			row_ys.add(ry)
		except Exception:
			pass
		try:
			stepx = int(m_r.group(5))
			if stepx > 0:
				site_step_x = stepx if site_step_x is None else min(site_step_x, stepx)
		except Exception:
			pass
row_ys_sorted = sorted(row_ys)
row_height = None
if len(row_ys_sorted) >= 2:
	diffs = [b - a for a, b in zip(row_ys_sorted[:-1], row_ys_sorted[1:]) if b > a]
	if diffs:
		row_height = min(diffs)
# Fallbacks
if row_height is None:
	# Default to a typical ASAP7 row height (0.27um) if rows missing
	row_height = int(round(0.27 * units_per_micron))
if site_step_x is None:
	# Default to 0.054um site width for ASAP7 if not found
	site_step_x = int(round(0.054 * units_per_micron))
t_log('parse DEF headers', t0)

# Locate COMPONENTS section
t0 = t_now()
in_components = False
comp_start = comp_end = None
for idx, line in enumerate(lines):
	if line.strip().startswith('COMPONENTS'):
		in_components = True
		comp_start = idx
	if in_components and line.strip().startswith('END COMPONENTS'):
		comp_end = idx
		break
if comp_start is None or comp_end is None:
	print("Error: COMPONENTS section not found in DEF.", file=sys.stderr)
	sys.exit(2)
comp_lines = lines[comp_start+1:comp_end]
t_log('locate COMPONENTS', t0)

def parse_cell_line(line):
	m = RE_COMPONENT.match(line)
	if m:
		cell_name = m.group(1)
		lib_name = m.group(2)
		x = int(m.group(3))
		y = int(m.group(4))
		orient = m.group(5)
		return cell_name, lib_name, x, y, orient
	return None, None, None, None, None

# Build cell_line_map and normalize formatting around PLACED parentheses when present
t0 = t_now()
cell_line_map = {}
for idx, line in enumerate(comp_lines):
	if line.strip().startswith('- '):
		cell_name, lib, x, y, orient = parse_cell_line(line)
		if cell_name:
			cell_line_map[cell_name] = idx
			if 'PLACED (' in line:
				fixed_line = line
				if 'PLACED (' in fixed_line and 'PLACED ( ' not in fixed_line:
					fixed_line = fixed_line.replace('PLACED (', 'PLACED ( ')
				if ') N' in fixed_line and ' ) N' not in fixed_line:
					fixed_line = fixed_line.replace(') N', ' ) N')
				if ') S' in fixed_line and ' ) S' not in fixed_line:
					fixed_line = fixed_line.replace(') S', ' ) S')
				if ') E' in fixed_line and ' ) E' not in fixed_line:
					fixed_line = fixed_line.replace(') E', ' ) E')
				if ') W' in fixed_line and ' ) W' not in fixed_line:
					fixed_line = fixed_line.replace(') W', ' ) W')
				if ') FN' in fixed_line and ' ) FN' not in fixed_line:
					fixed_line = fixed_line.replace(') FN', ' ) FN')
				if ') FS' in fixed_line and ' ) FS' not in fixed_line:
					fixed_line = fixed_line.replace(') FS', ' ) FS')
				if ') FE' in fixed_line and ' ) FE' not in fixed_line:
					fixed_line = fixed_line.replace(') FE', ' ) FE')
				if ') FW' in fixed_line and ' ) FW' not in fixed_line:
					fixed_line = fixed_line.replace(') FW', ' ) FW')
				comp_lines[idx] = fixed_line
t_log('build cell maps', t0)

# Export original def cells list for diffing/debug
try:
	def_cells_apply = sorted(cell_line_map.keys())
	with open("def_cells_apply.txt", "w") as f:
		for c in def_cells_apply:
			f.write(c + "\n")
except Exception as e:
	print(f"Warning: Could not write def_cells_apply.txt: {e}", file=sys.stderr)

# Build cell positions map
t0 = t_now()
cell_pos_map = {}
cell_lib_map = {}
for i, l in enumerate(comp_lines):
	cell, lib, x, y, orient = parse_cell_line(l)
	if cell:
		cell_pos_map[cell] = (x, y, orient)
		cell_lib_map[cell] = lib
t_log('build cell maps', t0)

# Load LEF macro sizes (microns) and convert to DEF DBU
t0 = t_now()
lef_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(def_file))), 'testcases', 'ASAP7', 'LEF')
macro_size = {}
current_macro = None
# In FAST mode, only parse needed macros (from changelist) and break early when all are found
needed_for_lef = (set(fast_needed_macros) | set(cell_lib_map.values())) if FAST else None
lef_file_names = [
	'asap7sc7p5t_28_R_1x_220121a.lef',
	'asap7sc7p5t_28_L_1x_220121a.lef',
	'asap7sc7p5t_28_SL_1x_220121a.lef',
	'asap7sc7p5t_28_SRAM_1x_220121a.lef'
]
lef_paths = [os.path.join(lef_dir, n) for n in lef_file_names if os.path.exists(os.path.join(lef_dir, n))]

def _parse_lef_file(args):
	lef_path, units_per_micron, needed_for = args
	local = {}
	cur = None
	try:
		with open(lef_path, 'r') as lf:
			for raw in lf:
				m_macro = RE_LEF_MACRO.match(raw)
				if m_macro:
					cur = m_macro.group(1)
					continue
				if cur:
					m_sz = RE_LEF_SIZE.match(raw)
					if m_sz:
						if (needed_for is None) or (cur in needed_for):
							w_um = float(m_sz.group(1))
							h_um = float(m_sz.group(2))
							local[cur] = (int(round(w_um * units_per_micron)), int(round(h_um * units_per_micron)))
						cur = None
	except Exception as e:
		print(f"Warning: Failed to parse LEF {lef_path}: {e}", file=sys.stderr)
	return local
t_log('parse LEF', t0)

if lef_paths:
	args = [(p, units_per_micron, needed_for_lef) for p in lef_paths]
	if LEF_WORKERS == 1:
		results = [_parse_lef_file(a) for a in args]
	else:
		with mp.Pool(processes=LEF_WORKERS) as pool:
			results = pool.map(_parse_lef_file, args)
	for d in results:
		macro_size.update(d)

# Build existing rectangles for overlap checks
# Use macro sizes; if unknown, fall back to width = one site and height = row_height
t0 = t_now()
existing_rects = []
for cell, (x, y, orient) in cell_pos_map.items():
	lib = cell_lib_map.get(cell)
	w, h = None, None
	if not FAST:
		if lib and lib in macro_size:
			w, h = macro_size[lib]
		else:
			# Attempt to find a close variant key (e.g., library variations)
			if lib:
				if lib.endswith('_ASAP7_75t_R') and lib[:-2] in macro_size:
					w, h = macro_size[lib[:-2]]
	if w is None or h is None:
		# In FAST mode or if size unknown, approximate as one site x one row
		w, h = site_step_x, row_height
	xl, yl, xh, yh = x, y, x + w, y + h
	existing_rects.append((xl, yl, xh, yh))
t_log('build rects/bins/rows', t0)

# Spatial bins for fast overlap queries
BIN_COLS = 50
BIN_ROWS = 4
bin_w = max(site_step_x * BIN_COLS, site_step_x)
bin_h = max(row_height * BIN_ROWS, row_height)
rect_bins = defaultdict(list)


def rect_to_bins(r):
	xl, yl, xh, yh = r
	bx0 = xl // bin_w
	by0 = yl // bin_h
	bx1 = (max(xl, xh - 1)) // bin_w
	by1 = (max(yl, yh - 1)) // bin_h
	return bx0, by0, bx1, by1


def add_rect(r):
	bx0, by0, bx1, by1 = rect_to_bins(r)
	for bx in range(bx0, bx1 + 1):
		for by in range(by0, by1 + 1):
			rect_bins[(bx, by)].append(r)


def overlaps_any(r):
	# FAST: row-based quick overlap check
	if FAST and row_occupancy:
		xl, yl, xh, yh = r
		for ry in row_occupancy.keys():
			if ry >= yl and ry < yh:
				intervals = row_occupancy.get(ry, [])
				# binary search in intervals
				lo, hi = 0, len(intervals)
				while lo < hi:
					mid = (lo + hi) // 2
					if intervals[mid][0] < xl:
						lo = mid + 1
					else:
						hi = mid
				# check neighbor intervals for overlap
				for j in (lo - 1, lo, lo + 1):
					if 0 <= j < len(intervals):
						ixl, ixh = intervals[j]
						if not (xh <= ixl or ixh <= xl):
							return True
		return False
	# Non-FAST: use bins
	bx0, by0, bx1, by1 = rect_to_bins(r)
	for bx in range(bx0, bx1 + 1):
		for by in range(by0, by1 + 1):
			for er in rect_bins.get((bx, by), []):
				x1l, y1l, x1h, y1h = r
				x2l, y2l, x2h, y2h = er
				if not (x1h <= x2l or x2h <= x1l or y1h <= y2l or y2h <= y1l):
					return True
	return False

# Seed bins with existing rectangles (skip in FAST mode)
if not FAST:
	for er in existing_rects:
		add_rect(er)

# Per-row occupancy intervals for fast, DP-like legal site search
row_occupancy = {}

def _merge_intervals(intervals):
	if not intervals:
		return []
	intervals.sort(key=lambda t: t[0])
	merged = []
	sx, ex = intervals[0]
	for a, b in intervals[1:]:
		if a <= ex:
			ex = max(ex, b)
		else:
			merged.append((sx, ex))
			sx, ex = a, b
	merged.append((sx, ex))
	return merged

def _align_up_to_grid(x):
	return ((x + site_step_x - 1) // site_step_x) * site_step_x

def _align_down_to_grid(x):
	return (x // site_step_x) * site_step_x

def _align_nearest_grid(x):
	return ((x + site_step_x // 2) // site_step_x) * site_step_x

def _build_row_occupancy():
	global row_occupancy
	# Determine needed rows: prioritize rows of target cells (and neighbors) in FAST
	if FAST and fast_target_cells:
		needed_rows = set()
		for c in fast_target_cells:
			if c in cell_pos_map:
				_, y, _ = cell_pos_map[c]
				if y in row_ys:
					needed_rows.add(y)
					# neighbor rows if exist
					if row_height:
						if (y - row_height) in row_ys:
							needed_rows.add(y - row_height)
						if (y + row_height) in row_ys:
							needed_rows.add(y + row_height)
		# fallback if none found
		if not needed_rows:
			needed_rows = set(row_ys)
	else:
		needed_rows = set(row_ys)
	row_occupancy = {ry: [] for ry in needed_rows}
	# Build intervals by iterating cells once
	for cell, (x, y, _orient) in cell_pos_map.items():
		if y not in row_occupancy:
			continue
		lib = cell_lib_map.get(cell)
		w = None
		if lib and lib in macro_size:
			w = macro_size[lib][0]
		elif lib and lib.endswith('_ASAP7_75t_R') and lib[:-2] in macro_size:
			w = macro_size[lib[:-2]][0]
		if w is None:
			w = site_step_x
		xl = x
		xh = x + w
		row_occupancy[y].append((xl, xh))
	# Merge per-row intervals
	for ry in list(row_occupancy.keys()):
		row_occupancy[ry] = _merge_intervals(row_occupancy[ry])


def _occupancy_insert(row_y, xl, xh):
	lst = row_occupancy.get(row_y)
	if lst is None:
		return
	# insert and merge locally
	lo, hi = 0, len(lst)
	while lo < hi:
		mid = (lo + hi) // 2
		if lst[mid][0] < xl:
			lo = mid + 1
		else:
			hi = mid
	lst.insert(lo, (xl, xh))
	# merge around lo
	start = max(0, lo - 1)
	end = min(len(lst) - 1, lo + 1)
	i = start
	out = lst[:start]
	cur_s, cur_e = lst[start]
	for j in range(start + 1, end + 2):
		if j < len(lst) and lst[j][0] <= cur_e:
			cur_e = max(cur_e, lst[j][1])
		else:
			out.append((cur_s, cur_e))
			if j < len(lst):
				cur_s, cur_e = lst[j]
			else:
				cur_s, cur_e = None, None
	if end + 2 < len(lst):
		out.extend(lst[end + 2:])
	row_occupancy[row_y] = out


def _find_slot_in_row(row_y, target_x, w, xmin=None, xmax=None):
	if row_y not in row_occupancy:
		return None
	xl_die, yl_die, xh_die, yh_die = _die
	left_bound = xl_die if xmin is None else max(xl_die, xmin)
	right_bound = xh_die if xmax is None else min(xh_die, xmax)
	if right_bound - left_bound < w:
		return None
	intervals = row_occupancy[row_y]
	# iterate free gaps between occupied intervals
	prev_end = left_bound
	best_cx = None
	best_dist = None
	def _consider_gap(gap_l, gap_r):
		nonlocal best_cx, best_dist
		if gap_r <= gap_l:
			return
		start = _align_up_to_grid(gap_l)
		max_cx = gap_r - w
		end = _align_down_to_grid(max_cx)
		if end < start:
			return
		cx = _align_nearest_grid(target_x)
		if cx < start:
			cx = start
		elif cx > end:
			cx = end
		d = abs(cx - target_x)
		if (best_dist is None) or (d < best_dist):
			best_cx = cx
			best_dist = d
	# gaps before first, between, and after last
	for (oxl, oxh) in intervals:
		# gap [prev_end, oxl)
		if oxl > prev_end:
			_consider_gap(prev_end, oxl)
		prev_end = max(prev_end, oxh)
	# tail gap
	if prev_end < right_bound:
		_consider_gap(prev_end, right_bound)
	return best_cx


def find_slot_near(target_x, target_y, w, h):
	if not row_ys or h > row_height or not row_occupancy:
		return None, None
	candidate_rows = sorted(list(row_ys), key=lambda ry: abs(ry - target_y))
	for ry in candidate_rows:
		cx = _find_slot_in_row(ry, target_x, w)
		if cx is not None:
			return cx, ry
	return None, None


def find_slot_in_bbox(target_x, target_y, w, h, xmin, ymin, xmax, ymax):
	if not row_ys or h > row_height or not row_occupancy:
		return None, None
	xmin2 = max(_die[0], xmin)
	ymin2 = max(_die[1], ymin)
	xmax2 = min(_die[2], xmax)
	ymax2 = min(_die[3], ymax)
	rows_in_box = [ry for ry in row_ys if ry >= ymin2 and ry + h <= ymax2]
	if not rows_in_box:
		return None, None
	candidate_rows = sorted(rows_in_box, key=lambda ry: abs(ry - target_y))
	for ry in candidate_rows:
		cx = _find_slot_in_row(ry, target_x, w, xmin2, xmax2)
		if cx is not None:
			return cx, ry
	return None, None

# Build per-row occupancy once
if row_ys:
	_build_row_occupancy()

# Quick helpers

def rects_overlap(a, b):
	x1l, y1l, x1h, y1h = a
	x2l, y2l, x2h, y2h = b
	return not (x1h <= x2l or x2h <= x1l or y1h <= y2l or y2h <= y1l)


def within_die(r):
	xl, yl, xh, yh = r
	dxl, dyl, dxh, dyh = _die
	return xl >= dxl and yl >= dyl and xh <= dxh and yh <= dyh


def is_legal_site(x, y):
	# Align checks
	if x % site_step_x != 0:
		return False
	if row_ys and y not in row_ys:
		return False
	return True


def find_nearest_legal_position(target_x, target_y, w, h):
	# Prefer same row first
	candidate_rows = []
	if row_ys:
		# sort by distance in rows
		candidate_rows = sorted(list(row_ys), key=lambda ry: abs(ry - target_y))
	else:
		candidate_rows = [target_y]
	max_cols = 100
	for ry in candidate_rows:
		# Horizontal scan around target_x
		# ensure alignment to site grid
		base_col = target_x // site_step_x
		for radius in range(0, 80):
			for dx_col in (-radius, radius):
				cx = (base_col + dx_col) * site_step_x
				cy = ry
				rect = (cx, cy, cx + w, cy + h)
				if not within_die(rect):
					continue
				# fast overlap
				if not overlaps_any(rect) and is_legal_site(cx, cy):
					return cx, cy
	return None, None

# BBox-prioritized search

def find_position_in_bbox(target_x, target_y, w, h, xmin, ymin, xmax, ymax):
	# Clamp search box to DIEAREA and fit width/height
	xmin2 = max(_die[0], xmin)
	ymin2 = max(_die[1], ymin)
	xmax2 = min(_die[2], xmax)
	ymax2 = min(_die[3], ymax)
	# Valid columns range after placing width
	col_min = (xmin2 + (site_step_x - 1)) // site_step_x
	col_max = (max(xmin2, xmax2 - w)) // site_step_x
	if col_max < col_min:
		return None, None
	# Candidate rows within box
	rows_in_box = [ry for ry in row_ys if ry >= ymin2 and ry + h <= ymax2]
	if not rows_in_box and row_ys:
		return None, None
	candidate_rows = sorted(rows_in_box, key=lambda ry: abs(ry - target_y)) if row_ys else [target_y]
	for ry in candidate_rows:
		base_col = max(col_min, min(col_max, target_x // site_step_x))
		for radius in range(0, 80):
			left = base_col - radius
			right = base_col + radius
			for col in (left, right):
				if col < col_min or col > col_max:
					continue
				cx = col * site_step_x
				cy = ry
				rect = (cx, cy, cx + w, cy + h)
				if not within_die(rect):
					continue
				# fast overlap
				if not overlaps_any(rect) and is_legal_site(cx, cy):
					return cx, cy
	return None, None

# Load net arcs for HPWL statistics (optional)
net_arcs = {} if (SKIP_HPWL or FAST) else load_net_arcs_for_hpwl_optimization(def_file)
t_log('load net_arcs', t0)

# Locate NETS section
t0 = t_now()
nets_start = nets_end = None
for idx, line in enumerate(lines):
	if line.strip().startswith('NETS'):
		nets_start = idx
		continue
	if nets_start is not None and line.strip().startswith('END NETS'):
		nets_end = idx
		break
if nets_start is None or nets_end is None:
	print("Error: NETS section not found in DEF.", file=sys.stderr)
	sys.exit(3)
t_log('locate NETS', t0)

# Parse original NET count
orig_net_count = None
m_nc = RE_NETS_COUNT.search(lines[nets_start])
if m_nc:
	try:
		orig_net_count = int(m_nc.group(1))
	except Exception:
		orig_net_count = None

# Build reverse index for nets and net-pin maps
pin_to_occurs = {}
net_to_pins = {}
pin_to_net = {}

if FAST and fast_target_cells:
	pin_to_occurs, net_to_pins, pin_to_net = build_net_index_parallel(lines, nets_start, nets_end, target_cells=fast_target_cells)
else:
	pin_to_occurs, net_to_pins, pin_to_net = build_net_index_parallel(lines, nets_start, nets_end, target_cells=None)
t_log('build NETS index', t0)

# Stage 2: read changelist, produce deltas
current_def_cells = get_original_def_cells()
new_nets = []
# line_idx -> list of (start, end, replacement)
line_replacements = {}
# global de-dup to avoid scheduling the same span multiple times
scheduled_spans = set()
pending_inserts = []  # defer buffer component creation for parallel placement
pending_net_edits = {}  # new_cell -> {occurrence:(line_idx,start,end), new_net:str, target_cell:str, target_pin:str}

with open(changelist_file, 'r') as f:
	for raw in f:
		line = raw.strip()
		if line.startswith('insert_buffer'):
			m = RE_INSERT_BUFFER.match(line)
			if not m:
				continue
			pins_blob = m.group(1)
			lib_cell_full = m.group(2)
			new_cell = m.group(3)
			new_net = m.group(4)
			lib_cell = lib_cell_full.split('/')[-1]
			# track command
			_insert_rec = {'new_cell': new_cell, 'raw': raw, 'success': False}
			insert_cmds.append(_insert_rec)
			commands_in_order.append(('insert', _insert_rec))
			
			target_cell = pins_blob.strip().split()[0].split('/')[0] if ('/' in pins_blob.strip().split()[0]) else (pins_blob.strip().split()[0] if pins_blob.strip().split() else None)
			target_pin = pins_blob.strip().split()[0].split('/')[1] if ('/' in pins_blob.strip().split()[0]) else 'Y'
			
			if target_cell and target_cell in current_def_cells:
				# Defer placement to parallel phase
				pending_inserts.append((new_cell, lib_cell, target_cell, target_pin))
				# Record planned NET edits tied to this buffer
				occurs = pin_to_occurs.get((target_cell, target_pin), [])
				occ = occurs[0] if occurs else None
				pending_net_edits[new_cell] = {
					'occurrence': occ,
					'new_net': new_net,
					'target_cell': target_cell,
					'target_pin': target_pin,
				}
			else:
				print(f"Warning: Skipping buffer insertion for non-existent cell: {target_cell}", file=sys.stderr)
		elif line.startswith('size_cell'):
			m = RE_SIZE_CELL.match(line)
			if not m:
				continue
			cell = m.group(1)
			new_lib_full = m.group(2)
			new_lib = new_lib_full.split('/')[-1]
			# default record
			_sc_rec = {'cell': cell, 'raw': raw, 'success': False}
			if cell.strip() in {c.strip() for c in current_def_cells} and cell.strip() in {c.strip() for c in cell_line_map}:
				idx = cell_line_map[cell]
				old_line = comp_lines[idx]
				new_line = re.sub(r'-\s+\S+\s+\S+', f'- {cell} {new_lib}', old_line)
				comp_lines[idx] = new_line
				_sc_rec['success'] = True
			else:
				print(f"Warning: Skipping gate sizing for non-existent cell: {cell}", file=sys.stderr)
			size_cmds.append(_sc_rec)
			commands_in_order.append(('size', _sc_rec))

# Apply scheduled line replacements in NETS, sorting by span descending per line
for line_idx, repls in line_replacements.items():
	# de-duplicate spans per line and enforce non-overlap
	unique = {}
	for s, e, r in repls:
		unique.setdefault((s, e), r)
	repls_dedup = [(s, e, unique[(s, e)]) for (s, e) in unique.keys()]
	repls_sorted = sorted(repls_dedup, key=lambda t: (t[0], t[1]), reverse=True)
	line_text = lines[line_idx]
	min_allowed = float('inf')
	for start, end, rep in repls_sorted:
		# skip overlaps with already-applied region
		if end > min_allowed:
			continue
		line_text = line_text[:start] + rep + line_text[end:]
		min_allowed = start
	lines[line_idx] = line_text

t_log('apply NET edits', t0)

# Insert new nets right before END NETS
if new_nets:
	insert_idx = nets_end
	lines = lines[:insert_idx] + new_nets + lines[insert_idx:]
	# Update NETS count without rescanning
	if orig_net_count is None:
		# Fallback: count from section header to insertion point (minimal scan)
		net_count = 0
		for i in range(nets_start + 1, insert_idx + len(new_nets)):
			if lines[i].lstrip().startswith('- '):
				net_count += 1
		lines[nets_start] = f'NETS {net_count} ;\n'
	else:
		lines[nets_start] = f'NETS {orig_net_count + len(new_nets)} ;\n'

t_log('insert new nets + update count', t0)

def _row_place_worker(args):
	row_y, tasks, site_step_x, row_height, die, macro_size, cell_pos_map, pin_to_net, net_to_pins = args
	# build local occupancy from existing cells on this row
	intervals = []
	for cell, (x, y, _o) in cell_pos_map.items():
		if y == row_y:
			lib = macro_size.get(cell_pos_map and None)
			w = None
			lib_name = None
			# lib name is not stored here; we approximate width as one site for baseline
			w = site_step_x
			intervals.append((x, x + w))
	intervals = _merge_intervals(intervals)
	placements = []
	def _insert_interval(iv, l, r):
		iv.append((l, r))
		iv[:] = _merge_intervals(iv)
	for (new_cell, lib_cell, target_cell, target_pin) in sorted(tasks, key=lambda t: cell_pos_map.get(t[2], (0, 0, 'N'))[0]):
		x, y, orient = cell_pos_map[target_cell]
		bw = macro_size.get(lib_cell, (site_step_x, row_height))[0]
		# derive bbox limits
		net_name = pin_to_net.get((target_cell, target_pin))
		xmin = xmax = None
		if net_name and net_name in net_to_pins:
			xs = []
			for c_ref, p_ref in net_to_pins[net_name]:
				if c_ref in cell_pos_map:
					xr, yr, _ = cell_pos_map[c_ref]
					xs.append(xr)
			if xs:
				xmin, xmax = min(xs), max(xs)
		# search slot in this row
		cx = _find_slot_in_row(row_y, x, bw, xmin, xmax) if xmin is not None else _find_slot_in_row(row_y, x, bw)
		if cx is None:
			# last resort: start from DIEAREA left
			cx = _find_slot_in_row(row_y, _die[0], bw)
		if cx is None:
			continue
		placements.append((new_cell, lib_cell, cx, row_y, orient))
		_insert_interval(intervals, cx, cx + bw)
	return placements

# Parallel per-row placement if there are pending inserts
if pending_inserts:
	# group by target row
	row_to_tasks = defaultdict(list)
	for item in pending_inserts:
		new_cell, lib_cell, target_cell, target_pin = item
		if target_cell in cell_pos_map:
			_, y, _ = cell_pos_map[target_cell]
			row_to_tasks[y].append(item)
	args = []
	for ry, tasks in row_to_tasks.items():
		args.append((ry, tasks, site_step_x, row_height, _die, macro_size, cell_pos_map, pin_to_net, net_to_pins))
	placements_all = []
	workers = max(1, min(NETS_WORKERS, mp.cpu_count()))
	# print(f"Row placement: rows={len(args)} workers={workers}")
	if workers == 1:
		for a in args:
			placements_all.extend(_row_place_worker(a))
	else:
		ctx = mp.get_context('fork')
		with ctx.Pool(processes=workers) as pool:
			for res in pool.imap_unordered(_row_place_worker, args, chunksize=1):
				placements_all.extend(res)

	# Final legalization with exact widths per row
	def _merge_intervals_local(iv):
		return _merge_intervals(iv)
	def _find_slot_in_row_intervals(intervals, row_y, target_x, w, xmin=None, xmax=None):
		xl_die, yl_die, xh_die, yh_die = _die
		left_bound = xl_die if xmin is None else max(xl_die, xmin)
		right_bound = xh_die if xmax is None else min(xh_die, xmax)
		if right_bound - left_bound < w:
			return None
		prev_end = left_bound
		best_cx = None
		best_dist = None
		def _consider_gap(gap_l, gap_r):
			nonlocal best_cx, best_dist
			if gap_r <= gap_l:
				return
			start = _align_up_to_grid(gap_l)
			max_cx = gap_r - w
			end = _align_down_to_grid(max_cx)
			if end < start:
				return
			cx = _align_nearest_grid(target_x)
			if cx < start:
				cx = start
			elif cx > end:
				cx = end
			d = abs(cx - target_x)
			if (best_dist is None) or (d < best_dist):
				best_cx = cx
				best_dist = d
		for (oxl, oxh) in intervals:
			if oxl > prev_end:
				_consider_gap(prev_end, oxl)
			prev_end = max(prev_end, oxh)
		if prev_end < right_bound:
			_consider_gap(prev_end, right_bound)
		return best_cx

	# build exact intervals from existing cells
	row_exact = defaultdict(list)
	for cell, (x, y, _o) in cell_pos_map.items():
		if row_ys and y not in row_ys:
			continue
		lib = cell_lib_map.get(cell)
		w = None
		if lib and lib in macro_size:
			w = macro_size[lib][0]
		elif lib and lib.endswith('_ASAP7_75t_R') and lib[:-2] in macro_size:
			w = macro_size[lib[:-2]][0]
		if w is None:
			w = site_step_x
		row_exact[y].append((x, x + w))
	for ry in list(row_exact.keys()):
		row_exact[ry] = _merge_intervals_local(row_exact[ry])

	legalized = []
	for (new_cell, lib_cell, bx, by, orient_out) in sorted(placements_all, key=lambda t: (t[3], t[2])):
		bw = macro_size.get(lib_cell, (site_step_x, row_height))[0]
		intervals = row_exact.get(by, [])
		# check overlap at proposed bx
		overlap = False
		for (l, r) in intervals:
			if not (bx + bw <= l or r <= bx):
				overlap = True
				break
		if not overlap and bx % site_step_x == 0:
			legalized.append((new_cell, lib_cell, bx, by, orient_out))
			row_exact[by] = _merge_intervals_local(intervals + [(bx, bx + bw)])
			continue
		# try find nearest slot in same row
		replacement = _find_slot_in_row_intervals(intervals, by, bx, bw)
		if replacement is not None:
			cx = replacement
			legalized.append((new_cell, lib_cell, cx, by, orient_out))
			row_exact[by] = _merge_intervals_local(intervals + [(cx, cx + bw)])
			continue
		# as last resort, try neighbor rows
		candidates = []
		if row_height and row_ys:
			for dy in (-row_height, row_height):
				ry2 = by + dy
				if ry2 in row_exact:
					cx2 = _find_slot_in_row_intervals(row_exact[ry2], ry2, bx, bw)
					if cx2 is not None:
						candidates.append((abs(ry2 - by), cx2, ry2))
		if candidates:
			candidates.sort()
			_, cx, ry_sel = candidates[0]
			legalized.append((new_cell, lib_cell, cx, ry_sel, orient_out))
			row_exact[ry_sel] = _merge_intervals_local(row_exact[ry_sel] + [(cx, cx + bw)])
		else:
			# will handle in global fallback
			pass

	# Global fallback: place any remaining buffers across all rows
	_cache = {'rows': None}
	def _place_anywhere(new_cell, lib_cell, target_cell, target_pin):
		bw = macro_size.get(lib_cell, (site_step_x, row_height))[0]
		tx, ty, _ = cell_pos_map.get(target_cell, (0, 0, 'N'))
		if _cache['rows'] is None:
			rows_list = list(row_exact.keys()) if row_exact else list(row_ys)
			_cache['rows'] = sorted(rows_list, key=lambda ry: abs(ry - ty)) if rows_list else [ty]
		# try all rows in order of proximity
		for ry in _cache['rows']:
			intervals = row_exact.get(ry)
			if intervals is None:
				intervals = []
				row_exact[ry] = intervals
			cx = _find_slot_in_row_intervals(intervals, ry, tx, bw)
			if cx is not None:
				row_exact[ry] = _merge_intervals_local(intervals + [(cx, cx + bw)])
				return cx, ry
		# as ultimate fallback, scan left-to-right on each row
		xl_die, _, xh_die, _ = _die
		for ry in _cache['rows']:
			intervals = row_exact.get(ry, [])
			cx = _find_slot_in_row_intervals(intervals, ry, xl_die, bw)
			if cx is not None:
				row_exact[ry] = _merge_intervals_local(intervals + [(cx, cx + bw)])
				return cx, ry
		return None, None

	# identify not-yet-placed buffers from pending list
	placed_keys = {c for (c, _lib, _x, _y, _o) in legalized}
	remaining = []
	for (new_cell, lib_cell, target_cell, target_pin) in pending_inserts:
		if new_cell not in placed_keys:
			remaining.append((new_cell, lib_cell, target_cell, target_pin))
	for (new_cell, lib_cell, target_cell, target_pin) in remaining:
		cx, ry = _place_anywhere(new_cell, lib_cell, target_cell, target_pin)
		if cx is not None and ry is not None:
			orient_out = cell_pos_map.get(target_cell, (0, 0, 'N'))[2]
			legalized.append((new_cell, lib_cell, cx, ry, orient_out))
		else:
			print(f"Warning: Could not place buffer {new_cell} anywhere in DIEAREA; skipping.", file=sys.stderr)

	# append component lines
	# Append all legalized components; NET edits will be filtered later by occurrence
	placed_set = set()
	for (new_cell, lib_cell, bx, by, orient_out) in legalized:
		new_comp_line = f"  - {new_cell} {lib_cell} + PLACED ( {bx} {by} ) {orient_out} ;\n"
		comp_lines.append(new_comp_line)
		placed_set.add(new_cell)
		if row_ys:
			_occupancy_insert(by, bx, bx + macro_size.get(lib_cell, (site_step_x, row_height))[0])

	# Now apply NET edits for successfully placed buffers
	post_line_replacements = {}
	post_scheduled = set()
	post_new_nets = []
	for new_cell in placed_set:
		meta = pending_net_edits[new_cell]
		if not meta.get('occurrence'):
			continue
		(line_idx, span_start, span_end) = meta['occurrence']
		key = (line_idx, span_start, span_end)
		if key not in post_scheduled:
			repl = f"( {new_cell} Y )"
			post_line_replacements.setdefault(line_idx, []).append((span_start, span_end, repl))
			post_scheduled.add(key)
		# create new net text
		target_cell = meta['target_cell']
		target_pin = meta['target_pin']
		new_net_name = meta['new_net']
		net_def = [f"- {new_net_name}\n", f"  ( {new_cell} Y )\n", f"  ( {target_cell} {target_pin} )\n", " ;\n"]
		post_new_nets.append(''.join(net_def))

	# apply replacements
	for line_idx, repls in post_line_replacements.items():
		unique = {}
		for s, e, r in repls:
			unique.setdefault((s, e), r)
		repls_dedup = [(s, e, unique[(s, e)]) for (s, e) in unique.keys()]
		repls_sorted = sorted(repls_dedup, key=lambda t: (t[0], t[1]), reverse=True)
		line_text = lines[line_idx]
		min_allowed = float('inf')
		for start, end, rep in repls_sorted:
			if end > min_allowed:
				continue
			line_text = line_text[:start] + rep + line_text[end:]
			min_allowed = start
		lines[line_idx] = line_text

	# insert new nets
	if post_new_nets:
		insert_idx = nets_end
		lines = lines[:insert_idx] + post_new_nets + lines[insert_idx:]
		if orig_net_count is None:
			net_count = 0
			for i in range(nets_start + 1, insert_idx + len(post_new_nets)):
				if lines[i].lstrip().startswith('- '):
					net_count += 1
			lines[nets_start] = f'NETS {net_count} ;\n'
		else:
			lines[nets_start] = f'NETS {orig_net_count + len(post_new_nets)} ;\n'

	# After placement, mark successful insert_buffer commands
	try:
		placed_ok = set(placed_set)
		for rec in insert_cmds:
			if rec['new_cell'] in placed_ok:
				rec['success'] = True
	except Exception as e:
		print(f"Warning: could not finalize insert results: {e}", file=sys.stderr)

	# Update changelist to keep only successful actions
	try:
		successful_lines = []
		for kind, rec in commands_in_order:
			if rec.get('success'):
				line_out = rec['raw'] if rec['raw'].endswith('\n') else (rec['raw'] + '\n')
				successful_lines.append(line_out)
		with open(changelist_file, 'w') as fchg:
			fchg.write(f"# updated by apply_changelist_to_def.py: kept {len(successful_lines)} removed {len(commands_in_order)-len(successful_lines)}\n")
			for l in successful_lines:
				fchg.write(l)
	except Exception as e:
		print(f"Warning: Failed to update changelist: {e}", file=sys.stderr)

t_log('parallel row placement + legalization', t0)

# Replace COMPONENTS payload
lines[comp_start+1:comp_end] = comp_lines
t_log('write components + counts + output', t0)

# Update COMPONENTS count to reflect appended buffers
try:
	comp_count = sum(1 for l in comp_lines if l.lstrip().startswith('- '))
	lines[comp_start] = re.sub(r'COMPONENTS\s+\d+\s*;', f'COMPONENTS {comp_count} ;', lines[comp_start])
except Exception as e:
	print(f"Warning: Failed to update COMPONENTS count: {e}", file=sys.stderr)

with open(output_def, 'w') as f:
	f.writelines(lines) 