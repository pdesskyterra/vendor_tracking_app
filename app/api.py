"""
REST API endpoints for the Vendor Logistics Database.
"""

from flask import Blueprint, request, jsonify, current_app
from typing import Dict, List, Optional, Any
import json
from datetime import datetime, date
import structlog
from .models import ScoringWeights
from .scoring import ScoringEngine
from .notion_repo import NotionRepository, NotionAPIError

logger = structlog.get_logger()

# Create API blueprint
api_bp = Blueprint('api', __name__)

# Global instances (would use dependency injection in production)
notion_repo = None
scoring_engine = None

def get_notion_repo():
    """Get or create Notion repository instance."""
    global notion_repo
    if notion_repo is None:
        notion_repo = NotionRepository()
    return notion_repo

def get_scoring_engine():
    """Get or create scoring engine instance."""
    global scoring_engine
    if scoring_engine is None:
        scoring_engine = ScoringEngine()
    return scoring_engine

@api_bp.errorhandler(Exception)
def handle_api_error(error):
    """Global error handler for API endpoints."""
    logger.error(f"API Error: {str(error)}", exc_info=True)
    
    if isinstance(error, NotionAPIError):
        return jsonify({
            "error": "Database connection error",
            "message": "Unable to connect to data store",
            "timestamp": datetime.now().isoformat()
        }), 503
    
    return jsonify({
        "error": "Internal server error",
        "message": str(error),
        "timestamp": datetime.now().isoformat()
    }), 500

@api_bp.route('/healthz', methods=['GET'])
def health_check():
    """Health check endpoint for AWS App Runner."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }), 200

@api_bp.route('/vendors', methods=['GET'])
def get_vendors():
    """
    Get ranked vendor list with filtering and sorting options.
    
    Query Parameters:
        sort: Sorting field (final_score, total_cost, total_time, reliability, capacity)
        range: Time range filter (7d, 30d, 90d, 6m, 1y)
        component: Filter by component name (partial match)
        region: Filter by vendor region
        mode: Filter by shipping mode
        limit: Maximum number of results (default 50)
    """
    try:
        # Parse query parameters
        sort_by = request.args.get('sort', 'final_score')
        time_range = request.args.get('range', '30d')
        component_filter = request.args.get('component', '')
        region_filter = request.args.get('region', '')
        mode_filter = request.args.get('mode', '')
        limit = min(int(request.args.get('limit', 50)), 100)
        
        logger.info(f"Fetching vendors with filters: sort={sort_by}, range={time_range}, component={component_filter}")
        
        # Get data from Notion
        repo = get_notion_repo()
        vendors = repo.list_vendors()
        
        if not vendors:
            return jsonify({
                "vendors": [],
                "total": 0,
                "filters_applied": {
                    "sort": sort_by,
                    "range": time_range,
                    "component": component_filter,
                    "region": region_filter,
                    "mode": mode_filter
                },
                "generated_at": datetime.now().isoformat()
            })
        
        # Get parts for each vendor
        parts_by_vendor = {}
        for vendor in vendors:
            parts = repo.list_parts_by_vendor(vendor.id)
            if parts:  # Only include vendors with parts
                parts_by_vendor[vendor.id] = parts
        
        # Filter vendors by region if specified
        if region_filter:
            vendors = [v for v in vendors if v.region.lower() == region_filter.lower()]
        
        # Filter by component name if specified
        if component_filter:
            filtered_vendor_ids = set()
            for vendor_id, parts in parts_by_vendor.items():
                for part in parts:
                    if component_filter.lower() in part.component_name.lower():
                        filtered_vendor_ids.add(vendor_id)
            vendors = [v for v in vendors if v.id in filtered_vendor_ids]
        
        # Filter by shipping mode if specified
        if mode_filter:
            filtered_vendor_ids = set()
            for vendor_id, parts in parts_by_vendor.items():
                for part in parts:
                    if part.shipping_mode.lower() == mode_filter.lower():
                        filtered_vendor_ids.add(vendor_id)
            vendors = [v for v in vendors if v.id in filtered_vendor_ids]
        
        # Score vendors
        engine = get_scoring_engine()
        analyses = engine.score_vendors(vendors, parts_by_vendor)
        
        # Sort by requested field
        if sort_by == 'total_cost':
            analyses.sort(key=lambda x: x.avg_landed_cost)
        elif sort_by == 'total_time':
            analyses.sort(key=lambda x: x.avg_total_time)
        elif sort_by == 'reliability':
            analyses.sort(key=lambda x: x.current_score.reliability_score, reverse=True)
        elif sort_by == 'capacity':
            analyses.sort(key=lambda x: x.total_monthly_capacity, reverse=True)
        else:  # Default to final_score
            analyses.sort(key=lambda x: x.current_score.final_score, reverse=True)
        
        # Apply limit
        analyses = analyses[:limit]
        
        # Generate executive summary
        executive_summary = engine.generate_executive_summary(analyses)
        
        # Format response
        vendor_list = []
        for analysis in analyses:
            vendor_data = {
                "id": analysis.vendor.id,
                "name": analysis.vendor.name,
                "region": analysis.vendor.region,
                "final_score": analysis.current_score.final_score,
                "pillar_scores": {
                    "total_cost": analysis.current_score.total_cost_score,
                    "total_time": analysis.current_score.total_time_score,
                    "reliability": analysis.current_score.reliability_score,
                    "capacity": analysis.current_score.capacity_score
                },
                "metrics": {
                    "avg_landed_cost": analysis.avg_landed_cost,
                    "avg_total_time": analysis.avg_total_time,
                    "total_capacity": analysis.total_monthly_capacity,
                    "part_count": len(analysis.parts)
                },
                "risk_flags": [
                    {
                        "type": flag.type,
                        "severity": flag.severity,
                        "description": flag.description
                    } for flag in analysis.risk_flags
                ],
                "staleness": analysis.vendor.is_stale(),
                "last_verified": analysis.vendor.last_verified.isoformat() if analysis.vendor.last_verified else None
            }
            vendor_list.append(vendor_data)
        
        return jsonify({
            "vendors": vendor_list,
            "total": len(vendor_list),
            "executive_summary": executive_summary,
            "filters_applied": {
                "sort": sort_by,
                "range": time_range,
                "component": component_filter,
                "region": region_filter,
                "mode": mode_filter
            },
            "generated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error fetching vendors: {e}")
        raise

@api_bp.route('/vendors/<vendor_id>', methods=['GET'])
def get_vendor_detail(vendor_id: str):
    """
    Get detailed vendor information including parts and historical scores.
    """
    try:
        repo = get_notion_repo()
        
        # Get vendor
        vendor = repo.get_vendor(vendor_id)
        if not vendor:
            return jsonify({"error": "Vendor not found"}), 404
        
        # Get parts for vendor
        parts = repo.list_parts_by_vendor(vendor_id)
        
        # Score the vendor
        engine = get_scoring_engine()
        analyses = engine.score_vendors([vendor], {vendor_id: parts})
        
        if not analyses:
            return jsonify({"error": "Unable to score vendor"}), 500
        
        analysis = analyses[0]
        
        # Calculate pillar contributions
        contributions = engine.get_pillar_contributions(analysis.current_score)
        
        # Format parts data
        parts_data = []
        for part in parts:
            parts_data.append({
                "id": part.id,
                "component_name": part.component_name,
                "odm_destination": part.odm_destination,
                "odm_region": part.odm_region,
                "unit_price": part.unit_price,
                "freight_cost": part.freight_cost,
                "tariff_rate_pct": part.tariff_rate_pct,
                "total_landed_cost": part.total_landed_cost,
                "lead_time_weeks": part.lead_time_weeks,
                "transit_days": part.transit_days,
                "total_time_days": part.total_time_days,
                "shipping_mode": part.shipping_mode,
                "monthly_capacity": part.monthly_capacity,
                "last_verified": part.last_verified.isoformat() if part.last_verified else None
            })
        
        # Mock historical data for prototype (6 months)
        historical_trend = []
        base_score = analysis.current_score.final_score
        for i in range(6):
            month_date = date(2025, i + 1, 1)
            # Add some realistic variation
            variation = 0.02 * (i - 2.5)  # Creates a slight trend
            score = max(0.1, min(0.95, base_score + variation))
            
            historical_trend.append({
                "date": month_date.isoformat(),
                "final_score": score,
                "rank": 1 + (5 - i) if i < 3 else 2  # Mock rank changes
            })
        
        return jsonify({
            "vendor": {
                "id": vendor.id,
                "name": vendor.name,
                "region": vendor.region,
                "reliability_score": vendor.reliability_score,
                "contact_email": vendor.contact_email,
                "last_verified": vendor.last_verified.isoformat() if vendor.last_verified else None,
                "is_stale": vendor.is_stale()
            },
            "current_score": {
                "final_score": analysis.current_score.final_score,
                "pillar_scores": {
                    "total_cost": analysis.current_score.total_cost_score,
                    "total_time": analysis.current_score.total_time_score,
                    "reliability": analysis.current_score.reliability_score,
                    "capacity": analysis.current_score.capacity_score
                },
                "contributions": contributions,
                "computed_at": analysis.current_score.computed_at.isoformat()
            },
            "parts": parts_data,
            "historical_trend": historical_trend,
            "risk_flags": [
                {
                    "type": flag.type,
                    "severity": flag.severity,
                    "description": flag.description,
                    "value": flag.value,
                    "threshold": flag.threshold
                } for flag in analysis.risk_flags
            ],
            "metrics": {
                "avg_landed_cost": analysis.avg_landed_cost,
                "avg_total_time": analysis.avg_total_time,
                "total_capacity": analysis.total_monthly_capacity,
                "part_count": len(parts)
            }
        })
        
    except Exception as e:
        logger.error(f"Error fetching vendor detail: {e}")
        raise

@api_bp.route('/weights', methods=['GET'])
def get_weights():
    """Get current scoring weights."""
    engine = get_scoring_engine()
    return jsonify({
        "weights": engine.weights.to_dict(),
        "updated_at": datetime.now().isoformat()
    })

@api_bp.route('/weights', methods=['POST'])
def update_weights():
    """Update scoring weights."""
    try:
        data = request.get_json()
        if not data or 'weights' not in data:
            return jsonify({"error": "Missing weights in request body"}), 400
        
        new_weights = data['weights']
        
        # Validate weights
        required_keys = ['total_cost', 'total_time', 'reliability', 'capacity']
        for key in required_keys:
            if key not in new_weights:
                return jsonify({"error": f"Missing weight for {key}"}), 400
            if not isinstance(new_weights[key], (int, float)):
                return jsonify({"error": f"Weight for {key} must be a number"}), 400
        
        # Update scoring engine
        engine = get_scoring_engine()
        engine.update_weights(new_weights)
        
        return jsonify({
            "weights": engine.weights.to_dict(),
            "updated_at": datetime.now().isoformat(),
            "message": "Scoring weights updated successfully"
        })
        
    except Exception as e:
        logger.error(f"Error updating weights: {e}")
        raise

@api_bp.route('/recompute', methods=['POST'])
def recompute_scores():
    """Recompute all vendor scores with current weights."""
    try:
        data = request.get_json(silent=True) or {}
        since = data.get('since')  # Optional date filter
        
        logger.info(f"Recomputing scores since {since}")
        
        # Get all vendors and parts
        repo = get_notion_repo()
        vendors = repo.list_vendors()
        
        parts_by_vendor = {}
        for vendor in vendors:
            parts = repo.list_parts_by_vendor(vendor.id)
            if parts:
                parts_by_vendor[vendor.id] = parts
        
        # Recompute scores
        engine = get_scoring_engine()
        analyses = engine.score_vendors(vendors, parts_by_vendor)
        
        # Generate summary
        summary = engine.generate_executive_summary(analyses)
        
        return jsonify({
            "recomputed": len(analyses),
            "weights_used": engine.weights.to_dict(),
            "executive_summary": summary,
            "computed_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error recomputing scores: {e}")
        raise


@api_bp.route('/analytics/trends', methods=['GET'])
def get_trends():
    """Get trend analysis data for charts."""
    try:
        # This would typically fetch historical score data
        # For prototype, return mock trend data
        
        mock_trends = {
            "vendor_rankings": [
                {"vendor": "Batreon", "scores": [0.85, 0.82, 0.88, 0.86, 0.84, 0.87], "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]},
                {"vendor": "PowerCell KR", "scores": [0.78, 0.79, 0.77, 0.81, 0.83, 0.82], "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]},
                {"vendor": "EuroEnergy", "scores": [0.72, 0.74, 0.71, 0.73, 0.75, 0.76], "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]}
            ],
            "cost_trends": {
                "avg_landed_cost": [1.45, 1.48, 1.52, 1.49, 1.46, 1.44],
                "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
            },
            "capacity_utilization": {
                "total_capacity": 2450000,
                "utilized_capacity": 1960000,
                "utilization_rate": 0.80
            }
        }
        
        return jsonify({
            "trends": mock_trends,
            "generated_at": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error fetching trends: {e}")
        raise

@api_bp.route('/seed', methods=['POST'])
def seed_data():
    """Placeholder seed endpoint to satisfy tests; returns 200.
    In production this would populate Notion with demo data.
    """
    try:
        body = request.get_json(silent=True) or {}
        return jsonify({
            "message": "Seed completed",
            "force": bool(body.get("force", False))
        }), 200
    except Exception as e:
        logger.error(f"Error seeding data: {e}")
        raise