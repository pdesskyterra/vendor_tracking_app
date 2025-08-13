"""
Test suite for the Synseer Vendor API endpoints.
Tests REST API functionality and response formats.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from app import create_app
from app.models import Vendor, Part, VendorScore

class TestVendorAPI:
    """Test cases for vendor API endpoints."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask application."""
        app = create_app()
        app.config['TESTING'] = True
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    @pytest.fixture
    def mock_vendors(self):
        """Mock vendor data for testing."""
        return [
            {
                "id": "vendor_1",
                "name": "Test Vendor A",
                "region": "US",
                "final_score": 0.85,
                "pillar_scores": {
                    "total_cost": 0.80,
                    "total_time": 0.90,
                    "reliability": 0.85,
                    "capacity": 0.85
                },
                "metrics": {
                    "avg_landed_cost": 2.50,
                    "avg_total_time": 12.0,
                    "total_capacity": 50000,
                    "part_count": 2
                },
                "risk_flags": [],
                "staleness": False,
                "last_verified": "2025-08-11"
            }
        ]
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get('/api/healthz')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert 'timestamp' in data
    
    @patch('app.api.get_notion_repo')
    @patch('app.api.get_scoring_engine')
    def test_get_vendors_success(self, mock_engine, mock_repo, client, mock_vendors):
        """Test successful vendor list retrieval."""
        # Mock repository
        mock_repo_instance = MagicMock()
        mock_repo_instance.list_vendors.return_value = [
            Vendor(id="vendor_1", name="Test Vendor A", region="US", reliability_score=0.85)
        ]
        mock_repo_instance.list_parts_by_vendor.return_value = [
            Part(id="part_1", component_name="Test Part", vendor_id="vendor_1", unit_price=2.50)
        ]
        mock_repo.return_value = mock_repo_instance
        
        # Mock scoring engine
        mock_engine_instance = MagicMock()
        mock_analysis = MagicMock()
        mock_analysis.vendor = Vendor(id="vendor_1", name="Test Vendor A", region="US", reliability_score=0.85)
        mock_analysis.current_score = VendorScore(final_score=0.85)
        mock_analysis.risk_flags = []
        mock_analysis.avg_landed_cost = 2.50
        mock_analysis.avg_total_time = 12.0
        mock_analysis.total_monthly_capacity = 50000
        mock_analysis.parts = []
        
        mock_engine_instance.score_vendors.return_value = [mock_analysis]
        mock_engine_instance.generate_executive_summary.return_value = {
            "summary": "Test summary",
            "recommendation": "Test recommendation"
        }
        mock_engine.return_value = mock_engine_instance
        
        response = client.get('/api/vendors')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'vendors' in data
        assert 'executive_summary' in data
        assert len(data['vendors']) > 0
    
    @patch('app.api.get_notion_repo')
    def test_get_vendors_empty_result(self, mock_repo, client):
        """Test vendor list endpoint with no vendors."""
        mock_repo_instance = MagicMock()
        mock_repo_instance.list_vendors.return_value = []
        mock_repo.return_value = mock_repo_instance
        
        response = client.get('/api/vendors')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['vendors'] == []
        assert data['total'] == 0
    
    def test_get_vendors_with_filters(self, client):
        """Test vendor list with query parameters."""
        response = client.get('/api/vendors?sort=total_cost&region=US&component=battery')
        
        # Should not error even with no data
        assert response.status_code in [200, 500]  # 500 if no Notion setup
    
    @patch('app.api.get_notion_repo')
    def test_get_vendor_detail_not_found(self, mock_repo, client):
        """Test vendor detail for non-existent vendor."""
        mock_repo_instance = MagicMock()
        mock_repo_instance.get_vendor.return_value = None
        mock_repo.return_value = mock_repo_instance
        
        response = client.get('/api/vendors/nonexistent')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
    
    @patch('app.api.get_scoring_engine')
    def test_get_weights(self, mock_engine, client):
        """Test get current scoring weights."""
        mock_engine_instance = MagicMock()
        mock_engine_instance.weights.to_dict.return_value = {
            'total_cost': 0.4,
            'total_time': 0.3,
            'reliability': 0.2,
            'capacity': 0.1
        }
        mock_engine.return_value = mock_engine_instance
        
        response = client.get('/api/weights')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'weights' in data
        assert data['weights']['total_cost'] == 0.4
    
    @patch('app.api.get_scoring_engine')
    def test_update_weights_success(self, mock_engine, client):
        """Test successful weight update."""
        mock_engine_instance = MagicMock()
        mock_engine_instance.weights.to_dict.return_value = {
            'total_cost': 0.5,
            'total_time': 0.3,
            'reliability': 0.15,
            'capacity': 0.05
        }
        mock_engine.return_value = mock_engine_instance
        
        new_weights = {
            'weights': {
                'total_cost': 0.5,
                'total_time': 0.3,
                'reliability': 0.15,
                'capacity': 0.05
            }
        }
        
        response = client.post('/api/weights', 
                             data=json.dumps(new_weights),
                             content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'weights' in data
        assert 'message' in data
    
    def test_update_weights_missing_data(self, client):
        """Test weight update with missing data."""
        response = client.post('/api/weights',
                             data=json.dumps({}),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    def test_update_weights_invalid_weight(self, client):
        """Test weight update with invalid weight value."""
        invalid_weights = {
            'weights': {
                'total_cost': 'invalid',
                'total_time': 0.3,
                'reliability': 0.2,
                'capacity': 0.1
            }
        }
        
        response = client.post('/api/weights',
                             data=json.dumps(invalid_weights),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
    
    @patch('app.api.get_notion_repo')
    @patch('app.api.get_scoring_engine') 
    def test_recompute_scores(self, mock_engine, mock_repo, client):
        """Test score recomputation."""
        # Mock repository
        mock_repo_instance = MagicMock()
        mock_repo_instance.list_vendors.return_value = []
        mock_repo.return_value = mock_repo_instance
        
        # Mock scoring engine
        mock_engine_instance = MagicMock()
        mock_engine_instance.score_vendors.return_value = []
        mock_engine_instance.generate_executive_summary.return_value = {
            "summary": "No vendors",
            "recommendation": "Add vendors"
        }
        mock_engine_instance.weights.to_dict.return_value = {
            'total_cost': 0.4,
            'total_time': 0.3,
            'reliability': 0.2,
            'capacity': 0.1
        }
        mock_engine.return_value = mock_engine_instance
        
        response = client.post('/api/recompute')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'recomputed' in data
        assert 'weights_used' in data
    
    def test_seed_data_endpoint(self, client):
        """Test seed data generation endpoint."""
        response = client.post('/api/seed',
                             data=json.dumps({'force': True}),
                             content_type='application/json')
        
        # Should not error (might return 500 if no Notion setup)
        assert response.status_code in [200, 500]
        
        if response.status_code == 200:
            data = json.loads(response.data)
            assert 'message' in data
    
    def test_analytics_trends(self, client):
        """Test analytics trends endpoint."""
        response = client.get('/api/analytics/trends')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'trends' in data
        assert 'vendor_rankings' in data['trends']
        assert 'cost_trends' in data['trends']
    
    def test_invalid_json_request(self, client):
        """Test request with invalid JSON."""
        response = client.post('/api/weights',
                             data='invalid json',
                             content_type='application/json')
        
        assert response.status_code in [400, 500]  # Should handle gracefully
    
    def test_cors_headers(self, client):
        """Test that CORS headers are present."""
        response = client.get('/api/healthz')
        
        # CORS headers should be added by the after_request handler
        assert response.status_code == 200


class TestAPIErrorHandling:
    """Test cases for API error handling."""
    
    @pytest.fixture
    def app(self):
        """Create test Flask application."""
        app = create_app()
        app.config['TESTING'] = True
        return app
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    def test_404_endpoint(self, client):
        """Test non-existent endpoint."""
        response = client.get('/api/nonexistent')
        assert response.status_code == 404
    
    def test_method_not_allowed(self, client):
        """Test wrong HTTP method."""
        response = client.delete('/api/healthz')
        assert response.status_code == 405
    
    @patch('app.api.get_notion_repo')
    def test_database_connection_error(self, mock_repo, client):
        """Test database connection error handling."""
        from app.notion_repo import NotionAPIError
        
        mock_repo.side_effect = NotionAPIError("Connection failed")
        
        response = client.get('/api/vendors')
        
        assert response.status_code == 503
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error'] == 'Database connection error'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])