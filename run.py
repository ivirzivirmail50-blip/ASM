#!/usr/bin/env python3
"""
Absolute Story Manager v4.0 - Main Entry Point
Run with: python run.py
"""
import os
import sys

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

app = create_app()

if __name__ == '__main__':
    print("=" * 60)
    print("Absolute Story Manager v4.0")
    print("=" * 60)
    print(f"Starting server at http://localhost:5000")
    print(f"Data directory: {app.instance_path}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=True)
