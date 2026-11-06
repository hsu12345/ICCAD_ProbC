#!/bin/bash
#
# Calculate initial HPWL for all benchmark designs
# Outputs CSV format: Design,Cells,Nets,Pins,Initial_HPWL
#

# Resolve workspace directory
workspace_dir="$(cd "$(dirname "$0")" && pwd)"
cd "$workspace_dir"

# List of designs
designs=("des" "aes" "ac97_top" "aes_cipher_top" "pci_bridge32" "ariane")

echo "=========================================="
echo "Calculating Initial HPWL for All Designs"
echo "=========================================="
echo ""

# Create results directory
mkdir -p results/initial_hpwl

# CSV header
output_file="results/initial_hpwl/initial_hpwl_report.csv"
echo "Design,Initial_HPWL,HPWL_Formatted" > "$output_file"

# Process each design
for design in "${designs[@]}"; do
    echo "----------------------------------------"
    echo "Processing: $design"
    echo "----------------------------------------"
    
    input_def="testcases/${design}/${design}.def"
    
    if [ ! -f "$input_def" ]; then
        echo "ERROR: DEF not found: $input_def"
        echo "$design,ERROR,ERROR" >> "$output_file"
        echo ""
        continue
    fi
    
    # Calculate HPWL using our Python script
    result=$(python3 calc_hpwl.py "$input_def" --quiet 2>&1)
    
    if [ $? -ne 0 ]; then
        echo "ERROR calculating HPWL for $design"
        echo "$result"
        echo "$design,ERROR,ERROR" >> "$output_file"
        echo ""
        continue
    fi
    
    # Extract HPWL value from output
    hpwl=$(echo "$result" | grep "HPWL:" | awk '{print $2}')
    hpwl_formatted=$(echo "$result" | grep "HPWL:" | sed 's/.*(\(.*\))/\1/')
    
    if [ -z "$hpwl" ]; then
        echo "ERROR: Could not extract HPWL value"
        echo "$result"
        echo "$design,ERROR,ERROR" >> "$output_file"
    else
        echo "✓ HPWL: $hpwl ($hpwl_formatted)"
        echo "$design,$hpwl,$hpwl_formatted" >> "$output_file"
    fi
    
    echo ""
done

echo "=========================================="
echo "Summary Report"
echo "=========================================="
echo ""
cat "$output_file" | column -t -s ','
echo ""
echo "Full report saved to: $output_file"
echo "=========================================="

