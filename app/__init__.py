"""
Vendor Logistics Database
A Flask application for tracking, scoring, and visualizing component vendors.
"""

from flask import Flask, request
import structlog
import os
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Configure structured logging
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", key="timestamp"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer() if os.getenv('FLASK_ENV') == 'development' else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(30),  # INFO level
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

def create_app():
    """Application factory pattern for Flask app creation."""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['DEBUG'] = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    # CORS configuration (simple approach for development)
    @app.after_request
    def after_request(response):
        allowed_origins = os.getenv('ALLOWED_ORIGINS', 'http://localhost:5000').split(',')
        origin = request.headers.get('Origin')
        if origin in allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        return response
    
    # Register blueprints
    from .api import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Register main routes
    from . import routes
    app.register_blueprint(routes.main_bp)
    
    logger.info("Flask application created successfully")
    return app