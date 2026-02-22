#!/bin/bash

# Navigate to the application root directory
cd "$(dirname "$0")"

# Optional: If you are using a virtual environment (e.g., venv), uncomment the next line to activate it before running.
# source venv/bin/activate

# 1. Start the Flask Webhook Server in the background
echo "Starting Webhook Server..."
python3 webhook_server.py &
WEBHOOK_PID=$!

# 2. Start the Streamlit Configuration UI in the foreground
echo "Starting Configuration UI..."
streamlit run config_ui.py

# 3. When Streamlit is closed, stop the Webhook server
echo "Shutting down..."
kill $WEBHOOK_PID
