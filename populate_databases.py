#!/usr/bin/env python3
"""
Standalone Notion Database Population Script for Synseer Vendor Database
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
    last_verified: Optional[date] = None
    timestamp: Optional[datetime] = None
    notes: str = ""


def generate_demo_data() -> Tuple[List[Vendor], List[Part]]:
    """Generate realistic vendor and part demo data."""
    
    # Vendor templates based on real supply chain scenarios
    vendor_templates = [
        # Asian suppliers (high volume, competitive pricing)
        {"name": "Batreon", "region": "KR", "reliability": 0.85, "email": "sourcing@batreon.kr"},
        {"name": "PowerCell KR", "region": "KR", "reliability": 0.82, "email": "exports@powercell.co.kr"},
        {"name": "Seoul Battery Co", "region": "KR", "reliability": 0.78, "email": "global@seoulbattery.com"},
        {"name": "Shenzhen Energy", "region": "CN", "reliability": 0.75, "email": "sales@szenergy.cn"},
        {"name": "BYD Components", "region": "CN", "reliability": 0.80, "email": "oem@byd.com"},
        {"name": "CATL Supply", "region": "CN", "reliability": 0.88, "email": "partnerships@catl.com"},
        {"name": "Panasonic Shenzhen", "region": "CN", "reliability": 0.92, "email": "b2b@panasonic.cn"},
        {"name": "VinFast Components", "region": "VN", "reliability": 0.72, "email": "supply@vinfast.vn"},
        {"name": "Hanoi Power", "region": "VN", "reliability": 0.68, "email": "export@hanoipower.vn"},
        {"name": "Vietnam Energy Co", "region": "VN", "reliability": 0.71, "email": "sales@vnenergy.com"},
        
        # European suppliers (premium quality, higher cost)
        {"name": "EuroEnergy", "region": "EU", "reliability": 0.91, "email": "procurement@euroenergy.de"},
        {"name": "Nordic Power", "region": "EU", "reliability": 0.89, "email": "sales@nordicpower.se"},
        {"name": "Alpine Components", "region": "EU", "reliability": 0.86, "email": "export@alpine-comp.at"},
        {"name": "French Cell Tech", "region": "EU", "reliability": 0.84, "email": "b2b@frenchcell.fr"},
        {"name": "Italian Energy", "region": "EU", "reliability": 0.79, "email": "global@italenergy.it"},
        
        # North American suppliers (balanced performance)
        {"name": "Tesla Energy", "region": "US", "reliability": 0.94, "email": "supply@tesla.com"},
        {"name": "GM Components", "region": "US", "reliability": 0.87, "email": "sourcing@gm.com"},
        {"name": "Ford Energy", "region": "US", "reliability": 0.83, "email": "partnerships@ford.com"},
        {"name": "Boston Power", "region": "US", "reliability": 0.81, "email": "oem@bostonpower.com"},
        {"name": "California Cells", "region": "US", "reliability": 0.77, "email": "sales@calcells.com"},
        {"name": "Tijuana Power", "region": "MX", "reliability": 0.74, "email": "export@tjpower.mx"},
        {"name": "Mexico Energy", "region": "MX", "reliability": 0.70, "email": "global@mexenergy.com"},
        {"name": "Guadalajara Tech", "region": "MX", "reliability": 0.73, "email": "sales@gdltech.mx"},
        
        # Indian suppliers (emerging market)
        {"name": "Mumbai Power", "region": "IN", "reliability": 0.69, "email": "export@mumbaipower.in"},
        {"name": "Delhi Components", "region": "IN", "reliability": 0.66, "email": "sales@delhicomp.in"},
        {"name": "Bangalore Energy", "region": "IN", "reliability": 0.71, "email": "global@blrenergy.in"},
        {"name": "Chennai Cells", "region": "IN", "reliability": 0.67, "email": "oem@chennaicells.in"},
        {"name": "Hyderabad Tech", "region": "IN", "reliability": 0.73, "email": "export@hydtech.in"},
        {"name": "Pune Power", "region": "IN", "reliability": 0.68, "email": "partnerships@punepower.in"},
        {"name": "Kolkata Energy", "region": "IN", "reliability": 0.65, "email": "sales@kolkataenergy.in"}
    ]
    
    # Generate vendors with realistic verification dates
    vendors = []
    base_date = date(2025, 6, 1)
    
    for i, template in enumerate(vendor_templates):
        # Vary verification dates - some recent, some stale
        days_ago = random.randint(1, 25) if i < 20 else random.randint(35, 90)
        
        vendor = Vendor(
            id=f"vendor_{i+1:02d}",
            name=template["name"],
            region=template["region"],
            reliability_score=template["reliability"] + random.uniform(-0.05, 0.05),
            contact_email=template["email"],
            last_verified=base_date - timedelta(days=days_ago),
            created_time=datetime.now() - timedelta(days=random.randint(30, 365))
        )
        vendors.append(vendor)
    
    # Component types based on supply chain requirements
    component_types = [
        # Batteries (primary focus)
        "Li-ion cell 18650", "Li-ion cell 21700", "Li-ion cell 302030", "Li-ion cell 402030",
        "Li-ion pouch 5Ah", "Li-ion pouch 10Ah", "LiFePO4 cell 32650", "Li-poly 1000mAh",
        "Li-poly 2000mAh", "Li-poly 3000mAh", "Solid-state 500mAh", "NMC cell 3500mAh",
        
        # Sensors
        "Heart Rate Sensor", "SpO2 Sensor", "Temperature Sensor", "Accelerometer 6-axis",
        "Gyroscope 3-axis", "Pressure Sensor", "Ambient Light Sensor", "UV Sensor",
        "ECG Sensor", "EEG Sensor", "EMG Sensor", "Bioimpedance Sensor",
        
        # Chips/ICs  
        "ARM Cortex-M4", "ARM Cortex-M7", "nRF52840 BLE", "ESP32-S3", 
        "Qualcomm WCN3990", "MediaTek MT2523", "STM32 MCU", "NXP i.MX RT",
        "TI CC2640", "Nordic nRF91", "Realtek RTL8720", "Broadcom BCM4343",
        
        # Additional components
        "OLED Display 1.3\"", "E-ink Display", "Haptic Motor", "Speaker 8ohm",
        "Microphone MEMS", "Antenna 2.4GHz", "Charging Coil", "Connector USB-C",
        "Flexible PCB", "Ceramic Substrate", "Silicone Overmold", "Metal Housing"
    ]
    
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
    
    # Generate parts
    parts = []
    part_id = 1
    
    for vendor in vendors:
        num_parts = random.choices([1, 2, 3, 4], weights=[10, 40, 35, 15])[0]
        
        for _ in range(num_parts):
            component = random.choice(component_types)
            odm_dest, odm_region = random.choice(odm_destinations)
            
            # Component-based pricing
            if "Li-ion" in component or "Li-poly" in component or "LiFePO4" in component:
                base_price = random.uniform(0.80, 8.50)
            elif "Sensor" in component:
                base_price = random.uniform(1.20, 15.00)
            elif any(chip in component for chip in ["ARM", "nRF", "ESP32", "Qualcomm"]):
                base_price = random.uniform(3.50, 25.00)
            else:
                base_price = random.uniform(0.30, 12.00)
            
            unit_price = base_price * region_multiplier[vendor.region]
            
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
            
            # Capacity based on supplier size
            if vendor.reliability_score > 0.90:
                capacity = random.randint(50000, 200000)
            elif vendor.reliability_score > 0.75:
                capacity = random.randint(15000, 80000)
            else:
                capacity = random.randint(5000, 30000)
            
            # Verification date
            part_verified = vendor.last_verified
            if random.random() < 0.3:  # 30% chance of more recent part data
                part_verified = vendor.last_verified + timedelta(days=random.randint(1, 10))
                if part_verified > date.today():
                    part_verified = date.today()
            
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
        
        print(f"🔗 Initialized Notion API connection")
    
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
            print(f"⏳ Rate limited, waiting {wait_time}s...")
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
            print("✅ Connected to Vendors database")
            
            self._make_request("GET", f"/databases/{self.parts_db_id}")
            print("✅ Connected to Parts database")
            
            if self.scores_db_id:
                self._make_request("GET", f"/databases/{self.scores_db_id}")
                print("✅ Connected to Scores database")
            
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def validate_schema(self, db_id: str, db_name: str, required_props: Dict[str, str]) -> bool:
        """Validate database schema."""
        try:
            print(f"\n🔍 Validating {db_name} database...")
            response = self._make_request("GET", f"/databases/{db_id}")
            properties = response.get('properties', {})
            
            valid = True
            for prop_name, expected_type in required_props.items():
                if prop_name not in properties:
                    print(f"  ❌ Missing: {prop_name} ({expected_type})")
                    valid = False
                else:
                    actual_type = properties[prop_name]['type']
                    if actual_type == expected_type:
                        print(f"  ✅ {prop_name}")
                    else:
                        print(f"  ⚠️  {prop_name}: expected {expected_type}, found {actual_type}")
                        if not ((expected_type == 'rich_text' and actual_type == 'text') or
                               (expected_type == 'text' and actual_type == 'rich_text')):
                            valid = False
            
            return valid
        except Exception as e:
            print(f"❌ Schema validation failed: {e}")
            return False
    
    def validate_all_schemas(self) -> bool:
        """Validate all database schemas."""
        print("🔍 Validating database schemas...")
        
        vendors_schema = {
            "Name": "title", "Region": "select", "Reliability Score": "number",
            "Contact Email": "email", "Last Verified": "date"
        }
        
        parts_schema = {
            "Component Name": "title", "Vendor": "relation", "ODM Destination": "rich_text",
            "ODM Region": "rich_text", "Unit Price": "number", "Freight Cost": "number",
            "Tariff Rate": "number", "Lead Time (weeks)": "number", "Transit Days": "number",
            "Shipping Mode": "select", "Monthly Capacity": "number", "Last Verified": "date"
        }
        
        vendors_valid = self.validate_schema(self.vendors_db_id, "Vendors", vendors_schema)
        parts_valid = self.validate_schema(self.parts_db_id, "Parts", parts_schema)
        
        all_valid = vendors_valid and parts_valid
        
        if all_valid:
            print("\n🎉 All schemas valid!")
        else:
            print("\n⚠️  Schema issues found. Fix before populating data.")
        
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
    
    def create_vendor(self, vendor: Vendor) -> str:
        """Create vendor in Notion."""
        data = {
            "parent": {"database_id": self.vendors_db_id},
            "properties": {
                "Name": {"title": [{"text": {"content": vendor.name}}]},
                "Region": {"select": {"name": vendor.region}},
                "Reliability Score": {"number": vendor.reliability_score},
                "Contact Email": {"email": vendor.contact_email} if vendor.contact_email else None,
                "Last Verified": {"date": {"start": vendor.last_verified.isoformat()}} if vendor.last_verified else None
            }
        }
        
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
                "Last Verified": {"date": {"start": part.last_verified.isoformat()}} if part.last_verified else None
            }
        }
        
        # Remove None values
        data["properties"] = {k: v for k, v in data["properties"].items() if v is not None}
        
        response = self._make_request("POST", f"/pages", json=data)
        return response["id"]
    
    def populate_databases(self, force: bool = False) -> Dict[str, Any]:
        """Populate databases with demo data."""
        print("\n🚀 Starting database population...")
        
        # Check existing data
        existing_vendors, existing_parts = self.check_existing_data()
        
        if (existing_vendors > 0 or existing_parts > 0) and not force:
            print(f"\n⚠️  Databases contain data: {existing_vendors} vendors, {existing_parts} parts")
            print(f"💡 Use --force flag to add more data")
            return {"success": False, "message": "Data exists. Use --force to continue."}
        
        # Generate demo data
        print("\n📊 Generating demo data...")
        vendors, parts = generate_demo_data()
        print(f"Generated {len(vendors)} vendors and {len(parts)} parts")
        
        # Population tracking
        created_vendors = 0
        created_parts = 0
        vendor_id_map = {}
        errors = []
        
        # Create vendors
        print(f"\n🏢 Creating {len(vendors)} vendors...")
        for i, vendor in enumerate(vendors):
            try:
                real_vendor_id = self.create_vendor(vendor)
                vendor_id_map[vendor.id] = real_vendor_id
                created_vendors += 1
                progress = ((i + 1) / len(vendors)) * 100
                print(f"  ✅ {vendor.name} ({i+1}/{len(vendors)}) - {progress:.0f}%")
            except Exception as e:
                errors.append(f"Vendor {vendor.name}: {e}")
                print(f"  ❌ Failed: {vendor.name}")
        
        # Create parts
        print(f"\n🔧 Creating {len(parts)} parts...")
        for i, part in enumerate(parts):
            try:
                if part.vendor_id in vendor_id_map:
                    part.vendor_id = vendor_id_map[part.vendor_id]
                    self.create_part(part)
                    created_parts += 1
                    progress = ((i + 1) / len(parts)) * 100
                    print(f"  ✅ {part.component_name} ({i+1}/{len(parts)}) - {progress:.0f}%")
                else:
                    errors.append(f"Part {part.component_name}: vendor not found")
            except Exception as e:
                errors.append(f"Part {part.component_name}: {e}")
                print(f"  ❌ Failed: {part.component_name}")
        
        # Summary
        success = created_vendors > 0 and created_parts > 0
        print(f"\n📈 Population complete!")
        print(f"   ✅ Vendors: {created_vendors}/{len(vendors)}")
        print(f"   ✅ Parts: {created_parts}/{len(parts)}")
        print(f"   ⚠️  Errors: {len(errors)}")
        
        if success:
            print(f"\n🎉 Success! Your Notion databases now contain realistic demo data.")
            print(f"🚀 Ready to run your Synseer Vendor Database application!")
        
        return {
            "success": success,
            "vendors_created": created_vendors,
            "parts_created": created_parts,
            "errors": len(errors)
        }


def load_environment():
    """Load environment variables from .env file."""
    env_files = ['.env', '.env.docker']
    for env_file in env_files:
        if os.path.exists(env_file):
            load_dotenv(env_file)
            print(f"✅ Loaded configuration from {env_file}")
            return True
    print("⚠️  No .env file found")
    return False


def main():
    parser = argparse.ArgumentParser(description="Populate Notion databases with demo data")
    parser.add_argument('--force', action='store_true', help='Add data even if databases not empty')
    parser.add_argument('--validate', action='store_true', help='Only validate schemas')
    
    args = parser.parse_args()
    
    print("🏗️  Synseer Vendor Database - Notion Population Tool")
    print("=" * 55)
    
    # Load environment
    load_environment()
    
    # Get credentials
    api_key = os.getenv('NOTION_API_KEY')
    vendors_db_id = os.getenv('VENDORS_DB_ID')
    parts_db_id = os.getenv('PARTS_DB_ID')
    scores_db_id = os.getenv('SCORES_DB_ID')
    
    if not all([api_key, vendors_db_id, parts_db_id]):
        print("❌ Missing required environment variables:")
        print("   • NOTION_API_KEY, VENDORS_DB_ID, PARTS_DB_ID")
        print("💡 Create .env file with your Notion credentials")
        return 1
    
    try:
        # Initialize populator
        populator = NotionPopulator(api_key, vendors_db_id, parts_db_id, scores_db_id)
        
        # Test connection
        if not populator.test_connection():
            return 1
        
        # Validate schemas
        if not populator.validate_all_schemas():
            return 1
        
        if args.validate:
            print("\n✅ Validation successful! Ready for population.")
            return 0
        
        # Populate databases
        result = populator.populate_databases(force=args.force)
        
        return 0 if result['success'] else 1
    
    except KeyboardInterrupt:
        print(f"\n⏹️  Cancelled by user.")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())