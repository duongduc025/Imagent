#!/bin/bash

# Install Material UI dependencies for Imagent Streamlit App
echo "=================================="
echo "  Imagent Material UI Installer"
echo "=================================="
echo ""

# Check if virtual environment is active
if [ -n "$VIRTUAL_ENV" ]; then
    PYTHON_CMD="pip"
    echo "✅ Virtual environment detected: $VIRTUAL_ENV"
elif [ -f "/venv/4kagent/bin/python" ]; then
    PYTHON_CMD="/venv/4kagent/bin/pip"
    echo "✅ Using Imagent venv: /venv/4kagent"
else
    PYTHON_CMD="pip"
    echo "⚠️  No virtual environment detected, using system pip"
fi

echo ""
echo "📦 Installing required packages..."
echo ""

# Install streamlit-elements (Material UI)
echo "Installing streamlit-elements..."
$PYTHON_CMD install streamlit-elements

# Install streamlit-image-comparison (if not already installed)
echo "Installing streamlit-image-comparison..."
$PYTHON_CMD install streamlit-image-comparison

# Verify installations
echo ""
echo "🔍 Verifying installations..."
echo ""

if /venv/4kagent/bin/python -c "import streamlit_elements" 2>/dev/null; then
    echo "✅ streamlit-elements: Installed"
else
    echo "❌ streamlit-elements: Failed"
fi

if /venv/4kagent/bin/python -c "import streamlit_image_comparison" 2>/dev/null; then
    echo "✅ streamlit-image-comparison: Installed"
else
    echo "❌ streamlit-image-comparison: Failed"
fi

echo ""
echo "=================================="
echo "  Installation Complete!"
echo "=================================="
echo ""
echo "🚀 To run the Material UI app:"
echo "   streamlit run app.py"
echo ""
echo "📚 Classic version backed up as:"
echo "   app_classic.py"
echo ""
