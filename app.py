#!/usr/bin/env python3
"""
Synseer Vendor Logistics Database - Main Application Entry Point
Flask application for tracking, scoring, and visualizing component vendors.

Production-ready application that reads data from Notion databases.
Use populate_databases.py to seed databases with demo data first.
"""

import os
from app import create_app

# Create Flask application
app = create_app()

if __name__ == '__main__':
    # Development server (not used in production - Gunicorn handles this)
    port = int(os.getenv('PORT', 8080))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    print(f"Synseer Vendor Database")
    print(f"Running on port {port}")
    print(f"Connects to Notion databases for live data")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )