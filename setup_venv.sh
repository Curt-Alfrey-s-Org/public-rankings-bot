#!/bin/bash
# Setup virtual environment for Rankings Bot + Web GUI
# Installs both main requirements and API requirements

set -e

echo "Setting up virtual environment for Rankings Bot..."
echo ""

# Create virtual environment
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo "✅ Virtual environment created"
else
    echo "Virtual environment already exists"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip in venv
echo "Upgrading pip..."
pip install --upgrade pip

# Install main dependencies
echo "Installing main bot dependencies..."
pip install -r requirements.txt

# Install API dependencies
echo "Installing FastAPI dependencies..."
pip install -r requirements-api.txt

echo ""
echo "✅ Virtual environment setup complete!"
echo ""
echo "To use the virtual environment:"
echo "  source venv/bin/activate"
echo ""
echo "To start the API server:"
echo "  source venv/bin/activate"
echo "  ./start_api.sh"
echo ""