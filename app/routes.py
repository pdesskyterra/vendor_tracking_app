"""
Main web routes for the Synseer Vendor Logistics Database.
Serves the SPA and handles browser navigation.
"""

from flask import Blueprint, render_template, send_from_directory, current_app
import os

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Serve the main SPA page."""
    return render_template('index.html')

@main_bp.route('/vendors')
@main_bp.route('/vendors/<vendor_id>')
def vendors_page(vendor_id=None):
    """Serve the vendors page (SPA handles routing)."""
    return render_template('index.html')

@main_bp.route('/analytics')
def analytics_page():
    """Serve the analytics page (SPA handles routing)."""
    return render_template('index.html')

@main_bp.route('/favicon.ico')
def favicon():
    """Serve favicon."""
    return send_from_directory(
        os.path.join(current_app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )