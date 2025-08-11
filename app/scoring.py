"""
Scoring engine for vendor evaluation based on the Synseer methodology.
Implements the normalized scoring formula: Final = Σ w_p * S_p,v
"""

from typing import List, Dict, Optional, Tuple
from datetime import date, datetime
import statistics
import structlog
from .models import Vendor, Part, VendorScore, VendorAnalysis, ScoringWeights, RiskFlag
from .utils import normalize_min_max, winsorize, calculate_month_over_month_change, safe_divide

logger = structlog.get_logger()

class ScoringEngine:
    """Core scoring engine implementing Synseer's vendor evaluation methodology."""
    
    def __init__(self, weights: Optional[ScoringWeights] = None):
        """Initialize scoring engine with default or custom weights."""
        self.weights = weights or ScoringWeights()
        self.weights.normalize()  # Ensure weights sum to 1.0
        
        # Risk detection thresholds
        self.cost_spike_threshold = 0.10  # 10% MoM increase
        self.delay_spike_threshold = 3    # Additional days
        self.capacity_shortfall_threshold = 0.8  # 80% utilization warning
        self.staleness_threshold_days = 30
    
    def score_vendors(self, vendors: List[Vendor], parts_by_vendor: Dict[str, List[Part]], 
                     historical_scores: Optional[Dict[str, List[VendorScore]]] = None) -> List[VendorAnalysis]:
        """
        Score all vendors and return ranked analysis.
        
        Args:
            vendors: List of vendor entities
            parts_by_vendor: Dict mapping vendor_id to list of parts
            historical_scores: Optional historical scores for trend analysis
        
        Returns:
            List of VendorAnalysis objects ranked by final score (descending)
        """
        logger.info(f"Scoring {len(vendors)} vendors with weights: {self.weights.to_dict()}")
        
        analyses = []
        
        # Collect all metrics for normalization
        all_costs = []
        all_times = []
        all_capacities = []
        all_reliability = []
        
        vendor_metrics = {}
        
        for vendor in vendors:
            vendor_parts = parts_by_vendor.get(vendor.id, [])
            if not vendor_parts:
                continue
                
            # Calculate aggregate metrics for this vendor
            avg_cost = self._calculate_avg_landed_cost(vendor_parts)
            avg_time = self._calculate_avg_total_time(vendor_parts)
            total_capacity = sum(part.monthly_capacity for part in vendor_parts)
            reliability = vendor.reliability_score
            
            vendor_metrics[vendor.id] = {
                'avg_cost': avg_cost,
                'avg_time': avg_time,
                'total_capacity': total_capacity,
                'reliability': reliability,
                'vendor': vendor,
                'parts': vendor_parts
            }
            
            all_costs.append(avg_cost)
            all_times.append(avg_time)
            all_capacities.append(total_capacity)
            all_reliability.append(reliability)
        
        if not vendor_metrics:
            logger.warning("No vendors with parts found for scoring")
            return []
        
        # Winsorize extreme outliers
        all_costs = winsorize(all_costs)
        all_times = winsorize(all_times)
        all_capacities = winsorize(all_capacities)
        
        # Normalize metrics to 0-1 scale
        normalized_costs = normalize_min_max(all_costs, invert=True)  # Lower cost is better
        normalized_times = normalize_min_max(all_times, invert=True)  # Lower time is better  
        normalized_capacities = normalize_min_max(all_capacities, invert=False)  # Higher capacity is better
        normalized_reliability = normalize_min_max(all_reliability, invert=False)  # Higher reliability is better
        
        # Calculate scores for each vendor
        for i, (vendor_id, metrics) in enumerate(vendor_metrics.items()):
            vendor = metrics['vendor']
            parts = metrics['parts']
            
            # Individual pillar scores (0-1)
            cost_score = normalized_costs[i]
            time_score = normalized_times[i]
            capacity_score = normalized_capacities[i]
            reliability_score = normalized_reliability[i]
            
            # Calculate final weighted score
            final_score = (
                self.weights.total_cost * cost_score +
                self.weights.total_time * time_score +
                self.weights.reliability * reliability_score +
                self.weights.capacity * capacity_score
            )
            
            # Create vendor score record
            vendor_score = VendorScore(
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                total_cost_score=cost_score,
                total_time_score=time_score,
                reliability_score=reliability_score,
                capacity_score=capacity_score,
                final_score=final_score,
                computed_at=datetime.now(),
                snapshot_date=date.today()
            )
            
            # Set weights and inputs for transparency
            vendor_score.weights = self.weights.to_dict()
            vendor_score.inputs = {
                'avg_landed_cost': metrics['avg_cost'],
                'avg_total_time': metrics['avg_time'],
                'total_capacity': metrics['total_capacity'],
                'reliability': metrics['reliability'],
                'part_count': len(parts)
            }
            
            # Generate risk flags
            historical_vendor_scores = historical_scores.get(vendor.id, []) if historical_scores else []
            risk_flags = self._generate_risk_flags(vendor, parts, vendor_score, historical_vendor_scores)
            
            # Create comprehensive analysis
            analysis = VendorAnalysis(
                vendor=vendor,
                parts=parts,
                current_score=vendor_score,
                historical_scores=historical_vendor_scores,
                risk_flags=risk_flags
            )
            
            analyses.append(analysis)
        
        # Sort by final score (descending)
        analyses.sort(key=lambda x: x.current_score.final_score, reverse=True)
        
        logger.info(f"Scored {len(analyses)} vendors. Top vendor: {analyses[0].vendor.name} ({analyses[0].current_score.final_score:.3f})")
        return analyses
    
    def _calculate_avg_landed_cost(self, parts: List[Part]) -> float:
        """Calculate average landed cost across all parts for a vendor."""
        if not parts:
            return 0.0
        return statistics.mean([part.total_landed_cost for part in parts])
    
    def _calculate_avg_total_time(self, parts: List[Part]) -> float:
        """Calculate average total time (lead + transit) across all parts for a vendor."""
        if not parts:
            return 0.0
        return statistics.mean([part.total_time_days for part in parts])
    
    def _generate_risk_flags(self, vendor: Vendor, parts: List[Part], 
                           current_score: VendorScore, historical_scores: List[VendorScore]) -> List[RiskFlag]:
        """Generate risk flags based on current data and trends."""
        flags = []
        
        # Data staleness risk
        if vendor.is_stale(self.staleness_threshold_days):
            days_stale = (date.today() - vendor.last_verified).days if vendor.last_verified else float('inf')
            flags.append(RiskFlag(
                type="stale_data",
                severity="high" if days_stale > 60 else "medium",
                description=f"Vendor data not verified for {days_stale} days",
                value=days_stale,
                threshold=self.staleness_threshold_days
            ))
        
        # Cost spike risk (requires historical data)
        if len(historical_scores) >= 2:
            previous_score = historical_scores[-2]  # Second to last
            cost_change = calculate_month_over_month_change(
                current_score.inputs.get('avg_landed_cost', 0),
                previous_score.inputs.get('avg_landed_cost', 0)
            )
            
            if cost_change > self.cost_spike_threshold:
                flags.append(RiskFlag(
                    type="cost_spike",
                    severity="high" if cost_change > 0.20 else "medium",
                    description=f"Cost increased {cost_change * 100:.1f}% from previous month",
                    value=cost_change,
                    threshold=self.cost_spike_threshold
                ))
        
        # Delay risk (shipping mode and transit time analysis)
        for part in parts:
            if part.shipping_mode == "Ocean" and part.transit_days > 14:
                flags.append(RiskFlag(
                    type="delay_risk",
                    severity="medium",
                    description=f"Extended ocean transit time: {part.transit_days} days for {part.component_name}",
                    value=part.transit_days,
                    threshold=14
                ))
            elif part.shipping_mode == "Air" and part.transit_days > 7:
                flags.append(RiskFlag(
                    type="delay_risk", 
                    severity="high",
                    description=f"Unusual air transit delay: {part.transit_days} days for {part.component_name}",
                    value=part.transit_days,
                    threshold=7
                ))
        
        # Capacity shortfall risk (if requested quantity provided)
        # Note: This would require demand forecast input in production
        total_capacity = sum(part.monthly_capacity for part in parts)
        if total_capacity < 10000:  # Arbitrary threshold for prototype
            flags.append(RiskFlag(
                type="capacity_shortfall",
                severity="medium",
                description=f"Limited capacity: {total_capacity:,} units/month",
                value=total_capacity,
                threshold=10000
            ))
        
        # Low reliability risk
        if vendor.reliability_score < 0.7:
            flags.append(RiskFlag(
                type="reliability_risk",
                severity="high" if vendor.reliability_score < 0.5 else "medium",
                description=f"Low reliability score: {vendor.reliability_score:.1%}",
                value=vendor.reliability_score,
                threshold=0.7
            ))
        
        return flags
    
    def update_weights(self, new_weights: Dict[str, float]):
        """Update scoring weights and normalize."""
        self.weights = ScoringWeights(
            total_cost=new_weights.get('total_cost', 0.4),
            total_time=new_weights.get('total_time', 0.3),
            reliability=new_weights.get('reliability', 0.2),
            capacity=new_weights.get('capacity', 0.1)
        )
        self.weights.normalize()
        logger.info(f"Updated scoring weights: {self.weights.to_dict()}")
    
    def get_pillar_contributions(self, vendor_score: VendorScore) -> Dict[str, float]:
        """Calculate how much each pillar contributes to the final score."""
        weights = vendor_score.weights
        
        return {
            'total_cost': weights.get('total_cost', 0) * vendor_score.total_cost_score,
            'total_time': weights.get('total_time', 0) * vendor_score.total_time_score,
            'reliability': weights.get('reliability', 0) * vendor_score.reliability_score,
            'capacity': weights.get('capacity', 0) * vendor_score.capacity_score
        }
    
    def generate_executive_summary(self, analyses: List[VendorAnalysis]) -> Dict[str, str]:
        """Generate executive summary insights from vendor analyses."""
        if not analyses:
            return {"summary": "No vendor data available for analysis."}
        
        top_vendor = analyses[0]
        total_vendors = len(analyses)
        high_risk_count = sum(1 for analysis in analyses 
                            if any(flag.severity == "high" for flag in analysis.risk_flags))
        
        # Identify trends
        insights = []
        
        # Top performer insight
        insights.append(f"**Top Performer**: {top_vendor.vendor.name} leads with {top_vendor.current_score.final_score:.1%} score")
        
        # Risk assessment
        if high_risk_count > 0:
            insights.append(f"**Risk Alert**: {high_risk_count}/{total_vendors} vendors flagged with high-risk issues")
        
        # Cost analysis
        avg_cost = statistics.mean([analysis.avg_landed_cost for analysis in analyses])
        cost_leaders = [a for a in analyses[:3]]  # Top 3 by final score
        avg_cost_leaders = statistics.mean([a.avg_landed_cost for a in cost_leaders])
        
        if avg_cost_leaders < avg_cost * 0.9:
            insights.append(f"**Cost Efficiency**: Top performers average 10%+ lower costs (\${avg_cost_leaders:.2f} vs \${avg_cost:.2f})")
        
        # Capacity insights
        total_capacity = sum(analysis.total_monthly_capacity for analysis in analyses)
        insights.append(f"**Supply Capacity**: {total_capacity:,} total units/month across all vendors")
        
        # Data freshness
        stale_vendors = sum(1 for analysis in analyses if analysis.vendor.is_stale())
        if stale_vendors > 0:
            insights.append(f"**Data Quality**: {stale_vendors}/{total_vendors} vendors need data refresh")
        
        return {
            "summary": " • ".join(insights),
            "recommendation": self._generate_recommendation(analyses),
            "generated_at": datetime.now().isoformat()
        }
    
    def _generate_recommendation(self, analyses: List[VendorAnalysis]) -> str:
        """Generate strategic recommendation based on analysis."""
        if not analyses:
            return "Insufficient data for recommendations."
        
        top_vendor = analyses[0]
        
        # Check for clear leader vs competitive landscape
        if len(analyses) > 1:
            score_gap = top_vendor.current_score.final_score - analyses[1].current_score.final_score
            if score_gap > 0.15:  # 15% gap
                return f"**Strong Leader**: Prioritize {top_vendor.vendor.name} for primary sourcing given significant performance advantage."
            else:
                return f"**Competitive Landscape**: Consider diversified sourcing between {top_vendor.vendor.name} and {analyses[1].vendor.name} to balance performance and risk."
        
        return f"**Single Option**: Proceed with {top_vendor.vendor.name} while developing alternative suppliers."