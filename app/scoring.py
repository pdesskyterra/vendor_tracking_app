"""
Scoring engine for vendor evaluation.
"""

from typing import List, Dict, Optional, Tuple, Any
from datetime import date, datetime
import statistics
import structlog
from .models import Vendor, Part, VendorScore, VendorAnalysis, ScoringWeights, RiskFlag
from .utils import normalize_min_max, winsorize, calculate_month_over_month_change, safe_divide

logger = structlog.get_logger()

class ScoringEngine:
    """Core scoring engine implementing the vendor evaluation methodology."""
    
    def __init__(self, weights: Optional[ScoringWeights] = None):
        """Initialize scoring engine with default or custom weights."""
        self.weights = weights or ScoringWeights()
        self.weights.normalize()  # Ensure weights sum to 1.0
        
        # Risk detection thresholds (adjusted for balanced risk distribution)
        self.cost_spike_threshold = 0.15  # 15% MoM increase (was 10%)
        self.delay_spike_threshold = 5    # Additional days (was 3)
        self.capacity_shortfall_threshold = 5000  # 5K units/month (was 10K)
        self.staleness_threshold_days = 120  # 120 days (was 90)
        # Delay high thresholds (can be overridden at runtime)
        self.ocean_delay_high_days = 35
        self.air_delay_high_days = 14
    
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
        all_maturity = []
        
        vendor_metrics = {}
        
        for vendor in vendors:
            vendor_parts = parts_by_vendor.get(vendor.id, [])
            if not vendor_parts:
                continue
                
            # Calculate aggregate metrics for this vendor
            avg_cost = self._calculate_avg_landed_cost(vendor_parts)
            avg_time = self._calculate_avg_total_time(vendor_parts)
            total_capacity = sum(part.monthly_capacity for part in vendor_parts)
            maturity_raw, maturity_components = self._compute_vendor_maturity(vendor, vendor_parts)
            
            vendor_metrics[vendor.id] = {
                'avg_cost': avg_cost,
                'avg_time': avg_time,
                'total_capacity': total_capacity,
                'maturity_raw': maturity_raw,
                'maturity_components': maturity_components,
                'vendor': vendor,
                'parts': vendor_parts
            }
            
            all_costs.append(avg_cost)
            all_times.append(avg_time)
            all_capacities.append(total_capacity)
            all_maturity.append(maturity_raw)
        
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
        normalized_maturity = normalize_min_max(all_maturity, invert=False)  # Higher maturity is better
        
        # Calculate scores for each vendor
        for i, (vendor_id, metrics) in enumerate(vendor_metrics.items()):
            vendor = metrics['vendor']
            parts = metrics['parts']
            
            # Individual pillar scores (0-1)
            cost_score = normalized_costs[i]
            time_score = normalized_times[i]
            capacity_score = normalized_capacities[i]
            maturity_score = normalized_maturity[i]
            
            # Calculate final weighted score
            final_score = (
                self.weights.total_cost * cost_score +
                self.weights.total_time * time_score +
                self.weights.reliability * maturity_score +  # reliability weight now represents vendor maturity
                self.weights.capacity * capacity_score
            )
            
            # Create vendor score record
            vendor_score = VendorScore(
                vendor_id=vendor.id,
                vendor_name=vendor.name,
                total_cost_score=cost_score,
                total_time_score=time_score,
                reliability_score=maturity_score,  # store maturity in reliability field
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
                'vendor_maturity_raw': metrics['maturity_raw'],
                'vendor_maturity_components': metrics['maturity_components'],
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
    
    def _compute_vendor_maturity(self, vendor: Vendor, parts: List[Part]) -> Tuple[float, Dict[str, float]]:
        """Compute vendor maturity using comprehensive 5-dimensional assessment model.
        Uses actual vendor data when available, falls back to proxy calculation.
        Returns: (raw_score_0_1, components_dict)
        """
        # Check if enhanced vendor data is available
        enhanced_data = getattr(vendor, '_enhanced_data', {})
        
        if enhanced_data and enhanced_data.get("vendor_maturity_score") is not None:
            # Use pre-calculated comprehensive vendor maturity score from Notion
            maturity_raw = enhanced_data["vendor_maturity_score"]
            
            # Extract actual components for transparency
            components = {
                'operational_excellence': self._calculate_operational_score(enhanced_data),
                'financial_maturity': self._calculate_financial_score(enhanced_data),
                'innovation_technology': self._calculate_innovation_score(enhanced_data),
                'business_maturity': self._calculate_business_score(enhanced_data),
                'partnership_communication': self._calculate_partnership_score(enhanced_data),
                'comprehensive_score': maturity_raw
            }
            
            logger.info(f"Using comprehensive maturity for {vendor.name}: {maturity_raw:.3f}")
            
        else:
            # Fallback to simplified proxy calculation for backwards compatibility
            logger.warning(f"Enhanced data not available for {vendor.name}, using proxy calculation")
            
            # Region reputation (ally status, regulatory alignment, supply reliability)
            region_reputation_map: Dict[str, float] = {
                'US': 0.95, 'EU': 0.92, 'KR': 0.88, 'MX': 0.80,
                'VN': 0.72, 'IN': 0.72, 'CN': 0.60,
            }
            region_rep = region_reputation_map.get(vendor.region, 0.75)
            
            # Geopolitical alignment
            geopolitics_alignment_map: Dict[str, float] = {
                'US': 1.00, 'EU': 0.95, 'KR': 0.92, 'MX': 0.88,
                'VN': 0.75, 'IN': 0.78, 'CN': 0.55,
            }
            geo_align = geopolitics_alignment_map.get(vendor.region, 0.8)
            
            # Data freshness
            if vendor.last_verified is None:
                freshness = 0.6
            else:
                days_stale = (date.today() - vendor.last_verified).days
                if days_stale <= 30:
                    freshness = 1.0
                elif days_stale <= 60:
                    freshness = 0.85
                elif days_stale <= 90:
                    freshness = 0.75
                else:
                    freshness = 0.6
            
            # Shipping risk
            ocean_count = sum(1 for p in parts if p.shipping_mode == 'Ocean')
            avg_transit = statistics.mean([p.transit_days for p in parts]) if parts else 0
            ocean_share = ocean_count / len(parts) if parts else 0.0
            shipping_penalty = 0.10 * ocean_share + max(0.0, (avg_transit - 10) / 100.0 * 2.0)
            shipping_score = max(0.6, 1.0 - shipping_penalty)
            
            # Blend proxy components 
            w_region, w_geo, w_fresh, w_ship = 0.35, 0.35, 0.15, 0.15
            maturity_raw = (
                w_region * region_rep +
                w_geo * geo_align +
                w_fresh * freshness +
                w_ship * shipping_score
            )
            
            components = {
                'region_reputation': region_rep,
                'geopolitics_alignment': geo_align,
                'data_freshness': freshness,
                'shipping_score': shipping_score,
                'proxy_calculation': True
            }
        
        return maturity_raw, components
    
    def _calculate_operational_score(self, enhanced_data: Dict[str, Any]) -> float:
        """Calculate operational excellence score from actual vendor data."""
        otif = enhanced_data.get("otif_percent", 0) / 100.0
        consistency = enhanced_data.get("lead_time_consistency", 0) / 100.0
        ppm_defects = enhanced_data.get("ppm_defects", 1000)
        quality = max(0, 1.0 - min(ppm_defects / 1000.0, 1.0))  # Capped at 1000 PPM
        
        return (otif * 0.4 + consistency * 0.3 + quality * 0.3)
    
    def _calculate_financial_score(self, enhanced_data: Dict[str, Any]) -> float:
        """Calculate financial maturity score from actual vendor data."""
        financial_stability = enhanced_data.get("financial_stability_score", 0.5)
        debt_to_equity = enhanced_data.get("debt_to_equity_ratio", 2.0)
        debt_management = min(1.0, max(0.0, (4.0 - debt_to_equity) / 4.0))  # Optimal around 1.0 D/E
        
        return (financial_stability * 0.6 + debt_management * 0.4)
    
    def _calculate_innovation_score(self, enhanced_data: Dict[str, Any]) -> float:
        """Calculate innovation & technology score from actual vendor data."""
        digital_transformation = enhanced_data.get("digital_transformation_score", 0.5)
        tech_readiness = enhanced_data.get("technology_readiness_level", 5) / 9.0  # TRL scale 1-9
        patent_strength = enhanced_data.get("patent_portfolio_strength", 0.3)
        
        return (digital_transformation * 0.4 + tech_readiness * 0.3 + patent_strength * 0.3)
    
    def _calculate_business_score(self, enhanced_data: Dict[str, Any]) -> float:
        """Calculate business maturity score from actual vendor data."""
        founded_year = enhanced_data.get("founded_year", 2000)
        current_year = 2025
        company_age = current_year - founded_year
        company_age_factor = min(1.0, company_age / 25.0)  # Mature at 25+ years
        
        company_size = enhanced_data.get("company_size", "Medium")
        size_factors = {"Enterprise": 1.0, "Large": 0.85, "Medium": 0.7, "Small": 0.55}
        size_factor = size_factors.get(company_size, 0.6)
        
        return (company_age_factor * 0.6 + size_factor * 0.4)
    
    def _calculate_partnership_score(self, enhanced_data: Dict[str, Any]) -> float:
        """Calculate partnership & communication score from actual vendor data."""
        communication_quality = enhanced_data.get("communication_quality", 0.6)
        continuous_improvement = enhanced_data.get("continuous_improvement_score", 0.5)
        
        return (communication_quality * 0.7 + continuous_improvement * 0.3)
    
    def _generate_risk_flags(self, vendor: Vendor, parts: List[Part], 
                           current_score: VendorScore, historical_scores: List[VendorScore]) -> List[RiskFlag]:
        """Generate risk flags based on current data and trends."""
        flags = []
        
        # Data staleness risk (more lenient thresholds)
        if vendor.is_stale(self.staleness_threshold_days):
            days_stale = (date.today() - vendor.last_verified).days if vendor.last_verified else float('inf')
            flags.append(RiskFlag(
                type="stale_data",
                severity="high" if days_stale > 180 else "medium",  # High risk after 6 months
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
                    severity="high" if cost_change > 0.25 else "medium",  # High risk at 25% increase
                    description=f"Cost increased {cost_change * 100:.1f}% from previous month",
                    value=cost_change,
                    threshold=self.cost_spike_threshold
                ))
        
        # Delay risk (more realistic shipping time thresholds by region/mode)
        for part in parts:
            if part.shipping_mode == "Ocean" and part.transit_days > 21:  # 3 weeks for ocean
                flags.append(RiskFlag(
                    type="delay_risk",
                    severity="high" if part.transit_days > getattr(self, 'ocean_delay_high_days', 35) else "medium",
                    description=f"Extended ocean transit time: {part.transit_days} days for {part.component_name}",
                    value=part.transit_days,
                    threshold=21
                ))
            elif part.shipping_mode == "Air" and part.transit_days > 10:  # 10 days for air
                flags.append(RiskFlag(
                    type="delay_risk", 
                    severity="high" if part.transit_days > getattr(self, 'air_delay_high_days', 14) else "medium",
                    description=f"Extended air transit delay: {part.transit_days} days for {part.component_name}",
                    value=part.transit_days,
                    threshold=10
                ))
        
        # Capacity shortfall risk (more reasonable threshold)
        total_capacity = sum(part.monthly_capacity for part in parts)
        if total_capacity < self.capacity_shortfall_threshold:
            flags.append(RiskFlag(
                type="capacity_shortfall",
                severity="high" if total_capacity < 2000 else "medium",  # Very low capacity = high risk
                description=f"Limited capacity: {total_capacity:,} units/month",
                value=total_capacity,
                threshold=self.capacity_shortfall_threshold
            ))
        
        # Low vendor maturity risk (more lenient threshold)
        maturity_score = current_score.reliability_score  # this holds the normalized maturity
        if maturity_score < 0.4:  # Lowered from 0.5 to 0.4
            flags.append(RiskFlag(
                type="maturity_risk",
                severity="high" if maturity_score < 0.25 else "medium",  # High risk below 25%
                description=f"Low vendor maturity score: {maturity_score:.0%}",
                value=maturity_score,
                threshold=0.4
            ))
        
        # Compliance-based risk flags (check enhanced vendor data)
        enhanced_data = getattr(vendor, '_enhanced_data', {})
        if enhanced_data:
            # UFLPA compliance risk
            if not enhanced_data.get("uflpa_compliant", True):  # Default True for backwards compatibility
                flags.append(RiskFlag(
                    type="uflpa_non_compliance",
                    severity="high",
                    description="Vendor not UFLPA compliant - potential forced labor risk",
                    value=0,
                    threshold=1
                ))
            
            # Conflict minerals compliance risk
            if not enhanced_data.get("conflict_minerals_compliant", True):
                flags.append(RiskFlag(
                    type="conflict_minerals_risk",
                    severity="high",
                    description="Vendor not conflict minerals compliant - supply chain ethics risk",
                    value=0,
                    threshold=1
                ))
            
            # Audit staleness risk (different from data staleness)
            last_audit = enhanced_data.get("last_audit_date")
            if last_audit is None:
                flags.append(RiskFlag(
                    type="missing_audit",
                    severity="medium",
                    description="No recent audit date on record",
                    value=float('inf'),
                    threshold=365
                ))
            else:
                days_since_audit = (date.today() - last_audit).days
                if days_since_audit > 730:  # 2 years
                    flags.append(RiskFlag(
                        type="audit_overdue",
                        severity="high" if days_since_audit > 1095 else "medium",  # 3 years = high
                        description=f"Audit overdue: {days_since_audit} days since last audit",
                        value=days_since_audit,
                        threshold=730
                    ))
                elif days_since_audit > 545:  # 18 months
                    flags.append(RiskFlag(
                        type="audit_due",
                        severity="low",
                        description=f"Audit due soon: {days_since_audit} days since last audit",
                        value=days_since_audit,
                        threshold=545
                    ))
            
            # ISO certification deficiency risk
            iso_certs = enhanced_data.get("iso_certifications", [])
            cert_count = len(iso_certs) if iso_certs else 0
            company_size = enhanced_data.get("company_size", "Medium")
            
            # Expected certification counts by company size
            expected_certs = {"Enterprise": 5, "Large": 4, "Medium": 2, "Small": 1}
            threshold = expected_certs.get(company_size, 2)
            
            if cert_count < threshold:
                flags.append(RiskFlag(
                    type="certification_deficiency",
                    severity="medium" if cert_count == 0 else "low",
                    description=f"Low certification count: {cert_count} certs (expected {threshold}+ for {company_size} company)",
                    value=cert_count,
                    threshold=threshold
                ))
        
        # Part-level compliance risks
        if parts:
            non_rohs_parts = [p for p in parts if not getattr(p, 'rohs_compliant', True)]
            non_reach_parts = [p for p in parts if not getattr(p, 'reach_compliant', True)]
            
            if non_rohs_parts:
                rohs_compliance_rate = 1.0 - (len(non_rohs_parts) / len(parts))
                flags.append(RiskFlag(
                    type="rohs_non_compliance",
                    severity="high" if rohs_compliance_rate < 0.8 else "medium",
                    description=f"RoHS non-compliance: {len(non_rohs_parts)}/{len(parts)} parts affected",
                    value=rohs_compliance_rate,
                    threshold=0.9
                ))
            
            if non_reach_parts:
                reach_compliance_rate = 1.0 - (len(non_reach_parts) / len(parts))
                flags.append(RiskFlag(
                    type="reach_non_compliance",
                    severity="high" if reach_compliance_rate < 0.7 else "medium",
                    description=f"REACH non-compliance: {len(non_reach_parts)}/{len(parts)} parts affected",
                    value=reach_compliance_rate,
                    threshold=0.8
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