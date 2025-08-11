"""
Data models for the Synseer Vendor Logistics Database.
Based on the Component → ODM Logistics schema from the Vendor Selection Ideas document.
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from dataclasses_json import dataclass_json
import json

@dataclass_json
@dataclass
class Vendor:
    """Vendor entity matching Notion database schema."""
    id: Optional[str] = None
    name: str = ""
    region: str = ""  # US, EU, KR, CN, VN, MX, IN
    reliability_score: float = 0.0  # 0.0-1.0
    contact_email: str = ""
    last_verified: Optional[date] = None
    created_time: Optional[datetime] = None
    
    def is_stale(self, days_threshold: int = 30) -> bool:
        """Check if vendor data is stale based on last_verified date."""
        if not self.last_verified:
            return True
        return (date.today() - self.last_verified).days > days_threshold

@dataclass_json
@dataclass  
class Part:
    """Part/Component entity matching Component → ODM Logistics table."""
    id: Optional[str] = None
    component_name: str = ""  # e.g., "Li-ion cell 302030"
    vendor_id: str = ""  # Relation to Vendor
    vendor_name: str = ""  # For display purposes
    
    # ODM Information
    odm_destination: str = ""  # e.g., "PDGV"
    odm_region: str = ""  # e.g., "California, USA"
    
    # Pricing (FOB)
    unit_price: float = 0.0  # Quoted Unit Price (FOB)
    freight_cost: float = 0.0  # Freight Cost ($/unit)
    tariff_rate_pct: float = 0.0  # Tariff Rate (%)
    
    # Timing
    lead_time_weeks: int = 0  # Lead Time (weeks)
    transit_days: int = 0  # Transit Time (days)
    shipping_mode: str = ""  # Air, Ocean, Ground
    
    # Capacity
    monthly_capacity: int = 0  # Monthly Capacity (units)
    
    # Metadata
    timestamp: Optional[datetime] = None
    last_verified: Optional[date] = None
    notes: str = ""
    
    @property
    def total_landed_cost(self) -> float:
        """Calculate total landed cost: FOB + freight + tariff."""
        tariff_amount = self.unit_price * (self.tariff_rate_pct / 100)
        return self.unit_price + self.freight_cost + tariff_amount
    
    @property
    def total_time_days(self) -> int:
        """Calculate total time in days: lead time + transit time."""
        return (self.lead_time_weeks * 7) + self.transit_days

@dataclass_json
@dataclass
class VendorScore:
    """Vendor scoring snapshot for historical tracking."""
    id: Optional[str] = None
    vendor_id: str = ""
    vendor_name: str = ""  # For display
    
    # Individual pillar scores (0.0-1.0)
    total_cost_score: float = 0.0
    total_time_score: float = 0.0
    reliability_score: float = 0.0
    capacity_score: float = 0.0
    
    # Final weighted score (0.0-1.0)
    final_score: float = 0.0
    
    # Configuration used
    weights_json: str = ""  # JSON string of weights used
    inputs_json: str = ""   # JSON string of input data used
    
    # Metadata
    computed_at: Optional[datetime] = None
    snapshot_date: Optional[date] = None  # Monthly snapshot identifier
    
    @property
    def weights(self) -> Dict[str, float]:
        """Parse weights from JSON string."""
        try:
            return json.loads(self.weights_json) if self.weights_json else {}
        except json.JSONDecodeError:
            return {}
    
    @weights.setter
    def weights(self, value: Dict[str, float]):
        """Set weights as JSON string."""
        self.weights_json = json.dumps(value)
    
    @property
    def inputs(self) -> Dict[str, Any]:
        """Parse inputs from JSON string."""
        try:
            return json.loads(self.inputs_json) if self.inputs_json else {}
        except json.JSONDecodeError:
            return {}
    
    @inputs.setter
    def inputs(self, value: Dict[str, Any]):
        """Set inputs as JSON string."""
        self.inputs_json = json.dumps(value, default=str)

@dataclass_json
@dataclass
class ScoringWeights:
    """Default scoring weights configuration."""
    total_cost: float = 0.4
    total_time: float = 0.3
    reliability: float = 0.2
    capacity: float = 0.1
    
    def normalize(self):
        """Ensure weights sum to 1.0."""
        total = self.total_cost + self.total_time + self.reliability + self.capacity
        if total > 0:
            self.total_cost /= total
            self.total_time /= total
            self.reliability /= total
            self.capacity /= total
    
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            'total_cost': self.total_cost,
            'total_time': self.total_time,
            'reliability': self.reliability,
            'capacity': self.capacity
        }

@dataclass_json
@dataclass
class RiskFlag:
    """Risk indicator for vendors."""
    type: str = ""  # "cost_spike", "delay_risk", "capacity_shortfall", "stale_data"
    severity: str = ""  # "low", "medium", "high"
    description: str = ""
    value: Optional[float] = None  # Associated metric value
    threshold: Optional[float] = None  # Threshold that triggered the flag

@dataclass_json
@dataclass
class VendorAnalysis:
    """Complete vendor analysis with scores, trends, and risks."""
    vendor: Vendor
    parts: List[Part] = field(default_factory=list)
    current_score: Optional[VendorScore] = None
    historical_scores: List[VendorScore] = field(default_factory=list)
    risk_flags: List[RiskFlag] = field(default_factory=list)
    
    @property
    def avg_landed_cost(self) -> float:
        """Average landed cost across all parts."""
        if not self.parts:
            return 0.0
        return sum(p.total_landed_cost for p in self.parts) / len(self.parts)
    
    @property
    def avg_total_time(self) -> float:
        """Average total time across all parts."""
        if not self.parts:
            return 0.0
        return sum(p.total_time_days for p in self.parts) / len(self.parts)
    
    @property
    def total_monthly_capacity(self) -> int:
        """Total monthly capacity across all parts."""
        return sum(p.monthly_capacity for p in self.parts)