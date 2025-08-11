"""
Notion API integration layer for Synseer Vendor Logistics Database.
Handles CRUD operations with rate limiting, retries, and error handling.
"""

import os
import time
import json
from datetime import datetime, date
from typing import List, Optional, Dict, Any, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import structlog
from .models import Vendor, Part, VendorScore
from .utils import exponential_backoff

logger = structlog.get_logger()

class NotionAPIError(Exception):
    """Custom exception for Notion API errors."""
    pass

class NotionRepository:
    """Repository class for interacting with Notion databases."""
    
    def __init__(self):
        self.api_key = os.getenv('NOTION_API_KEY')
        if not self.api_key:
            raise ValueError("NOTION_API_KEY environment variable is required")
        
        self.vendors_db_id = os.getenv('VENDORS_DB_ID')
        self.parts_db_id = os.getenv('PARTS_DB_ID') 
        self.scores_db_id = os.getenv('SCORES_DB_ID')
        
        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        # Rate limiting: Notion allows ~3 requests per second
        self.last_request_time = 0
        self.min_request_interval = 0.35  # 350ms between requests
        
        # Session with retry strategy
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
    def _rate_limit(self):
        """Ensure we don't exceed Notion's rate limits."""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    @exponential_backoff(max_retries=3)
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with rate limiting and error handling."""
        self._rate_limit()
        
        url = f"{self.base_url}{endpoint}"
        response = self.session.request(method, url, headers=self.headers, **kwargs)
        
        if response.status_code == 429:
            # Rate limited - wait and retry
            wait_time = int(response.headers.get('Retry-After', 5))
            logger.warning(f"Rate limited, waiting {wait_time}s")
            time.sleep(wait_time)
            raise requests.exceptions.RequestException("Rate limited")
        
        if not response.ok:
            error_msg = f"Notion API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            raise NotionAPIError(error_msg)
        
        return response.json()
    
    def _ensure_database_exists(self, db_id: str, schema: Dict[str, Any]) -> str:
        """Ensure database exists and has correct schema, create if needed."""
        if not db_id:
            return self._create_database(schema)
        
        try:
            # Try to retrieve the database
            self._make_request("GET", f"/databases/{db_id}")
            return db_id
        except NotionAPIError:
            # Database doesn't exist, create it
            logger.info(f"Database {db_id} not found, creating new one")
            return self._create_database(schema)
    
    def _create_database(self, schema: Dict[str, Any]) -> str:
        """Create a new Notion database with the given schema."""
        # This would typically require a parent page ID
        # For now, we'll assume the database IDs are provided
        raise NotImplementedError("Database creation requires manual setup in Notion")
    
    def setup_databases(self):
        """Initialize and validate all required databases."""
        vendors_schema = {
            "title": "Vendors",
            "properties": {
                "Name": {"title": {}},
                "Region": {"select": {"options": [
                    {"name": "US"}, {"name": "EU"}, {"name": "KR"}, 
                    {"name": "CN"}, {"name": "VN"}, {"name": "MX"}, {"name": "IN"}
                ]}},
                "Reliability Score": {"number": {"format": "percent"}},
                "Contact Email": {"email": {}},
                "Last Verified": {"date": {}},
                "Created Time": {"created_time": {}}
            }
        }
        
        parts_schema = {
            "title": "Parts",
            "properties": {
                "Component Name": {"title": {}},
                "Vendor": {"relation": {"database_id": self.vendors_db_id}},
                "ODM Destination": {"rich_text": {}},
                "ODM Region": {"rich_text": {}},
                "Unit Price": {"number": {"format": "dollar"}},
                "Freight Cost": {"number": {"format": "dollar"}},
                "Tariff Rate": {"number": {"format": "percent"}},
                "Lead Time (weeks)": {"number": {}},
                "Transit Days": {"number": {}},
                "Shipping Mode": {"select": {"options": [
                    {"name": "Air"}, {"name": "Ocean"}, {"name": "Ground"}
                ]}},
                "Monthly Capacity": {"number": {}},
                "Last Verified": {"date": {}},
                "Notes": {"rich_text": {}},
                "Created Time": {"created_time": {}}
            }
        }
        
        scores_schema = {
            "title": "Vendor Scores",
            "properties": {
                "Vendor": {"relation": {"database_id": self.vendors_db_id}},
                "Total Cost Score": {"number": {"format": "percent"}},
                "Total Time Score": {"number": {"format": "percent"}},
                "Reliability Score": {"number": {"format": "percent"}},
                "Capacity Score": {"number": {"format": "percent"}},
                "Final Score": {"number": {"format": "percent"}},
                "Weights JSON": {"rich_text": {}},
                "Inputs JSON": {"rich_text": {}},
                "Computed At": {"created_time": {}},
                "Snapshot Date": {"date": {}}
            }
        }
        
        logger.info("Setting up Notion databases")
        # Note: In production, these database IDs should be provided
        # Database creation requires manual setup or parent page access
    
    # Vendor CRUD operations
    def create_vendor(self, vendor: Vendor) -> str:
        """Create a new vendor record."""
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
        vendor_id = response["id"]
        logger.info(f"Created vendor {vendor.name} with ID {vendor_id}")
        return vendor_id
    
    def get_vendor(self, vendor_id: str) -> Optional[Vendor]:
        """Retrieve a vendor by ID."""
        try:
            response = self._make_request("GET", f"/pages/{vendor_id}")
            return self._parse_vendor(response)
        except NotionAPIError:
            return None
    
    def list_vendors(self, limit: int = 100) -> List[Vendor]:
        """List all vendors."""
        data = {"page_size": min(limit, 100)}
        response = self._make_request("POST", f"/databases/{self.vendors_db_id}/query", json=data)
        
        vendors = []
        for page in response["results"]:
            vendor = self._parse_vendor(page)
            if vendor:
                vendors.append(vendor)
        
        return vendors
    
    def _parse_vendor(self, page: Dict[str, Any]) -> Optional[Vendor]:
        """Parse Notion page data into Vendor object."""
        try:
            props = page["properties"]
            
            return Vendor(
                id=page["id"],
                name=self._get_title(props.get("Name")),
                region=self._get_select(props.get("Region")),
                reliability_score=self._get_number(props.get("Reliability Score")) or 0.0,
                contact_email=self._get_email(props.get("Contact Email")),
                last_verified=self._get_date(props.get("Last Verified")),
                created_time=self._get_created_time(props.get("Created Time"))
            )
        except Exception as e:
            logger.error(f"Error parsing vendor: {e}")
            return None
    
    # Part CRUD operations  
    def create_part(self, part: Part) -> str:
        """Create a new part record."""
        data = {
            "parent": {"database_id": self.parts_db_id},
            "properties": {
                "Component Name": {"title": [{"text": {"content": part.component_name}}]},
                "Vendor": {"relation": [{"id": part.vendor_id}]} if part.vendor_id else None,
                "ODM Destination": {"rich_text": [{"text": {"content": part.odm_destination}}]},
                "ODM Region": {"rich_text": [{"text": {"content": part.odm_region}}]},
                "Unit Price": {"number": part.unit_price},
                "Freight Cost": {"number": part.freight_cost},
                "Tariff Rate": {"number": part.tariff_rate_pct / 100},  # Convert to decimal
                "Lead Time (weeks)": {"number": part.lead_time_weeks},
                "Transit Days": {"number": part.transit_days},
                "Shipping Mode": {"select": {"name": part.shipping_mode}} if part.shipping_mode else None,
                "Monthly Capacity": {"number": part.monthly_capacity},
                "Last Verified": {"date": {"start": part.last_verified.isoformat()}} if part.last_verified else None,
                "Notes": {"rich_text": [{"text": {"content": part.notes}}]} if part.notes else None
            }
        }
        
        # Remove None values
        data["properties"] = {k: v for k, v in data["properties"].items() if v is not None}
        
        response = self._make_request("POST", f"/pages", json=data)
        part_id = response["id"]
        logger.info(f"Created part {part.component_name} with ID {part_id}")
        return part_id
    
    def list_parts_by_vendor(self, vendor_id: str) -> List[Part]:
        """List all parts for a specific vendor."""
        data = {
            "filter": {
                "property": "Vendor",
                "relation": {"contains": vendor_id}
            }
        }
        
        response = self._make_request("POST", f"/databases/{self.parts_db_id}/query", json=data)
        
        parts = []
        for page in response["results"]:
            part = self._parse_part(page)
            if part:
                parts.append(part)
        
        return parts
    
    def _parse_part(self, page: Dict[str, Any]) -> Optional[Part]:
        """Parse Notion page data into Part object."""
        try:
            props = page["properties"]
            
            return Part(
                id=page["id"],
                component_name=self._get_title(props.get("Component Name")),
                vendor_id=self._get_relation_id(props.get("Vendor")),
                odm_destination=self._get_rich_text(props.get("ODM Destination")),
                odm_region=self._get_rich_text(props.get("ODM Region")),
                unit_price=self._get_number(props.get("Unit Price")) or 0.0,
                freight_cost=self._get_number(props.get("Freight Cost")) or 0.0,
                tariff_rate_pct=(self._get_number(props.get("Tariff Rate")) or 0.0) * 100,  # Convert back to percentage
                lead_time_weeks=int(self._get_number(props.get("Lead Time (weeks)")) or 0),
                transit_days=int(self._get_number(props.get("Transit Days")) or 0),
                shipping_mode=self._get_select(props.get("Shipping Mode")),
                monthly_capacity=int(self._get_number(props.get("Monthly Capacity")) or 0),
                last_verified=self._get_date(props.get("Last Verified")),
                notes=self._get_rich_text(props.get("Notes")),
                timestamp=self._get_created_time(props.get("Created Time"))
            )
        except Exception as e:
            logger.error(f"Error parsing part: {e}")
            return None
    
    # Helper methods for parsing Notion properties
    def _get_title(self, prop: Optional[Dict]) -> str:
        """Extract title from Notion property."""
        if not prop or not prop.get("title"):
            return ""
        return prop["title"][0]["text"]["content"] if prop["title"] else ""
    
    def _get_rich_text(self, prop: Optional[Dict]) -> str:
        """Extract rich text from Notion property."""
        if not prop or not prop.get("rich_text"):
            return ""
        return prop["rich_text"][0]["text"]["content"] if prop["rich_text"] else ""
    
    def _get_select(self, prop: Optional[Dict]) -> str:
        """Extract select value from Notion property."""
        if not prop or not prop.get("select"):
            return ""
        return prop["select"]["name"] if prop["select"] else ""
    
    def _get_number(self, prop: Optional[Dict]) -> Optional[float]:
        """Extract number from Notion property."""
        if not prop:
            return None
        return prop.get("number")
    
    def _get_email(self, prop: Optional[Dict]) -> str:
        """Extract email from Notion property."""
        if not prop:
            return ""
        return prop.get("email", "")
    
    def _get_date(self, prop: Optional[Dict]) -> Optional[date]:
        """Extract date from Notion property."""
        if not prop or not prop.get("date"):
            return None
        date_str = prop["date"]["start"]
        return datetime.fromisoformat(date_str).date() if date_str else None
    
    def _get_created_time(self, prop: Optional[Dict]) -> Optional[datetime]:
        """Extract created time from Notion property."""
        if not prop:
            return None
        time_str = prop.get("created_time")
        return datetime.fromisoformat(time_str.replace('Z', '+00:00')) if time_str else None
    
    def _get_relation_id(self, prop: Optional[Dict]) -> str:
        """Extract first relation ID from Notion property."""
        if not prop or not prop.get("relation"):
            return ""
        return prop["relation"][0]["id"] if prop["relation"] else ""