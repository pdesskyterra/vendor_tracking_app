"""
Test suite for the Synseer Vendor Scoring Engine.
Tests the scoring methodology and risk detection logic.
"""

import pytest
from datetime import date, datetime, timedelta
from app.models import Vendor, Part, ScoringWeights
from app.scoring import ScoringEngine

class TestScoringEngine:
    """Test cases for the ScoringEngine class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ScoringEngine()
        
        # Create test vendors
        self.vendors = [
            Vendor(
                id="vendor_1",
                name="Test Vendor A",
                region="US",
                reliability_score=0.85,
                last_verified=date.today()
            ),
            Vendor(
                id="vendor_2", 
                name="Test Vendor B",
                region="CN",
                reliability_score=0.75,
                last_verified=date.today() - timedelta(days=45)  # Stale data
            )
        ]
        
        # Create test parts
        self.parts_by_vendor = {
            "vendor_1": [
                Part(
                    id="part_1",
                    component_name="Li-ion cell 18650",
                    vendor_id="vendor_1",
                    unit_price=2.50,
                    freight_cost=0.15,
                    tariff_rate_pct=6.5,
                    lead_time_weeks=4,
                    transit_days=5,
                    shipping_mode="Air",
                    monthly_capacity=50000,
                    last_verified=date.today()
                )
            ],
            "vendor_2": [
                Part(
                    id="part_2",
                    component_name="Li-ion cell 21700",
                    vendor_id="vendor_2",
                    unit_price=1.80,
                    freight_cost=0.25,
                    tariff_rate_pct=10.0,
                    lead_time_weeks=6,
                    transit_days=14,
                    shipping_mode="Ocean",
                    monthly_capacity=100000,
                    last_verified=date.today() - timedelta(days=45)
                )
            ]
        }
    
    def test_score_calculation(self):
        """Test basic score calculation."""
        analyses = self.engine.score_vendors(self.vendors, self.parts_by_vendor)
        
        assert len(analyses) == 2
        
        # Check that scores are normalized (0-1 range)
        for analysis in analyses:
            score = analysis.current_score
            assert 0 <= score.total_cost_score <= 1
            assert 0 <= score.total_time_score <= 1
            assert 0 <= score.reliability_score <= 1
            assert 0 <= score.capacity_score <= 1
            assert 0 <= score.final_score <= 1
    
    def test_scoring_weights(self):
        """Test that scoring weights are applied correctly."""
        custom_weights = ScoringWeights(
            total_cost=0.6,
            total_time=0.2,
            reliability=0.1,
            capacity=0.1
        )
        
        engine = ScoringEngine(custom_weights)
        analyses = engine.score_vendors(self.vendors, self.parts_by_vendor)
        
        # Verify weights are used in calculation
        for analysis in analyses:
            score = analysis.current_score
            weights = score.weights
            
            assert abs(weights['total_cost'] - 0.6) < 0.01
            assert abs(weights['total_time'] - 0.2) < 0.01
            assert abs(weights['reliability'] - 0.1) < 0.01
            assert abs(weights['capacity'] - 0.1) < 0.01
    
    def test_landed_cost_calculation(self):
        """Test total landed cost calculation."""
        part = self.parts_by_vendor["vendor_1"][0]
        
        expected_tariff = part.unit_price * (part.tariff_rate_pct / 100)
        expected_total = part.unit_price + part.freight_cost + expected_tariff
        
        assert abs(part.total_landed_cost - expected_total) < 0.01
    
    def test_risk_flag_generation(self):
        """Test risk flag detection."""
        analyses = self.engine.score_vendors(self.vendors, self.parts_by_vendor)
        
        # Vendor 2 should have stale data flag
        vendor_2_analysis = next(a for a in analyses if a.vendor.id == "vendor_2")
        
        stale_flags = [f for f in vendor_2_analysis.risk_flags if f.type == "stale_data"]
        assert len(stale_flags) > 0
        assert stale_flags[0].severity in ["medium", "high"]
    
    def test_score_ranking(self):
        """Test that vendors are properly ranked by final score."""
        analyses = self.engine.score_vendors(self.vendors, self.parts_by_vendor)
        
        # Scores should be in descending order
        for i in range(len(analyses) - 1):
            current_score = analyses[i].current_score.final_score
            next_score = analyses[i + 1].current_score.final_score
            assert current_score >= next_score
    
    def test_normalization_with_identical_values(self):
        """Test normalization when all values are identical."""
        # Create vendors with identical metrics
        identical_parts = {
            "vendor_1": [Part(
                id="part_1",
                component_name="Test",
                vendor_id="vendor_1", 
                unit_price=2.00,
                freight_cost=0.10,
                tariff_rate_pct=5.0,
                lead_time_weeks=4,
                transit_days=7,
                monthly_capacity=50000,
                last_verified=date.today()
            )],
            "vendor_2": [Part(
                id="part_2",
                component_name="Test",
                vendor_id="vendor_2",
                unit_price=2.00,
                freight_cost=0.10, 
                tariff_rate_pct=5.0,
                lead_time_weeks=4,
                transit_days=7,
                monthly_capacity=50000,
                last_verified=date.today()
            )]
        }
        
        analyses = self.engine.score_vendors(self.vendors, identical_parts)
        
        # When metrics are identical, cost/time/capacity scores should be 0.5
        # Only reliability should differ based on vendor.reliability_score
        for analysis in analyses:
            score = analysis.current_score
            assert abs(score.total_cost_score - 0.5) < 0.01
            assert abs(score.total_time_score - 0.5) < 0.01
            assert abs(score.capacity_score - 0.5) < 0.01
    
    def test_executive_summary_generation(self):
        """Test executive summary generation."""
        analyses = self.engine.score_vendors(self.vendors, self.parts_by_vendor)
        summary = self.engine.generate_executive_summary(analyses)
        
        assert "summary" in summary
        assert "recommendation" in summary
        assert len(summary["summary"]) > 0
        assert len(summary["recommendation"]) > 0
    
    def test_pillar_contributions(self):
        """Test pillar contribution calculation."""
        analyses = self.engine.score_vendors(self.vendors, self.parts_by_vendor)
        
        for analysis in analyses:
            contributions = self.engine.get_pillar_contributions(analysis.current_score)
            
            # All contributions should sum to approximately final score
            total_contribution = sum(contributions.values())
            assert abs(total_contribution - analysis.current_score.final_score) < 0.01
            
            # Each contribution should be non-negative
            for contribution in contributions.values():
                assert contribution >= 0
    
    def test_weight_update(self):
        """Test weight updating functionality."""
        new_weights = {
            'total_cost': 0.5,
            'total_time': 0.25,
            'reliability': 0.15,
            'capacity': 0.1
        }
        
        self.engine.update_weights(new_weights)
        
        # Check weights were updated and normalized
        assert abs(self.engine.weights.total_cost - 0.5) < 0.01
        assert abs(self.engine.weights.total_time - 0.25) < 0.01
        assert abs(self.engine.weights.reliability - 0.15) < 0.01
        assert abs(self.engine.weights.capacity - 0.1) < 0.01
    
    def test_empty_vendor_list(self):
        """Test handling of empty vendor list."""
        analyses = self.engine.score_vendors([], {})
        assert len(analyses) == 0
        
        summary = self.engine.generate_executive_summary(analyses)
        assert "No vendor data available" in summary["summary"]
    
    def test_vendor_without_parts(self):
        """Test handling of vendor without parts."""
        vendor_no_parts = Vendor(
            id="vendor_3",
            name="No Parts Vendor",
            region="EU",
            reliability_score=0.80,
            last_verified=date.today()
        )
        
        vendors_with_empty = self.vendors + [vendor_no_parts]
        parts_with_empty = dict(self.parts_by_vendor)
        parts_with_empty["vendor_3"] = []
        
        analyses = self.engine.score_vendors(vendors_with_empty, parts_with_empty)
        
        # Should only score vendors with parts
        assert len(analyses) == 2  # Only vendors with parts
        vendor_ids = [a.vendor.id for a in analyses]
        assert "vendor_3" not in vendor_ids


class TestScoringWeights:
    """Test cases for ScoringWeights model."""
    
    def test_weight_normalization(self):
        """Test that weights are normalized to sum to 1.0."""
        weights = ScoringWeights(
            total_cost=0.8,
            total_time=0.6,
            reliability=0.4,
            capacity=0.2
        )
        
        weights.normalize()
        
        total = weights.total_cost + weights.total_time + weights.reliability + weights.capacity
        assert abs(total - 1.0) < 0.001
    
    def test_weight_to_dict(self):
        """Test weight conversion to dictionary."""
        weights = ScoringWeights()
        weight_dict = weights.to_dict()
        
        expected_keys = ['total_cost', 'total_time', 'reliability', 'capacity']
        assert all(key in weight_dict for key in expected_keys)
        
        # Default weights should sum to 1.0
        assert abs(sum(weight_dict.values()) - 1.0) < 0.001


if __name__ == '__main__':
    pytest.main([__file__, '-v'])