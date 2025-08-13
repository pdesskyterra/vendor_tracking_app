#!/usr/bin/env python3
"""
Standalone Notion Database Population Script for the Vendor Database
Populates Notion databases with realistic demo data for testing and development.

Usage:
    python populate_databases.py              # Normal population
    python populate_databases.py --force      # Force overwrite existing data
    python populate_databases.py --validate   # Only validate schemas
    python populate_databases.py --help       # Show help

Required Environment Variables:
    NOTION_API_KEY - Your Notion integration API key
    VENDORS_DB_ID - Vendors database ID
    PARTS_DB_ID - Parts database ID  
    SCORES_DB_ID - Scores database ID (optional, for validation)
"""

import os
import sys
import time
import argparse
import random
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, date, timedelta
from dataclasses import dataclass
from dotenv import load_dotenv
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@dataclass
class Vendor:
    """Vendor data model."""
    id: str
    name: str
    region: str
    reliability_score: float
    contact_email: Optional[str] = None
    last_verified: Optional[date] = None
    created_time: Optional[datetime] = None


@dataclass
class Part:
    """Part/component data model."""
    id: str
    component_name: str
    vendor_id: str
    vendor_name: str
    odm_destination: str
    odm_region: str
    unit_price: float
    freight_cost: float
    tariff_rate_pct: float
    lead_time_weeks: int
    transit_days: int
    shipping_mode: str
    monthly_capacity: int
    rohs_compliant: bool = False  # RoHS (Restriction of Hazardous Substances) compliance
    reach_compliant: bool = False  # REACH (Registration, Evaluation, Authorization of Chemicals) compliance
    last_verified: Optional[date] = None
    timestamp: Optional[datetime] = None
    notes: str = ""


def generate_demo_data() -> Tuple[List[Vendor], List[Part]]:
    """Generate realistic vendor and part demo data with comprehensive properties."""
    
    # Enhanced vendor templates with strategic positioning and comprehensive metrics
    vendor_templates = [
        # Strategic Partners (High Kraljic positioning - premium suppliers)
        {
            "name": "Tesla Energy Systems", "region": "US", "archetype": "strategic",
            "email": "supply@tesla.com", 
            "annual_revenue": 85000000000, "employee_count": 127855, "founded_year": 2003,
            "company_size": "Enterprise", "market_presence": "Global Leader",
            "credit_rating": "A+", "manufacturing_sites": 45
        },
        {
            "name": "Samsung SDI Europe", "region": "EU", "archetype": "strategic", 
            "email": "partnerships@samsungsdi.com",
            "annual_revenue": 15200000000, "employee_count": 25400, "founded_year": 1970,
            "company_size": "Enterprise", "market_presence": "Global Leader", 
            "credit_rating": "A+", "manufacturing_sites": 18
        },
        {
            "name": "CATL Innovation", "region": "CN", "archetype": "strategic",
            "email": "global@catl.com",
            "annual_revenue": 32400000000, "employee_count": 75000, "founded_year": 2011,
            "company_size": "Enterprise", "market_presence": "Global Leader",
            "credit_rating": "A", "manufacturing_sites": 25
        },
        
        # Leverage Suppliers (High spend, lower risk - competitive market)
        {
            "name": "LG Energy Solution", "region": "KR", "archetype": "leverage",
            "email": "sourcing@lgensol.com",
            "annual_revenue": 22800000000, "employee_count": 42000, "founded_year": 2020,
            "company_size": "Large", "market_presence": "Regional Leader",
            "credit_rating": "A", "manufacturing_sites": 22
        },
        {
            "name": "Panasonic Industry", "region": "CN", "archetype": "leverage",
            "email": "b2b@panasonic.cn", 
            "annual_revenue": 18500000000, "employee_count": 38500, "founded_year": 1980,
            "company_size": "Large", "market_presence": "Regional Leader",
            "credit_rating": "A", "manufacturing_sites": 16
        },
        {
            "name": "BYD Components", "region": "CN", "archetype": "leverage",
            "email": "oem@byd.com",
            "annual_revenue": 35600000000, "employee_count": 295000, "founded_year": 1995,
            "company_size": "Enterprise", "market_presence": "Regional Leader",
            "credit_rating": "BBB", "manufacturing_sites": 35
        },
        {
            "name": "Northvolt Systems", "region": "EU", "archetype": "leverage",
            "email": "procurement@northvolt.com",
            "annual_revenue": 1200000000, "employee_count": 6500, "founded_year": 2016,
            "company_size": "Medium", "market_presence": "Regional Player",
            "credit_rating": "BBB", "manufacturing_sites": 4
        },
        
        # Bottleneck Suppliers (Low spend, high risk - specialized/constrained)
        {
            "name": "Rare Earth Dynamics", "region": "US", "archetype": "bottleneck",
            "email": "sales@redynamics.com",
            "annual_revenue": 185000000, "employee_count": 1250, "founded_year": 2008,
            "company_size": "Medium", "market_presence": "Niche Specialist",
            "credit_rating": "BB", "manufacturing_sites": 3
        },
        {
            "name": "Nordic Magnetics", "region": "EU", "archetype": "bottleneck",
            "email": "export@nordicmag.se",
            "annual_revenue": 95000000, "employee_count": 485, "founded_year": 1995,
            "company_size": "Small", "market_presence": "Niche Specialist",
            "credit_rating": "BB", "manufacturing_sites": 2
        },
        {
            "name": "Baotou Rare Metals", "region": "CN", "archetype": "bottleneck",
            "email": "global@baotourare.cn",
            "annual_revenue": 420000000, "employee_count": 2800, "founded_year": 1988,
            "company_size": "Medium", "market_presence": "Regional Player",
            "credit_rating": "B", "manufacturing_sites": 5
        },
        {
            "name": "Vietnam Specialty Alloys", "region": "VN", "archetype": "bottleneck",
            "email": "supply@vnalloys.vn",
            "annual_revenue": 65000000, "employee_count": 890, "founded_year": 2012,
            "company_size": "Small", "market_presence": "Local Player",
            "credit_rating": "B", "manufacturing_sites": 2
        },
        
        # Routine Suppliers (Low spend, low risk - commodity suppliers)
        {
            "name": "Standard Components Inc", "region": "US", "archetype": "routine",
            "email": "orders@standardcomp.com",
            "annual_revenue": 125000000, "employee_count": 650, "founded_year": 1985,
            "company_size": "Medium", "market_presence": "Regional Player",
            "credit_rating": "BBB", "manufacturing_sites": 4
        },
        {
            "name": "Global Connectors Ltd", "region": "MX", "archetype": "routine",
            "email": "sales@globalconn.mx",
            "annual_revenue": 85000000, "employee_count": 1200, "founded_year": 1998,
            "company_size": "Medium", "market_presence": "Regional Player", 
            "credit_rating": "BB", "manufacturing_sites": 6
        },
        {
            "name": "Shenzhen Basic Tech", "region": "CN", "archetype": "routine",
            "email": "export@szbasic.cn",
            "annual_revenue": 58000000, "employee_count": 2400, "founded_year": 2005,
            "company_size": "Medium", "market_presence": "Regional Player",
            "credit_rating": "BB", "manufacturing_sites": 8
        },
        {
            "name": "Prague Electronics", "region": "EU", "archetype": "routine",
            "email": "b2b@pragueelectronics.cz",
            "annual_revenue": 42000000, "employee_count": 380, "founded_year": 1992,
            "company_size": "Small", "market_presence": "Local Player",
            "credit_rating": "BBB", "manufacturing_sites": 2
        },
        {
            "name": "Mumbai Circuit Systems", "region": "IN", "archetype": "routine",
            "email": "export@mumbaicircuits.in",
            "annual_revenue": 28000000, "employee_count": 1850, "founded_year": 2001,
            "company_size": "Medium", "market_presence": "Local Player",
            "credit_rating": "B", "manufacturing_sites": 5
        },
        {
            "name": "Delhi Sensor Works", "region": "IN", "archetype": "routine",
            "email": "sales@delhisensors.in",
            "annual_revenue": 15000000, "employee_count": 750, "founded_year": 2008,
            "company_size": "Small", "market_presence": "Local Player",
            "credit_rating": "B", "manufacturing_sites": 3
        },
        
        # Additional suppliers for scale and variety
        {
            "name": "Korean Advanced Materials", "region": "KR", "archetype": "leverage",
            "email": "global@kamaterials.kr",
            "annual_revenue": 850000000, "employee_count": 4200, "founded_year": 1978,
            "company_size": "Large", "market_presence": "Regional Leader",
            "credit_rating": "A", "manufacturing_sites": 8
        },
        {
            "name": "Vietnam Tech Assembly", "region": "VN", "archetype": "routine", 
            "email": "assembly@vntech.vn",
            "annual_revenue": 32000000, "employee_count": 1650, "founded_year": 2015,
            "company_size": "Medium", "market_presence": "Local Player",
            "credit_rating": "BB", "manufacturing_sites": 4
        },
        {
            "name": "Guadalajara Components", "region": "MX", "archetype": "routine",
            "email": "export@gdlcomponents.mx", 
            "annual_revenue": 48000000, "employee_count": 980, "founded_year": 2003,
            "company_size": "Medium", "market_presence": "Local Player",
            "credit_rating": "BB", "manufacturing_sites": 3
        },
        {
            "name": "Alpine Precision", "region": "EU", "archetype": "bottleneck",
            "email": "precision@alpine.at",
            "annual_revenue": 125000000, "employee_count": 650, "founded_year": 1987,
            "company_size": "Medium", "market_presence": "Niche Specialist", 
            "credit_rating": "BBB", "manufacturing_sites": 3
        }
    ]
    
    # Generate comprehensive vendor data with realistic correlations
    vendors = []
    base_date = date(2025, 6, 1)
    
    # Regional risk and economic factors
    regional_factors = {
        "US": {"country_risk": 0.05, "currency_stability": 0.02, "trade_relations": 0.03, "regulatory_compliance": 0.95},
        "EU": {"country_risk": 0.06, "currency_stability": 0.04, "trade_relations": 0.02, "regulatory_compliance": 0.97},
        "KR": {"country_risk": 0.12, "currency_stability": 0.08, "trade_relations": 0.05, "regulatory_compliance": 0.92},
        "CN": {"country_risk": 0.25, "currency_stability": 0.15, "trade_relations": 0.18, "regulatory_compliance": 0.85},
        "MX": {"country_risk": 0.18, "currency_stability": 0.12, "trade_relations": 0.08, "regulatory_compliance": 0.88},
        "VN": {"country_risk": 0.35, "currency_stability": 0.22, "trade_relations": 0.12, "regulatory_compliance": 0.78},
        "IN": {"country_risk": 0.28, "currency_stability": 0.18, "trade_relations": 0.15, "regulatory_compliance": 0.82}
    }
    
    for i, template in enumerate(vendor_templates):
        # Data verification patterns based on archetype
        archetype = template["archetype"]
        if archetype == "strategic":
            days_ago = random.randint(1, 15)  # Recent data for strategic suppliers
        elif archetype == "leverage": 
            days_ago = random.randint(5, 30)  # Moderate freshness for leverage
        elif archetype == "bottleneck":
            days_ago = random.randint(15, 60)  # Less frequent updates for niche suppliers
        else:  # routine
            days_ago = random.randint(30, 120)  # Stale data for routine suppliers
        
        # Generate base metrics independently, then derive reliability from operational performance
        region_factors = regional_factors[template["region"]]
        company_age = 2025 - template["founded_year"]
        
        # Financial metrics (correlated with company size and regional stability)
        revenue = template["annual_revenue"] * random.uniform(0.85, 1.15)
        
        # Debt-to-equity based on region and company size
        if template["company_size"] == "Enterprise":
            debt_to_equity = random.uniform(0.2, 0.8)
        elif template["company_size"] == "Large": 
            debt_to_equity = random.uniform(0.3, 1.2)
        else:
            debt_to_equity = random.uniform(0.5, 2.0)
            
        # Financial stability based on regional risk and company fundamentals
        base_financial_stability = 1.0 - region_factors["country_risk"]
        if template["company_size"] == "Enterprise":
            base_financial_stability += 0.1
        elif template["company_size"] == "Large":
            base_financial_stability += 0.05
            
        financial_stability = min(0.98, max(0.3, base_financial_stability + random.uniform(-0.15, 0.1)))
        
        # Operational metrics based on archetype and company maturity
        employee_count = template["employee_count"] * random.randint(85, 115) // 100
        
        # OTIF % based on archetype and operational maturity
        if archetype == "strategic":
            otif_percent = random.uniform(92.0, 99.0)
        elif archetype == "leverage":
            otif_percent = random.uniform(88.0, 96.0)
        elif archetype == "bottleneck":
            otif_percent = random.uniform(75.0, 92.0)  # Can be inconsistent due to specialization
        else:  # routine
            otif_percent = random.uniform(85.0, 94.0)
            
        # PPM defects inversely related to company size and archetype
        if archetype == "strategic":
            ppm_defects = random.randint(5, 50)
        elif archetype == "leverage": 
            ppm_defects = random.randint(20, 150)
        elif archetype == "bottleneck":
            ppm_defects = random.randint(50, 300)  # Higher due to complexity
        else:  # routine
            ppm_defects = random.randint(100, 500)
        
        # Lead time consistency based on operational maturity
        company_maturity_factor = min(1.0, company_age / 25.0)  # Mature at 25+ years
        size_bonus = {"Enterprise": 8.0, "Large": 5.0, "Medium": 2.0, "Small": 0.0}[template["company_size"]]
        lead_time_consistency = min(98.0, max(65.0, 75.0 + company_maturity_factor * 15.0 + size_bonus + random.uniform(-8, 5)))
        
        # Response time based on region and company size  
        base_response = 24 if template["company_size"] == "Enterprise" else 48
        response_time = base_response * random.uniform(0.5, 2.5)
        
        # R&D investment based on archetype and company size
        if archetype == "strategic":
            rd_investment = random.uniform(8.0, 18.0)
            tech_readiness = random.randint(7, 9)
            digital_transformation = random.uniform(0.8, 0.95)
        elif archetype == "leverage":
            rd_investment = random.uniform(4.0, 12.0) 
            tech_readiness = random.randint(6, 8)
            digital_transformation = random.uniform(0.6, 0.85)
        elif archetype == "bottleneck":
            rd_investment = random.uniform(12.0, 25.0)  # High R&D for specialized tech
            tech_readiness = random.randint(6, 9)
            digital_transformation = random.uniform(0.4, 0.75)
        else:  # routine
            rd_investment = random.uniform(1.0, 6.0)
            tech_readiness = random.randint(4, 7) 
            digital_transformation = random.uniform(0.3, 0.65)
            
        # Patent portfolio strength based on R&D investment and company maturity
        patent_strength = min(0.95, max(0.1, (rd_investment / 20.0) * company_maturity_factor * random.uniform(0.7, 1.4)))
        
        # Communication quality based on company size and digital transformation
        comm_base = {"Enterprise": 0.85, "Large": 0.75, "Medium": 0.65, "Small": 0.55}[template["company_size"]]
        communication_quality = min(0.98, max(0.4, comm_base + digital_transformation * 0.15 + random.uniform(-0.1, 0.1)))
        
        # Continuous improvement based on R&D investment and operational metrics
        continuous_improvement = min(0.95, max(0.3, (rd_investment / 25.0) + (otif_percent / 200.0) + random.uniform(-0.1, 0.15)))
        
        # Supply chain resilience based on financial stability and regional factors
        supply_chain_resilience = min(0.95, max(0.3, financial_stability * 0.6 + (1 - region_factors["country_risk"]) * 0.4))
        
        # Innovation partnership potential
        partnership_potential = min(0.9, max(0.2, (rd_investment / 25.0) + (financial_stability * 0.3) + random.uniform(-0.1, 0.1)))
        
        # Payment terms based on financial stability and archetype
        if archetype == "strategic":
            payment_terms = random.randint(30, 60)
        elif financial_stability > 0.8:
            payment_terms = random.randint(30, 45) 
        else:
            payment_terms = random.randint(15, 30)
            
        # Calculate reliability score from operational performance metrics  
        # Reliability represents overall operational dependability - derived from actual performance
        reliability_from_otif = otif_percent / 100.0
        reliability_from_quality = 1.0 - min(ppm_defects / 1000.0, 1.0)  # Capped at 1000 PPM
        reliability_from_consistency = lead_time_consistency / 100.0
        reliability_from_communication = min(1.0, response_time / 120.0)  # Better response = higher reliability
        
        # Weighted combination of reliability factors
        calculated_reliability = (
            reliability_from_otif * 0.40 +           # On-time delivery is most important
            reliability_from_quality * 0.30 +        # Quality consistency 
            reliability_from_consistency * 0.20 +    # Lead time predictability
            (1.0 - reliability_from_communication) * 0.10  # Communication responsiveness (inverted)
        )
        
        # Calculate comprehensive vendor maturity score from multiple business metrics
        # Maturity is assessed across 5 key dimensions with different weightings
        
        # 1. Operational Excellence (35% weight)
        operational_score = (
            (otif_percent / 100.0) * 0.4 +                    # On-time delivery performance
            (lead_time_consistency / 100.0) * 0.3 +           # Consistency in delivery
            (1 - min(ppm_defects / 1000.0, 1.0)) * 0.3       # Quality (inverse of defects, capped at 1000 PPM)
        )
        
        # 2. Financial Maturity (25% weight)  
        financial_maturity = (
            financial_stability * 0.6 +                       # Overall financial health
            min(1.0, max(0.0, (4.0 - debt_to_equity) / 4.0)) * 0.4  # Debt management (optimal around 1.0 D/E)
        )
        
        # 3. Innovation & Technology (20% weight)
        innovation_score = (
            digital_transformation * 0.4 +                    # Digital readiness
            (tech_readiness / 9.0) * 0.3 +                   # Technology maturity (TRL scale)
            patent_strength * 0.3                             # IP portfolio strength
        )
        
        # 4. Business Maturity (15% weight) 
        company_age_factor = min(1.0, company_age / 25.0)     # Mature at 25+ years
        
        # Company size factor (larger = more mature processes)
        size_factors = {"Enterprise": 1.0, "Large": 0.85, "Medium": 0.7, "Small": 0.55}
        size_factor = size_factors.get(template["company_size"], 0.6)
        
        business_maturity = (company_age_factor * 0.6 + size_factor * 0.4)
        
        # 5. Communication & Partnership (5% weight)
        partnership_maturity = (
            communication_quality * 0.7 +
            continuous_improvement * 0.3
        )
        
        # Calculate final vendor maturity score
        vendor_maturity = (
            operational_score * 0.35 +
            financial_maturity * 0.25 + 
            innovation_score * 0.20 +
            business_maturity * 0.15 +
            partnership_maturity * 0.05
        )
        
        # Generate compliance & certifications data based on archetype and regional factors
        # UFLPA compliance (higher for strategic suppliers and US/EU regions)
        uflpa_base_rate = {"strategic": 0.90, "leverage": 0.75, "bottleneck": 0.65, "routine": 0.55}
        regional_uflpa_bonus = {"US": 0.10, "EU": 0.08, "KR": 0.05, "CN": -0.15, "MX": 0.02, "VN": -0.10, "IN": -0.05}
        uflpa_prob = min(0.95, uflpa_base_rate[archetype] + regional_uflpa_bonus.get(template["region"], 0))
        uflpa_compliant = random.random() < uflpa_prob
        
        # Conflict minerals compliance (higher for established companies and regulated regions)
        conflict_base_rate = {"strategic": 0.85, "leverage": 0.70, "bottleneck": 0.60, "routine": 0.50}
        regional_conflict_bonus = {"US": 0.12, "EU": 0.15, "KR": 0.08, "CN": -0.10, "MX": 0.05, "VN": -0.08, "IN": -0.03}
        conflict_prob = min(0.95, conflict_base_rate[archetype] + regional_conflict_bonus.get(template["region"], 0))
        conflict_minerals_compliant = random.random() < conflict_prob
        
        # Last audit date (strategic suppliers audited more recently)
        if archetype == "strategic":
            audit_days_ago = random.randint(30, 180)  # 1-6 months ago
        elif archetype == "leverage":
            audit_days_ago = random.randint(90, 365)  # 3-12 months ago
        elif archetype == "bottleneck":
            audit_days_ago = random.randint(180, 540)  # 6-18 months ago
        else:  # routine
            audit_days_ago = random.randint(365, 730)  # 1-2 years ago
        
        # 20% chance of no recent audit (especially for routine suppliers)
        no_audit_prob = {"strategic": 0.05, "leverage": 0.10, "bottleneck": 0.15, "routine": 0.25}
        if random.random() < no_audit_prob[archetype]:
            last_audit_date = None
        else:
            last_audit_date = base_date - timedelta(days=audit_days_ago)
        
        # ISO certifications based on company size, archetype, and industry focus
        iso_certification_pool = {
            "quality": ["ISO 9001:2015", "ISO/TS 16949:2016"],  # Quality management
            "environmental": ["ISO 14001:2015", "ISO 50001:2018"],  # Environmental/Energy
            "safety": ["ISO 45001:2018", "ISO 31000:2018"],  # Safety/Risk management
            "security": ["ISO 27001:2022", "ISO 22301:2019"],  # Information security/Business continuity
            "specialized": ["ISO 13485:2016", "ISO 26000:2010", "AS9100D", "ISO 14971:2019"]  # Medical, Social responsibility, Aerospace
        }
        
        # Determine certification count based on archetype and company size
        size_multiplier = {"Enterprise": 1.0, "Large": 0.8, "Medium": 0.6, "Small": 0.4}
        archetype_cert_range = {
            "strategic": (4, 8),  # 4-8 certifications
            "leverage": (2, 5),   # 2-5 certifications  
            "bottleneck": (3, 6), # 3-6 certifications (specialized)
            "routine": (1, 3)     # 1-3 certifications
        }
        
        min_certs, max_certs = archetype_cert_range[archetype]
        target_cert_count = random.randint(min_certs, max_certs)
        actual_cert_count = max(1, int(target_cert_count * size_multiplier[template["company_size"]]))
        
        # Select certifications with realistic probability distributions
        selected_certifications = []
        
        # Quality certifications (almost all companies have these)
        if random.random() < 0.85:
            selected_certifications.append(random.choice(iso_certification_pool["quality"]))
        
        # Environmental certifications (higher for strategic and EU companies)
        env_prob = 0.70 if archetype in ["strategic", "leverage"] else 0.45
        if template["region"] == "EU":
            env_prob += 0.15
        if random.random() < env_prob:
            selected_certifications.append(random.choice(iso_certification_pool["environmental"]))
        
        # Safety certifications (higher for manufacturing-heavy companies)
        safety_prob = 0.60 if template["company_size"] in ["Enterprise", "Large"] else 0.35
        if random.random() < safety_prob:
            selected_certifications.append(random.choice(iso_certification_pool["safety"]))
        
        # Security certifications (higher for tech companies and strategic suppliers)
        security_prob = 0.50 if archetype == "strategic" else 0.25
        if archetype == "bottleneck":  # Specialized tech companies
            security_prob = 0.65
        if random.random() < security_prob:
            selected_certifications.append(random.choice(iso_certification_pool["security"]))
        
        # Specialized certifications (especially for bottleneck suppliers)
        if archetype == "bottleneck" and random.random() < 0.40:
            selected_certifications.append(random.choice(iso_certification_pool["specialized"]))
        elif archetype == "strategic" and random.random() < 0.25:
            selected_certifications.append(random.choice(iso_certification_pool["specialized"]))
        
        # Ensure we don't exceed the target count and remove duplicates
        selected_certifications = list(set(selected_certifications))
        if len(selected_certifications) > actual_cert_count:
            selected_certifications = random.sample(selected_certifications, actual_cert_count)
        
        # Add more basic certifications if we're under the target
        all_certs = [cert for cert_list in iso_certification_pool.values() for cert in cert_list]
        while len(selected_certifications) < actual_cert_count:
            remaining_certs = [cert for cert in all_certs if cert not in selected_certifications]
            if remaining_certs:
                selected_certifications.append(random.choice(remaining_certs))
            else:
                break
        
        # Create enhanced vendor with all comprehensive properties
        enhanced_vendor = {
            "id": f"vendor_{i+1:02d}",
            "name": template["name"],
            "region": template["region"],
            "archetype": template["archetype"],  # Store archetype for parts generation
            "calculated_reliability": round(min(0.98, max(0.30, calculated_reliability)), 3),  # For internal use only
            "contact_email": template["email"],
            "last_verified": base_date - timedelta(days=days_ago),
            "created_time": datetime.now() - timedelta(days=random.randint(30, 365)),
            
            # Financial metrics
            "annual_revenue": int(revenue),
            "employee_count": employee_count,
            "debt_to_equity_ratio": round(debt_to_equity, 2),
            "financial_stability_score": round(financial_stability, 3),
            "credit_rating": template["credit_rating"],
            "payment_terms": payment_terms,
            
            # Operational metrics
            "founded_year": template["founded_year"],
            "company_size": template["company_size"],
            "market_presence": template["market_presence"],
            "manufacturing_sites": template["manufacturing_sites"],
            "otif_percent": round(otif_percent, 1),
            "ppm_defects": ppm_defects,
            "lead_time_consistency": round(lead_time_consistency, 1),
            "response_time": round(response_time, 1),
            "communication_quality": round(communication_quality, 3),
            
            # Risk metrics
            "country_risk_score": round(region_factors["country_risk"], 3),
            "currency_stability_risk": round(region_factors["currency_stability"], 3), 
            "trade_relations_risk": round(region_factors["trade_relations"], 3),
            "regulatory_compliance_risk": round(1 - region_factors["regulatory_compliance"], 3),
            "supply_chain_resilience": round(supply_chain_resilience, 3),
            
            # Innovation metrics
            "rd_investment_percent": round(rd_investment, 1),
            "technology_readiness_level": tech_readiness,
            "digital_transformation_score": round(digital_transformation, 3),
            "patent_portfolio_strength": round(patent_strength, 3),
            "innovation_partnership_potential": round(partnership_potential, 3),
            "continuous_improvement_score": round(continuous_improvement, 3),
            
            # Compliance & Certifications (realistic patterns by archetype)
            "uflpa_compliant": uflpa_compliant,
            "conflict_minerals_compliant": conflict_minerals_compliant,
            "last_audit_date": last_audit_date,
            "iso_certifications": selected_certifications,
            
            # Derived maturity score (comprehensive assessment)
            "vendor_maturity_score": round(min(0.98, max(0.25, vendor_maturity)), 3)
        }
        
        # Convert to simple Vendor object for compatibility
        vendor = Vendor(
            id=enhanced_vendor["id"],
            name=enhanced_vendor["name"], 
            region=enhanced_vendor["region"],
            reliability_score=enhanced_vendor["calculated_reliability"],  # Use calculated reliability for internal compatibility
            contact_email=enhanced_vendor["contact_email"],
            last_verified=enhanced_vendor["last_verified"],
            created_time=enhanced_vendor["created_time"]
        )
        
        # Store enhanced data for Notion creation
        vendor._enhanced_data = enhanced_vendor
        
        # Set compliance data as direct attributes for Streamlit app compatibility
        vendor.uflpa_compliant = enhanced_vendor["uflpa_compliant"]
        vendor.conflict_minerals_compliant = enhanced_vendor["conflict_minerals_compliant"]
        vendor.last_audit_date = enhanced_vendor["last_audit_date"]
        vendor.iso_certifications = enhanced_vendor["iso_certifications"]
        
        vendors.append(vendor)
    
    # Enhanced component catalog aligned with vendor archetypes and industry scenarios
    component_catalog = {
        # Strategic supplier components (high-value, critical)
        "strategic": [
            {"name": "Tesla 4680 Li-ion Cell", "base_price": 12.50, "category": "battery"},
            {"name": "Samsung 21700 NMC Cell", "base_price": 8.25, "category": "battery"},  
            {"name": "CATL LiFePO4 Prismatic 100Ah", "base_price": 145.00, "category": "battery"},
            {"name": "Solid-State Li Metal Cell 5Ah", "base_price": 89.50, "category": "battery"},
            {"name": "Apple Silicon A17 Pro SoC", "base_price": 58.00, "category": "semiconductor"},
            {"name": "NVIDIA Tegra AI Processor", "base_price": 125.00, "category": "semiconductor"},
            {"name": "Qualcomm Snapdragon X Elite", "base_price": 95.00, "category": "semiconductor"}
        ],
        
        # Leverage supplier components (competitive commodity)
        "leverage": [
            {"name": "LG 18650 Li-ion Cell 2500mAh", "base_price": 4.80, "category": "battery"},
            {"name": "Panasonic 21700 Cell 4000mAh", "base_price": 6.20, "category": "battery"},
            {"name": "BYD LiFePO4 Blade Cell", "base_price": 52.00, "category": "battery"},
            {"name": "Samsung AMOLED 6.1\" Display", "base_price": 45.00, "category": "display"},
            {"name": "MediaTek Dimensity 9300", "base_price": 38.00, "category": "semiconductor"},
            {"name": "ARM Cortex-A78 MCU", "base_price": 28.50, "category": "semiconductor"},
            {"name": "Omnivision OV64B Camera Sensor", "base_price": 18.20, "category": "sensor"}
        ],
        
        # Bottleneck supplier components (specialized, constrained)
        "bottleneck": [
            {"name": "Rare Earth Permanent Magnet NdFeB", "base_price": 185.00, "category": "materials"},
            {"name": "Tungsten Carbide Coating", "base_price": 95.50, "category": "materials"},
            {"name": "Gallium Arsenide RF Amplifier", "base_price": 125.00, "category": "semiconductor"},
            {"name": "Indium Gallium Zinc Oxide TFT", "base_price": 78.50, "category": "display"},
            {"name": "Precision Titanium Alloy Housing", "base_price": 245.00, "category": "mechanical"},
            {"name": "Lithium Metal Anode Material", "base_price": 420.00, "category": "materials"},
            {"name": "Single Crystal Silicon Wafer", "base_price": 158.00, "category": "materials"}
        ],
        
        # Routine supplier components (standard, interchangeable)
        "routine": [
            {"name": "Standard USB-C Connector", "base_price": 1.85, "category": "connector"},
            {"name": "Plastic Injection Housing", "base_price": 2.40, "category": "mechanical"},
            {"name": "FR4 PCB 4-layer", "base_price": 3.20, "category": "pcb"},
            {"name": "Ceramic Capacitor 10uF", "base_price": 0.15, "category": "passive"},
            {"name": "SMD Resistor Array", "base_price": 0.08, "category": "passive"},
            {"name": "Standard Flex Cable", "base_price": 1.25, "category": "cable"},
            {"name": "Silicone O-Ring Seal", "base_price": 0.45, "category": "seal"},
            {"name": "Aluminum Heat Sink", "base_price": 4.20, "category": "thermal"},
            {"name": "Polyimide Film Sheet", "base_price": 2.80, "category": "materials"},
            {"name": "Standard Phillips Screws M2", "base_price": 0.05, "category": "fastener"}
        ]
    }
    
    # ODM destinations (where parts are shipped)
    odm_destinations = [
        ("PDGV", "California, USA"),
        ("Foxconn", "Shenzhen, China"), 
        ("Flex", "Austin, Texas"),
        ("Jabil", "St. Petersburg, Florida"),
        ("Wistron", "Taipei, Taiwan"),
        ("Pegatron", "Shanghai, China"),
        ("Compal", "Kunshan, China"),
        ("Quanta", "Taoyuan, Taiwan")
    ]
    
    # Shipping data and regional parameters
    shipping_data = {
        "US": {"Air": (2, 5), "Ground": (3, 7), "Ocean": (14, 21)},
        "CN": {"Air": (3, 7), "Ocean": (18, 28), "Ground": (28, 35)},
        "KR": {"Air": (2, 4), "Ocean": (14, 21), "Ground": (21, 28)},
        "EU": {"Air": (1, 3), "Ocean": (12, 18), "Ground": (5, 9)},
        "VN": {"Air": (4, 8), "Ocean": (21, 30), "Ground": (30, 42)},
        "MX": {"Air": (1, 2), "Ground": (2, 4), "Ocean": (7, 12)},
        "IN": {"Air": (5, 9), "Ocean": (25, 35), "Ground": (35, 50)}
    }
    
    tariff_rates = {
        "CN": [0, 2.5, 6.5, 10.0], "KR": [0, 0, 2.5, 6.5], "EU": [0, 2.5, 4.0, 6.5],
        "VN": [0, 0, 2.5, 6.5], "MX": [0, 0, 0, 2.5], "IN": [0, 2.5, 6.5, 10.0], "US": [0, 0, 0, 0]
    }
    
    region_multiplier = {
        "CN": 0.85, "VN": 0.80, "IN": 0.75, "KR": 1.0, "MX": 0.90, "US": 1.15, "EU": 1.25
    }
    
    # Generate parts aligned with vendor archetypes  
    parts = []
    part_id = 1
    
    for vendor in vendors:
        archetype = vendor._enhanced_data["archetype"] if hasattr(vendor, '_enhanced_data') else "routine"
        
        # Number of parts based on archetype
        if archetype == "strategic":
            num_parts = random.choices([1, 2, 3], weights=[30, 50, 20])[0]  # Fewer, high-value parts
        elif archetype == "leverage":
            num_parts = random.choices([2, 3, 4, 5], weights=[20, 40, 30, 10])[0]  # Multiple competitive parts
        elif archetype == "bottleneck":
            num_parts = random.choices([1, 2], weights=[70, 30])[0]  # Few specialized parts
        else:  # routine
            num_parts = random.choices([2, 3, 4, 5, 6], weights=[15, 25, 35, 20, 5])[0]  # Many standard parts
        
        for _ in range(num_parts):
            # Select component from archetype-appropriate catalog
            if archetype in component_catalog:
                component_info = random.choice(component_catalog[archetype])
            else:
                component_info = random.choice(component_catalog["routine"])
                
            component = component_info["name"]
            base_price = component_info["base_price"]
            odm_dest, odm_region = random.choice(odm_destinations)
            
            # Apply regional pricing multipliers
            unit_price = base_price * region_multiplier[vendor.region] * random.uniform(0.85, 1.15)
            
            # Shipping configuration
            shipping_modes = list(shipping_data[vendor.region].keys())
            shipping_mode = random.choice(shipping_modes)
            
            if shipping_mode == "Air":
                freight_cost = random.uniform(0.15, 0.45) * region_multiplier[vendor.region]
            elif shipping_mode == "Ocean":
                freight_cost = random.uniform(0.05, 0.20)
            else:  # Ground
                freight_cost = random.uniform(0.08, 0.25)
            
            transit_range = shipping_data[vendor.region][shipping_mode]
            transit_days = random.randint(transit_range[0], transit_range[1])
            
            # Lead time based on supplier reliability
            if vendor.reliability_score > 0.85:
                lead_time = random.choices([2, 3, 4, 6], weights=[20, 40, 30, 10])[0]
            else:
                lead_time = random.choices([3, 4, 6, 8, 12], weights=[10, 25, 35, 20, 10])[0]
            
            # Tariff rates
            tariff_options = tariff_rates[vendor.region]
            tariff_weights = [40, 20, 30, 10] if vendor.region in ["CN", "IN"] else [60, 25, 10, 5]
            tariff_rate = random.choices(tariff_options, weights=tariff_weights)[0]
            
            # Capacity based on archetype, company size, and component type
            if archetype == "strategic":
                # Strategic suppliers: high capacity, premium components
                if component_info["category"] in ["battery", "semiconductor"]:
                    capacity = random.randint(100000, 500000)
                else:
                    capacity = random.randint(50000, 200000)
            elif archetype == "leverage":
                # Leverage suppliers: competitive volume production
                capacity = random.randint(200000, 1000000)
            elif archetype == "bottleneck":
                # Bottleneck suppliers: limited capacity, specialized
                capacity = random.randint(1000, 15000)
            else:  # routine
                # Routine suppliers: variable capacity, standard components  
                capacity = random.randint(50000, 300000)
            
            # Verification date
            part_verified = vendor.last_verified
            if random.random() < 0.3:  # 30% chance of more recent part data
                part_verified = vendor.last_verified + timedelta(days=random.randint(1, 10))
                if part_verified > date.today():
                    part_verified = date.today()
            
            # Generate part-level compliance data with realistic regional patterns
            # RoHS compliance (Restriction of Hazardous Substances) - EU directive, widely adopted
            rohs_base_rates = {"EU": 0.95, "US": 0.85, "KR": 0.82, "CN": 0.75, "MX": 0.70, "VN": 0.65, "IN": 0.68}
            rohs_rate = rohs_base_rates.get(vendor.region, 0.70)
            
            # Adjust by archetype (strategic suppliers higher compliance)
            archetype_rohs_bonus = {"strategic": 0.08, "leverage": 0.05, "bottleneck": 0.03, "routine": 0.0}
            rohs_rate += archetype_rohs_bonus[archetype]
            
            # Component category affects compliance (electronic components higher rate)
            if component_info["category"] in ["semiconductor", "display", "sensor"]:
                rohs_rate += 0.10  # Electronics more likely to be RoHS compliant
            
            rohs_compliant = random.random() < min(0.98, rohs_rate)
            
            # REACH compliance (Registration, Evaluation, Authorization of Chemicals) - EU regulation
            reach_base_rates = {"EU": 0.92, "US": 0.70, "KR": 0.65, "CN": 0.60, "MX": 0.55, "VN": 0.50, "IN": 0.52}
            reach_rate = reach_base_rates.get(vendor.region, 0.55)
            
            # Adjust by archetype
            archetype_reach_bonus = {"strategic": 0.10, "leverage": 0.06, "bottleneck": 0.04, "routine": 0.0}
            reach_rate += archetype_reach_bonus[archetype]
            
            # Material-based components more likely to need REACH compliance
            if component_info["category"] in ["materials", "battery"]:
                reach_rate += 0.12  # Chemical/material components more critical for REACH
            
            reach_compliant = random.random() < min(0.96, reach_rate)
            
            part = Part(
                id=f"part_{part_id:03d}",
                component_name=component,
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                odm_destination=odm_dest,
                odm_region=odm_region,
                unit_price=round(unit_price, 2),
                freight_cost=round(freight_cost, 3),
                tariff_rate_pct=tariff_rate,
                lead_time_weeks=lead_time,
                transit_days=transit_days,
                shipping_mode=shipping_mode,
                monthly_capacity=capacity,
                rohs_compliant=rohs_compliant,
                reach_compliant=reach_compliant,
                last_verified=part_verified,
                timestamp=datetime.now() - timedelta(days=random.randint(1, 30)),
                notes=f"Demo data for {component}" if random.random() < 0.2 else ""
            )
            
            parts.append(part)
            part_id += 1
            
            if len(parts) >= 60:  # Limit to 60 parts total
                break
        
        if len(parts) >= 60:
            break
    
    return vendors, parts


class NotionPopulator:
    """Notion database populator with rate limiting and error handling."""
    
    def __init__(self, api_key: str, vendors_db_id: str, parts_db_id: str, scores_db_id: str = None):
        self.api_key = api_key
        self.vendors_db_id = vendors_db_id
        self.parts_db_id = parts_db_id
        self.scores_db_id = scores_db_id
        
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        # Rate limiting: Notion allows ~3 requests per second
        self.last_request_time = 0
        self.min_request_interval = 0.35
        
        # Session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Schema caches
        self._vendors_schema: Optional[Dict[str, Any]] = None
        self._parts_schema: Optional[Dict[str, Any]] = None
        
        print(f"[INIT] Initialized Notion API connection")
    
    def _rate_limit(self):
        """Ensure we don't exceed Notion's rate limits."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self.last_request_time = time.time()
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with rate limiting and error handling."""
        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, headers=self.headers, **kwargs)
        
        if response.status_code == 429:
            wait_time = int(response.headers.get('Retry-After', 5))
            print(f"[WAIT] Rate limited, waiting {wait_time}s...")
            time.sleep(wait_time)
            return self._make_request(method, endpoint, **kwargs)
        
        if not response.ok:
            try:
                error_data = response.json()
                error_msg = f"Notion API error: {response.status_code}\n"
                error_msg += f"Message: {error_data.get('message', response.text)}\n"
                if 'code' in error_data:
                    error_msg += f"Code: {error_data['code']}\n"
                if 'details' in error_data:
                    error_msg += f"Details: {error_data['details']}"
            except:
                error_msg = f"Notion API error: {response.status_code} - {response.text}"
            raise Exception(error_msg)
        
        return response.json()
    
    def test_connection(self) -> bool:
        """Test connection to Notion API."""
        try:
            self._make_request("GET", f"/databases/{self.vendors_db_id}")
            print("[OK] Connected to Vendors database")
            
            self._make_request("GET", f"/databases/{self.parts_db_id}")
            print("[OK] Connected to Parts database")
            
            if self.scores_db_id:
                self._make_request("GET", f"/databases/{self.scores_db_id}")
                print("[OK] Connected to Scores database")
            
            return True
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False
    
    def validate_schema(self, db_id: str, db_name: str, required_props: Dict[str, str]) -> bool:
        """Validate database schema."""
        try:
            print(f"\n[VALIDATION] Validating {db_name} database...")
            response = self._make_request("GET", f"/databases/{db_id}")
            properties = response.get('properties', {})
            
            valid = True
            for prop_name, expected_type in required_props.items():
                if prop_name not in properties:
                    print(f"  [MISSING] {prop_name} ({expected_type})")
                    valid = False
                else:
                    actual_type = properties[prop_name]['type']
                    if actual_type == expected_type:
                        print(f"  [OK] {prop_name}")
                    else:
                        print(f"  [WARNING] {prop_name}: expected {expected_type}, found {actual_type}")
                        if not ((expected_type == 'rich_text' and actual_type == 'text') or
                               (expected_type == 'text' and actual_type == 'rich_text')):
                            valid = False
            
            return valid
        except Exception as e:
            print(f"[ERROR] Schema validation failed: {e}")
            return False
    
    def validate_all_schemas(self) -> bool:
        """Validate all database schemas."""
        print("[VALIDATION] Validating database schemas...")
        
        # Updated vendors schema to match exact Notion column names
        vendors_schema = {
            "Name": "title", 
            "Region": "select", 
            "Contact Email": "email", 
            "Last Verified": "date",
            # Core business metrics
            "Vendor Maturity Score": "number",
            "Annual Revenue (USD)": "number",
            "Employee Count": "number", 
            "Founded Year": "number",
            "Company Size": "select",
            "Market Presence": "select",
            # Financial metrics
            "Financial Stability Score": "number",
            "Debt to Equity Ratio": "number",
            "Credit Rating": "select",
            "Payment Terms (days)": "number",
            # Operational metrics
            "OTIF %": "number",
            "PPM Defects": "number",
            "Lead Time Consistency %": "number",
            "Response Time (hrs)": "number",
            "Communication Quality": "number",
            "Manufacturing Sites": "number",
            # Risk metrics
            "Country Risk Score": "number",
            "Currency Stability Risk": "number",
            "Trade Relations Risk": "number",
            "Regulatory Compliance Risk": "number",
            "Supply Chain Resilience": "number",
            # Innovation metrics
            "R&D Investment %": "number",
            "Technology Readiness Level": "number", 
            "Digital Transformation Score": "number",
            "Patent Portfolio Strength": "number",
            "Innovation Partnership Potential": "number",
            "Continuous Improvement Score": "number",
            # Compliance & Certifications
            "UFLPA Compliant": "checkbox",
            "Conflict Minerals Compliant": "checkbox",
            "Last Audit Date": "date",
            "ISO Certifications": "multi_select"
        }
        
        parts_schema = {
            "Component Name": "title", "Vendor": "relation", "ODM Destination": "rich_text",
            "ODM Region": "rich_text", "Unit Price": "number", "Freight Cost": "number",
            "Tariff Rate": "number", "Lead Time (weeks)": "number", "Transit Days": "number",
            "Shipping Mode": "select", "Monthly Capacity": "number", "Last Verified": "date",
            # Compliance & Certifications
            "RoHS Compliant": "checkbox",
            "REACH Compliant": "checkbox"
        }
        
        vendors_valid = self.validate_schema(self.vendors_db_id, "Vendors", vendors_schema)
        parts_valid = self.validate_schema(self.parts_db_id, "Parts", parts_schema)
        
        all_valid = vendors_valid and parts_valid
        
        if all_valid:
            print("\n[SUCCESS] All schemas valid!")
        else:
            print("\n[WARNING] Schema issues found. Fix before populating data.")
        
        return all_valid
    
    def check_existing_data(self) -> Tuple[int, int]:
        """Check existing data in databases."""
        try:
            vendors_response = self._make_request("POST", f"/databases/{self.vendors_db_id}/query", 
                                                json={"page_size": 1})
            vendor_count = len(vendors_response.get('results', []))
            
            parts_response = self._make_request("POST", f"/databases/{self.parts_db_id}/query",
                                              json={"page_size": 1})
            parts_count = len(parts_response.get('results', []))
            
            return vendor_count, parts_count
        except:
            return 0, 0
    
    def _get_db_schema(self, db_id: str) -> Dict[str, Any]:
        """Fetch and cache database schema properties."""
        if db_id == self.vendors_db_id and self._vendors_schema is not None:
            return self._vendors_schema
        if db_id == self.parts_db_id and self._parts_schema is not None:
            return self._parts_schema
        resp = self._make_request("GET", f"/databases/{db_id}")
        props = resp.get('properties', {})
        if db_id == self.vendors_db_id:
            self._vendors_schema = props
        elif db_id == self.parts_db_id:
            self._parts_schema = props
        return props

    def create_vendor(self, vendor: Vendor) -> str:
        """Create vendor in Notion with comprehensive properties."""
        # Get enhanced data if available
        enhanced_data = getattr(vendor, '_enhanced_data', {})
        
        # Base properties
        data = {
            "parent": {"database_id": self.vendors_db_id},
            "properties": {
                "Name": {"title": [{"text": {"content": vendor.name}}]},
                "Region": {"select": {"name": vendor.region}},
                "Last Verified": {"date": {"start": vendor.last_verified.isoformat()}} if vendor.last_verified else None,
                "Contact Email": {"email": vendor.contact_email} if vendor.contact_email else None,
            }
        }
        
        # Populate all enhanced properties if available
        try:
            schema = self._get_db_schema(self.vendors_db_id)
            props = data["properties"]
            
            def has_prop(name: str, ptype: str = None) -> bool:
                return name in schema and (ptype is None or schema[name].get('type') == ptype)
            
            def add_prop(notion_name: str, data_key: str, prop_type: str, format_fn=None):
                if has_prop(notion_name, prop_type) and data_key in enhanced_data:
                    value = enhanced_data[data_key]
                    if format_fn:
                        value = format_fn(value)
                    
                    if prop_type == "number":
                        props[notion_name] = {"number": value}
                    elif prop_type == "select":
                        props[notion_name] = {"select": {"name": str(value)}}
                    elif prop_type == "email":
                        props[notion_name] = {"email": value}
                    elif prop_type == "date":
                        props[notion_name] = {"date": {"start": value.isoformat() if hasattr(value, 'isoformat') else value}}
                    elif prop_type == "rich_text":
                        props[notion_name] = {"rich_text": [{"text": {"content": str(value)}}]}
            
            # Financial metrics
            add_prop("Annual Revenue (USD)", "annual_revenue", "number")
            add_prop("Employee Count", "employee_count", "number") 
            add_prop("Debt to Equity Ratio", "debt_to_equity_ratio", "number")
            add_prop("Financial Stability Score", "financial_stability_score", "number")
            add_prop("Credit Rating", "credit_rating", "select")
            add_prop("Payment Terms (days)", "payment_terms", "number")
            
            # Operational metrics
            add_prop("Founded Year", "founded_year", "number")
            add_prop("Company Size", "company_size", "select") 
            add_prop("Market Presence", "market_presence", "select")
            add_prop("Manufacturing Sites", "manufacturing_sites", "number")
            add_prop("OTIF %", "otif_percent", "number", lambda x: x / 100.0)  # Convert to decimal
            add_prop("PPM Defects", "ppm_defects", "number")
            add_prop("Lead Time Consistency %", "lead_time_consistency", "number", lambda x: x / 100.0)
            add_prop("Response Time (hrs)", "response_time", "number")
            add_prop("Communication Quality", "communication_quality", "number")
            
            # Risk metrics
            add_prop("Country Risk Score", "country_risk_score", "number")
            add_prop("Currency Stability Risk", "currency_stability_risk", "number")
            add_prop("Trade Relations Risk", "trade_relations_risk", "number") 
            add_prop("Regulatory Compliance Risk", "regulatory_compliance_risk", "number")
            add_prop("Supply Chain Resilience", "supply_chain_resilience", "number")
            
            # Innovation metrics
            add_prop("R&D Investment %", "rd_investment_percent", "number", lambda x: x / 100.0)
            add_prop("Technology Readiness Level", "technology_readiness_level", "number")
            add_prop("Digital Transformation Score", "digital_transformation_score", "number")
            add_prop("Patent Portfolio Strength", "patent_portfolio_strength", "number")
            add_prop("Innovation Partnership Potential", "innovation_partnership_potential", "number")
            add_prop("Continuous Improvement Score", "continuous_improvement_score", "number")
            
            # Compliance & Certifications
            if has_prop("UFLPA Compliant", "checkbox") and "uflpa_compliant" in enhanced_data:
                props["UFLPA Compliant"] = {"checkbox": enhanced_data["uflpa_compliant"]}
            if has_prop("Conflict Minerals Compliant", "checkbox") and "conflict_minerals_compliant" in enhanced_data:
                props["Conflict Minerals Compliant"] = {"checkbox": enhanced_data["conflict_minerals_compliant"]}
            if has_prop("Last Audit Date", "date") and "last_audit_date" in enhanced_data and enhanced_data["last_audit_date"]:
                props["Last Audit Date"] = {"date": {"start": enhanced_data["last_audit_date"].isoformat()}}
            if has_prop("ISO Certifications", "multi_select") and "iso_certifications" in enhanced_data:
                cert_list = enhanced_data["iso_certifications"]
                if cert_list:
                    props["ISO Certifications"] = {"multi_select": [{"name": cert} for cert in cert_list]}
            
            # Maturity scores
            add_prop("Vendor Maturity Score", "vendor_maturity_score", "number")
                
        except Exception as e:
            # If schema fetch fails, proceed with minimal properties
            print(f"[WARNING] Schema error for {vendor.name}: {e}")
            props = data["properties"]
        
        # Remove None values
        data["properties"] = {k: v for k, v in data["properties"].items() if v is not None}
        
        response = self._make_request("POST", f"/pages", json=data)
        return response["id"]
    
    def create_part(self, part: Part) -> str:
        """Create part in Notion."""
        data = {
            "parent": {"database_id": self.parts_db_id},
            "properties": {
                "Component Name": {"title": [{"text": {"content": part.component_name}}]},
                "Vendor": {"relation": [{"id": part.vendor_id}]},
                "ODM Destination": {"rich_text": [{"text": {"content": part.odm_destination}}]},
                "ODM Region": {"rich_text": [{"text": {"content": part.odm_region}}]},
                "Unit Price": {"number": part.unit_price},
                "Freight Cost": {"number": part.freight_cost},
                "Tariff Rate": {"number": part.tariff_rate_pct / 100},
                "Lead Time (weeks)": {"number": part.lead_time_weeks},
                "Transit Days": {"number": part.transit_days},
                "Shipping Mode": {"select": {"name": part.shipping_mode}},
                "Monthly Capacity": {"number": part.monthly_capacity},
                "Last Verified": {"date": {"start": part.last_verified.isoformat()}} if part.last_verified else None,
                "RoHS Compliant": {"checkbox": part.rohs_compliant},
                "REACH Compliant": {"checkbox": part.reach_compliant}
            }
        }
        
        # Remove None values
        data["properties"] = {k: v for k, v in data["properties"].items() if v is not None}
        
        response = self._make_request("POST", f"/pages", json=data)
        return response["id"]
    
    def populate_databases(self, force: bool = False) -> Dict[str, Any]:
        """Populate databases with demo data."""
        print("\n[START] Starting database population...")
        
        # Check existing data
        existing_vendors, existing_parts = self.check_existing_data()
        
        if (existing_vendors > 0 or existing_parts > 0) and not force:
            print(f"\n[WARNING] Databases contain data: {existing_vendors} vendors, {existing_parts} parts")
            print(f"[INFO] Use --force flag to add more data")
            return {"success": False, "message": "Data exists. Use --force to continue."}
        
        # Generate demo data
        print("\n[DATA] Generating demo data...")
        vendors, parts = generate_demo_data()
        print(f"Generated {len(vendors)} vendors and {len(parts)} parts")
        
        # Population tracking
        created_vendors = 0
        created_parts = 0
        vendor_id_map = {}
        errors = []
        
        # Create vendors
        print(f"\n[VENDORS] Creating {len(vendors)} vendors...")
        for i, vendor in enumerate(vendors):
            try:
                real_vendor_id = self.create_vendor(vendor)
                vendor_id_map[vendor.id] = real_vendor_id
                created_vendors += 1
                progress = ((i + 1) / len(vendors)) * 100
                print(f"  [OK] {vendor.name} ({i+1}/{len(vendors)}) - {progress:.0f}%")
            except Exception as e:
                errors.append(f"Vendor {vendor.name}: {e}")
                print(f"  [ERROR] Failed: {vendor.name}")
        
        # Create parts
        print(f"\n[PARTS] Creating {len(parts)} parts...")
        for i, part in enumerate(parts):
            try:
                if part.vendor_id in vendor_id_map:
                    part.vendor_id = vendor_id_map[part.vendor_id]
                    self.create_part(part)
                    created_parts += 1
                    progress = ((i + 1) / len(parts)) * 100
                    print(f"  [OK] {part.component_name} ({i+1}/{len(parts)}) - {progress:.0f}%")
                else:
                    errors.append(f"Part {part.component_name}: vendor not found")
            except Exception as e:
                errors.append(f"Part {part.component_name}: {e}")
                print(f"  [ERROR] Failed: {part.component_name}")
        
        # Summary
        success = created_vendors > 0 and created_parts > 0
        print(f"\n[COMPLETE] Population complete!")
        print(f"   [VENDORS] {created_vendors}/{len(vendors)}")
        print(f"   [PARTS] {created_parts}/{len(parts)}")
        print(f"   [ERRORS] {len(errors)}")
        
        if success:
            print(f"\n[SUCCESS] Your Vendor Database now contains realistic demo data.")
            print(f"[READY] Ready to run your Vendor Database application!")
        
        return {
            "success": success,
            "vendors_created": created_vendors,
            "parts_created": created_parts,
            "errors": len(errors)
        }

    def dump_database_schema(self, db_id: str, db_name: str) -> Dict[str, Any]:
        """Fetch and print a concise schema of a Notion database."""
        try:
            resp = self._make_request("GET", f"/databases/{db_id}")
            properties = resp.get('properties', {})
            print(f"\n[SCHEMA] {db_name} properties ({len(properties)}):")
            schema_list = []
            for prop_name, prop in properties.items():
                ptype = prop.get('type', 'unknown')
                schema_list.append({"name": prop_name, "type": ptype})
                print(f"  - {prop_name}: {ptype}")
            return {"name": db_name, "properties": schema_list}
        except Exception as e:
            print(f"[ERROR] Failed to fetch schema for {db_name}: {e}")
            return {"name": db_name, "properties": []}


def load_environment():
    """Load environment variables from .env file."""
    env_files = ['.env', '.env.docker']
    for env_file in env_files:
        if os.path.exists(env_file):
            load_dotenv(env_file)
            print(f"[OK] Loaded configuration from {env_file}")
            return True
    print("[WARNING] No .env file found")
    return False


def main():
    parser = argparse.ArgumentParser(description="Populate Notion databases with demo data")
    parser.add_argument('--force', action='store_true', help='Add data even if databases not empty')
    parser.add_argument('--validate', action='store_true', help='Only validate schemas')
    parser.add_argument('--dump-schema', action='store_true', help='Print current Notion DB schemas and exit')
    
    args = parser.parse_args()
    
    print("Vendor Database - Notion Population Tool")
    print("=" * 55)
    
    # Load environment
    load_environment()
    
    # Get credentials
    api_key = os.getenv('NOTION_API_KEY')
    vendors_db_id = os.getenv('VENDORS_DB_ID')
    parts_db_id = os.getenv('PARTS_DB_ID')
    scores_db_id = os.getenv('SCORES_DB_ID')
    
    if not all([api_key, vendors_db_id, parts_db_id]):
        print("[ERROR] Missing required environment variables:")
        print("   • NOTION_API_KEY, VENDORS_DB_ID, PARTS_DB_ID")
        print("[INFO] Create .env file with your Notion credentials")
        return 1
    
    try:
        # Initialize populator
        populator = NotionPopulator(api_key, vendors_db_id, parts_db_id, scores_db_id)
        
        # Test connection
        if not populator.test_connection():
            return 1
        
        # Dump schema and exit if requested
        if args.dump_schema:
            v_schema = populator.dump_database_schema(vendors_db_id, "Vendors")
            p_schema = populator.dump_database_schema(parts_db_id, "Parts")
            if scores_db_id:
                populator.dump_database_schema(scores_db_id, "Scores")
            print("\n[SUCCESS] Schema dump complete. Use these property names/types to align populate_databases.py.")
            return 0
        
        # Validate schemas
        if not populator.validate_all_schemas():
            return 1
        
        if args.validate:
            print("\n[SUCCESS] Validation successful! Ready for population.")
            return 0
        
        # Populate databases
        result = populator.populate_databases(force=args.force)
        
        return 0 if result['success'] else 1
    
    except KeyboardInterrupt:
        print(f"\n[CANCELLED] Cancelled by user.")
        return 1
    except Exception as e:
        print(f"\n[ERROR] {e}")
        return 1


# Helper functions for qualitative fields

def _region_reputation(region: str) -> float:
    table = {"US": 0.95, "EU": 0.92, "KR": 0.88, "MX": 0.80, "VN": 0.72, "IN": 0.72, "CN": 0.60}
    return table.get(region, 0.75)


def _us_alignment(region: str) -> float:
    table = {"US": 1.00, "EU": 0.95, "KR": 0.92, "MX": 0.88, "VN": 0.75, "IN": 0.78, "CN": 0.55}
    return table.get(region, 0.8)


def _credit_rating_from_score(score: float) -> str:
    # Simple mapping: >=0.9 A+, >=0.8 A, >=0.7 BBB, >=0.6 BB, else B
    if score >= 0.9:
        return "A+"
    if score >= 0.8:
        return "A"
    if score >= 0.7:
        return "BBB"
    if score >= 0.6:
        return "BB"
    return "B"


if __name__ == "__main__":
    sys.exit(main())