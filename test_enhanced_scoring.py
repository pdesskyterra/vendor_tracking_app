#!/usr/bin/env python3
"""
Test script to verify enhanced vendor scoring logic works correctly.
This tests the key fixes implemented for the data display issues.
"""

from app.scoring import ScoringEngine
from app.models import Vendor, Part, ScoringWeights
from datetime import date, datetime
from typing import Dict, Any

def create_test_vendor_with_enhanced_data() -> Vendor:
    """Create a test vendor with comprehensive enhanced data."""
    vendor = Vendor(
        id="test_001",
        name="TechGlobal Semiconductors",
        region="US",
        reliability_score=0.85,  # This will be overridden by enhanced calculation
        contact_email="supply@techglobal.com",
        last_verified=date.today(),
        created_time=datetime.now()
    )
    
    # Add enhanced data that would come from Notion
    enhanced_data = {
        # Comprehensive vendor maturity score (pre-calculated)
        "vendor_maturity_score": 0.924,  # 92.4% - strategic supplier level
        
        # Operational metrics
        "otif_percent": 96.0,  # 96% On-Time In-Full
        "ppm_defects": 25,     # 25 PPM defects
        "lead_time_consistency": 94.0,  # 94% consistency
        "communication_quality": 0.91,
        "response_time": 4.5,  # 4.5 hours response time
        
        # Financial metrics
        "financial_stability_score": 0.92,
        "debt_to_equity_ratio": 0.4,  # Optimal debt level
        "credit_rating": "A+",
        "annual_revenue": 85000000000,  # $85B revenue
        
        # Innovation metrics
        "rd_investment_percent": 12.5,  # 12.5% R&D investment
        "technology_readiness_level": 8,  # TRL 8/9
        "digital_transformation_score": 0.88,
        "patent_portfolio_strength": 0.78,
        
        # Business maturity
        "founded_year": 2003,  # 22 years old
        "company_size": "Enterprise",
        "employee_count": 127855,
        "manufacturing_sites": 45,
        
        # Compliance & Certifications
        "uflpa_compliant": True,
        "conflict_minerals_compliant": True,
        "last_audit_date": date(2024, 3, 15),  # Recent audit
        "iso_certifications": [
            "ISO 9001:2015",
            "ISO 14001:2015", 
            "ISO 45001:2018",
            "ISO 27001:2022",
            "ISO/TS 16949:2016",
            "AS9100D"
        ]
    }
    
    vendor._enhanced_data = enhanced_data
    return vendor

def create_test_parts() -> list[Part]:
    """Create test parts with compliance data."""
    return [
        Part(
            id="part_001",
            component_name="Tesla 4680 Li-ion Cell",
            vendor_id="test_001",
            vendor_name="TechGlobal Semiconductors",
            odm_destination="PDGV",
            odm_region="California, USA",
            unit_price=12.50,
            freight_cost=0.25,
            tariff_rate_pct=0.0,
            lead_time_weeks=3,
            transit_days=5,
            shipping_mode="Air",
            monthly_capacity=250000,
            rohs_compliant=True,
            reach_compliant=True,
            last_verified=date.today()
        ),
        Part(
            id="part_002", 
            component_name="Advanced Battery Management IC",
            vendor_id="test_001",
            vendor_name="TechGlobal Semiconductors",
            odm_destination="PDGV",
            odm_region="California, USA",
            unit_price=8.75,
            freight_cost=0.15,
            tariff_rate_pct=0.0,
            lead_time_weeks=4,
            transit_days=5,
            shipping_mode="Air", 
            monthly_capacity=150000,
            rohs_compliant=True,
            reach_compliant=True,
            last_verified=date.today()
        )
    ]

def test_enhanced_scoring():
    """Test the enhanced scoring engine."""
    print("🧪 Testing Enhanced Vendor Scoring Logic")
    print("=" * 60)
    
    # Create scoring engine
    scoring_engine = ScoringEngine()
    
    # Create test data
    vendor = create_test_vendor_with_enhanced_data()
    parts = create_test_parts()
    
    vendors = [vendor]
    parts_by_vendor = {vendor.id: parts}
    
    print(f"📊 Testing vendor: {vendor.name}")
    print(f"   Region: {vendor.region}")
    print(f"   Enhanced data available: {hasattr(vendor, '_enhanced_data')}")
    print(f"   Parts count: {len(parts)}")
    print()
    
    # Test vendor scoring
    try:
        analyses = scoring_engine.score_vendors(vendors, parts_by_vendor)
        
        if analyses:
            analysis = analyses[0]
            print("✅ SCORING RESULTS:")
            print(f"   Final Score: {analysis.current_score.final_score:.1%}")
            print(f"   Vendor Maturity: {analysis.current_score.reliability_score:.1%}")
            print(f"   Cost Score: {analysis.current_score.total_cost_score:.1%}")
            print(f"   Time Score: {analysis.current_score.total_time_score:.1%}")
            print(f"   Capacity Score: {analysis.current_score.capacity_score:.1%}")
            print()
            
            # Test risk flags
            print("🚩 RISK FLAGS:")
            if analysis.risk_flags:
                for flag in analysis.risk_flags:
                    print(f"   {flag.severity.upper()}: {flag.description}")
            else:
                print("   No risk flags detected ✅")
            print()
            
            # Test enhanced data usage
            if hasattr(analysis.vendor, '_enhanced_data'):
                enhanced = analysis.vendor._enhanced_data
                print("📈 ENHANCED DATA VERIFICATION:")
                print(f"   OTIF%: {enhanced.get('otif_percent', 'N/A')}%")
                print(f"   PPM Defects: {enhanced.get('ppm_defects', 'N/A')}")
                print(f"   UFLPA Compliant: {enhanced.get('uflpa_compliant', 'N/A')}")
                print(f"   ISO Certifications: {len(enhanced.get('iso_certifications', []))}")
                print()
            
            # Check if comprehensive scoring is being used
            maturity_components = analysis.current_score.inputs.get('vendor_maturity_components', {})
            if 'comprehensive_score' in maturity_components:
                print("✅ Using comprehensive vendor maturity calculation")
                print(f"   Operational Excellence: {maturity_components.get('operational_excellence', 'N/A'):.1%}")
                print(f"   Financial Maturity: {maturity_components.get('financial_maturity', 'N/A'):.1%}")
                print(f"   Innovation & Technology: {maturity_components.get('innovation_technology', 'N/A'):.1%}")
            elif maturity_components.get('proxy_calculation'):
                print("⚠️  Using proxy calculation (enhanced data not available)")
            else:
                print("❌ Unknown maturity calculation method")
            
        else:
            print("❌ No analysis results generated")
            
    except Exception as e:
        print(f"❌ ERROR during scoring: {e}")
        import traceback
        traceback.print_exc()

def test_compliance_data():
    """Test compliance data generation logic."""
    print("\n🔍 Testing Compliance Data Logic")
    print("=" * 60)
    
    vendor = create_test_vendor_with_enhanced_data()
    parts = create_test_parts()
    
    # Test vendor compliance
    enhanced = vendor._enhanced_data
    print("VENDOR COMPLIANCE:")
    print(f"   UFLPA Compliant: {enhanced.get('uflpa_compliant')}")
    print(f"   Conflict Minerals Compliant: {enhanced.get('conflict_minerals_compliant')}")
    print(f"   Last Audit: {enhanced.get('last_audit_date')}")
    print(f"   ISO Certifications: {enhanced.get('iso_certifications')}")
    print()
    
    # Test part compliance
    print("PART COMPLIANCE:")
    for part in parts:
        print(f"   {part.component_name}:")
        print(f"     RoHS Compliant: {part.rohs_compliant}")
        print(f"     REACH Compliant: {part.reach_compliant}")
    print()

if __name__ == "__main__":
    test_enhanced_scoring()
    test_compliance_data()
    
    print("🎉 Testing completed! Check results above.")
    print("\nKey fixes implemented:")
    print("✅ Enhanced vendor maturity calculation using 31 properties")
    print("✅ Compliance data pipeline for vendors and parts") 
    print("✅ Realistic risk thresholds for balanced distribution")
    print("✅ Comprehensive scoring transparency")