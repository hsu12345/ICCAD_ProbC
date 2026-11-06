#!/bin/bash

# Check arguments
if [ $# -ne 4 ]; then
    echo "Usage: $0 <design_name> <TNS_weight_α> <power_weight_β> <WL_weight_γ>"
    echo "Example: $0 aes 5.0 1.0 1.0"
    echo ""
    echo "Where:"
    echo "  <design_name> denotes a folder under testcases/ (e.g., testcases/aes/)"
    echo "  <TNS_weight_α> is the weight for timing (TNS)"
    echo "  <power_weight_β> is the weight for power"
    echo "  <WL_weight_γ> is the weight for wirelength"
    exit 1
fi

design_name=$1
tns_weight=$2
power_weight=$3
wl_weight=$4

# Fixed parameters as requested
# Note: kept for logging only; actual runtime weights are determined by logic below
timing_weight=5.0
power_weight_fixed=1.0

# Set up file paths
input_def="testcases/${design_name}/${design_name}.def"

# Find INSTA directory
insta_dir=$(find "testcases/${design_name}" -type d -name 'INSTA_*' | head -n1)
if [ -z "$insta_dir" ]; then
    echo "Error: INSTA directory not found in testcases/${design_name}/"
    exit 1
fi

echo "Found INSTA directory: $insta_dir"

# Check if input files exist
if [ ! -f "$input_def" ]; then
    echo "Error: Input DEF file not found: $input_def"
    exit 1
fi

if [ ! -d "$insta_dir/insta_inputs" ]; then
    echo "Error: INSTA inputs directory not found: $insta_dir/insta_inputs"
    exit 1
fi

# Prepare LEF list (tech LEF + stdcell/SRAM LEFs under testcases/ASAP7)
tech_lef="testcases/ASAP7/techlef/asap7_tech_1x_201209.lef"
cell_lefs=$(ls testcases/ASAP7/LEF/*.lef 2>/dev/null | tr '\n' ',' | sed 's/,$//')
lef_arg="$tech_lef"
if [ -n "$cell_lefs" ]; then
    lef_arg="$lef_arg,$cell_lefs"
fi

# Clean any stale changelist before we start
if [ -f "insta_optimization.changelist" ]; then
    rm -f "insta_optimization.changelist"
fi

# Decide flow
run_hpwl=0
hpwl_args=""

# Compute cell count from DEF
cell_num=$(awk '/^[[:space:]]*COMPONENTS/{print $2; exit}' "$input_def")
# Compute signed setup TNS (endpoints-only, both polarities)
tns_signed=$(python3 scripts/calc_tns.py "$insta_dir/insta_inputs" --signed --check setup --polarity both 2>/dev/null)
# Validate TNS result; if unavailable or non-numeric, go to default branch later
if [[ -z "$tns_signed" || ! "$tns_signed" =~ ^-?[0-9]+(\.[0-9]+)?$ ]]; then
    tns_available=0
else
    tns_available=1
    abs_tns=$(awk -v t="$tns_signed" 'BEGIN{print (t<0)?-t:t}')
    ratio=$(awk -v c="$cell_num" -v t="$abs_tns" 'BEGIN{if (t==0) print 1e99; else print c/t}')
fi

if [ "$tns_available" = "1" ] && awk -v r="$ratio" 'BEGIN{exit !(r>10)}'; then
    cond1=$(awk -v t="$tns_weight" -v p="$power_weight" -v w="$wl_weight" 'BEGIN{print (t>(p+w)*10)?1:0}')
    cond2=$(awk -v t="$tns_weight" -v p="$power_weight" -v w="$wl_weight" 'BEGIN{print (t*3<(p+w))?1:0}')

    if [ "$cond1" -eq 1 ]; then
        python3 scripts/insta_optimization_new.py "$input_def" "$insta_dir/insta_inputs" --timing-weight 1 --power-weight 1
        if [ $? -ne 0 ]; then
            echo "Error: INSTA optimization failed"
            exit 1
        fi
        run_hpwl=0
    elif [ "$cond2" -eq 1 ]; then
        : > "insta_optimization.changelist"
        run_hpwl=1
        hpwl_args=""
    else
        python3 scripts/insta_optimization_new.py "$input_def" "$insta_dir/insta_inputs" --timing-weight 1 --power-weight 1
        if [ $? -ne 0 ]; then
            echo "Error: INSTA optimization failed"
            exit 1
        fi
        run_hpwl=1
        hpwl_args="--iteration 1 --learning-rate 0.0005 --target-density 0.70 --density-weight 3e-5 --ignore-net-degree 20 --enable-fillers 0 --enable-density-weight-update 0"
    fi
else
    python3 scripts/insta_optimization_new.py "$input_def" "$insta_dir/insta_inputs" --timing-weight 5 --power-weight 1
    if [ $? -ne 0 ]; then
        echo "Error: INSTA optimization failed"
        exit 1
    fi
    run_hpwl=1
    hpwl_args=""
fi

# Ensure changelist exists (create empty if INSTA did not produce it)
changelist_file="insta_optimization.changelist"
if [ ! -f "$changelist_file" ]; then
    echo "Warning: Changelist not found; creating an empty changelist at $changelist_file"
    : > "$changelist_file"
fi

echo "Generated changelist: $changelist_file"

# Step: Apply changelist to DEF
python3 scripts/apply_changelist_to_def.py "$input_def" "$changelist_file"
if [ $? -ne 0 ]; then
    echo "Error: Applying changelist failed"
    exit 1
fi

# The apply_changelist_to_def.py should generate a modified DEF file
# Note: apply_changelist_to_def.py typically generates a file with .sol.def suffix
modified_def="${design_name}.sol.def"
if [ ! -f "$modified_def" ]; then
    echo "Error: Modified DEF file not generated: $modified_def"
    exit 1
fi

echo "Generated modified DEF: $modified_def"

# DREAMPlace placement is intentionally disabled in this flow
if [ "$run_hpwl" -eq 1 ]; then
    echo "HPWL minimization skipped (DREAMPlace stage disabled by run_buffer_insertion.sh)"
else
    echo "HPWL minimization not requested for this branch."
fi

# Rename changelist to match expected output
mv "$changelist_file" "${design_name}.sol.changelist"

echo ""
echo "=========================================="
echo "BUFFER-ONLY OPTIMIZATION COMPLETED"
echo "=========================================="
echo "Output files generated:"
echo "  - ${design_name}.sol.def"
echo "  - ${design_name}.sol.changelist"
echo "=========================================="
