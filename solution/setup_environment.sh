#!/bin/bash
source /opt/conda/etc/profile.d/conda.sh
source /opt/conda/etc/profile.d/mamba.sh
mamba activate probC_env

export DEBIAN_FRONTEND=noninteractive
export TZ=${TZ:-Etc/UTC}
ln -fs /usr/share/zoneinfo/$TZ /etc/localtime 2>/dev/null || true
echo "$TZ" > /etc/timezone 2>/dev/null || true

echo "=========================================="
echo "Setting up ICCAD25 ProbC Environment"
echo "=========================================="

# Install system dependencies
echo "[STEP 1] Installing system dependencies..."
if command -v apt-get &> /dev/null; then
    # Debian/Ubuntu based systems
    apt-get update && apt-get install -y \
        bc \
        build-essential \
        libboost-dev \
        libboost-system-dev \
        libboost-filesystem-dev \
        protobuf-compiler \
        libprotobuf-dev \
        bison \
        flex \
        libcairo2-dev \
        libcairo2 \
        nano
elif command -v yum &> /dev/null; then
    # RHEL/CentOS based systems
    yum install -y \
        bc \
        gcc-c++ \
        boost-devel \
        protobuf-compiler \
        protobuf-devel \
        bison \
        flex \
        cairo-devel \
        nano
elif command -v dnf &> /dev/null; then
    # Fedora based systems
    dnf install -y \
        bc \
        gcc-c++ \
        boost-devel \
        protobuf-compiler \
        protobuf-devel \
        bison \
        flex \
        cairo-devel \
        nano
elif command -v apk &> /dev/null; then
    # Alpine Linux
    apk add \
        bc \
        build-base \
        boost-dev \
        protobuf-dev \
        bison \
        flex \
        cairo-dev \
        nano
else
    echo "Warning: Could not install system dependencies. Please install them manually."
fi

echo "[STEP 2] Installing Python dependencies for DREAMPlace..."
# Install Python dependencies for DREAMPlace
pip install numpy torch matplotlib cairocffi scipy shapely

echo "[STEP 3] Building DREAMPlace..."
# Navigate to DREAMPlace
cd DREAMPlace

# Install system dependencies (including BISON and Cairo)
echo "Installing system dependencies for DREAMPlace..."
apt-get update
apt-get install -y bison libcairo2-dev libcairo2

# Install Python dependencies
echo "Installing Python dependencies from requirements.txt..."
pip install -r requirements.txt

# Initialize submodules
echo "Initializing git submodules..."
git submodule init
cd /workspace/solution/DREAMPlace && git config --global --add safe.directory /workspace/solution/DREAMPlace/thirdparty/OpenTimer && git config --global --add safe.directory /workspace/solution/DREAMPlace/thirdparty/munkres-cpp && git config --global --add safe.directory /workspace/solution/DREAMPlace/thirdparty/cub && git config --global --add safe.directory /workspace/solution/DREAMPlace/thirdparty/pybind11
git submodule update

# Clean build and configure
echo "Cleaning previous build and creating new build directory..."
rm -rf build
mkdir build
cd build

# Configure with CMake
echo "Running CMake configuration..."
cmake .. -DCMAKE_INSTALL_PREFIX=../install -DPython_EXECUTABLE=$(which python)

# Build and install
echo "Building DREAMPlace (this may take several minutes)..."
make

echo "Installing DREAMPlace..."
make install

if [ $? -ne 0 ]; then
    echo "Error: DREAMPlace installation failed"
    exit 1
fi

cd ../..

echo "[STEP 4] Verifying DREAMPlace installation..."
# Test DREAMPlace installation
if python DREAMPlace/install/dreamplace/Placer.py --help > /dev/null 2>&1; then
    echo "✅ DREAMPlace installation successful!"
else
    echo "❌ DREAMPlace installation verification failed"
    echo "You may need to install additional dependencies or check the build logs"
fi

echo ""
echo "=========================================="
echo "Environment Setup Complete!"
echo "=========================================="
echo "Installed components:"
echo "  - System dependencies (bc, build tools, libraries)"
echo "  - Python dependencies (numpy, torch, matplotlib, etc.)"
echo "  - DREAMPlace (VLSI placement tool)"
echo ""
echo "You can now run the optimization pipeline with:"
echo "  ./run.sh <design_name> <TNS_weight> <power_weight> <WL_weight>"
echo "=========================================="
