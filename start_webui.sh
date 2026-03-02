#!/bin/bash
# Start the Novel Audiobook Generator Web UI

echo "🚀 Starting Novel Audiobook Generator Web UI..."
echo ""

# Check if gradio is installed
if ! python3 -c "import gradio" 2>/dev/null; then
    echo "❌ Gradio not found. Installing dependencies..."
    pip install -r requirements.txt
fi

# Start the web UI
echo "📱 Launching Web UI at http://localhost:7860"
echo "Press Ctrl+C to stop"
echo ""

python3 webui.py
