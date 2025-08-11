/**
 * Synseer Vendor Logistics Database - Frontend Application
 * Handles UI interactions, API calls, and data visualization
 */

class VendorApp {
    constructor() {
        this.currentView = 'vendors';
        this.vendors = [];
        this.currentFilters = {
            sort: 'final_score',
            range: '30d',
            component: '',
            region: '',
            mode: ''
        };
        this.charts = {};
        this.weights = {
            total_cost: 40,
            total_time: 30,
            reliability: 20,
            capacity: 10
        };
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadInitialData();
        this.setupWeightSliders();
    }

    bindEvents() {
        // Navigation
        document.getElementById('nav-vendors').addEventListener('click', (e) => {
            e.preventDefault();
            this.showView('vendors');
        });

        document.getElementById('nav-analytics').addEventListener('click', (e) => {
            e.preventDefault();
            this.showView('analytics');
        });

        document.getElementById('nav-settings').addEventListener('click', (e) => {
            e.preventDefault();
            this.showView('settings');
        });

        // Filters
        document.getElementById('apply-filters').addEventListener('click', () => {
            this.applyFilters();
        });

        // Modal
        document.getElementById('close-modal').addEventListener('click', () => {
            this.closeModal();
        });

        // Click outside modal to close
        document.getElementById('vendor-modal').addEventListener('click', (e) => {
            if (e.target === e.currentTarget) {
                this.closeModal();
            }
        });

        // Settings
        document.getElementById('update-weights').addEventListener('click', () => {
            this.updateWeights();
        });

        document.getElementById('reset-weights').addEventListener('click', () => {
            this.resetWeights();
        });


        // Main scoring interface (PDF page 11 style)
        document.getElementById('update-scores').addEventListener('click', () => {
            this.updateMainWeights();
        });

        // Enter key for component filter
        document.getElementById('component-filter').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.applyFilters();
            }
        });
    }

    async loadInitialData() {
        this.showLoading(true);
        try {
            await this.loadVendors();
            await this.loadWeights();
        } catch (error) {
            this.showError('Failed to load initial data: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }

    async loadVendors() {
        try {
            const params = new URLSearchParams(this.currentFilters);
            const response = await fetch(`/api/vendors?${params}`);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.vendors = data.vendors;
            
            this.renderVendorsTable();
            this.renderExecutiveSummary(data.executive_summary);
            this.updateAnalytics();
        } catch (error) {
            console.error('Error loading vendors:', error);
            throw error;
        }
    }

    async loadWeights() {
        try {
            const response = await fetch('/api/weights');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.weights = {
                total_cost: Math.round(data.weights.total_cost * 100),
                total_time: Math.round(data.weights.total_time * 100),
                reliability: Math.round(data.weights.reliability * 100),
                capacity: Math.round(data.weights.capacity * 100)
            };
            
            this.updateWeightSliders();
        } catch (error) {
            console.error('Error loading weights:', error);
        }
    }

    renderVendorsTable() {
        const tbody = document.getElementById('vendors-table-body');
        tbody.innerHTML = '';

        this.vendors.forEach((vendor, index) => {
            const row = document.createElement('tr');
            row.addEventListener('click', () => this.showVendorDetail(vendor.id));
            
            row.innerHTML = `
                <td class="font-bold text-primary">${index + 1}</td>
                <td>
                    <div class="font-bold">${vendor.name}</div>
                    <div class="text-sm text-secondary">${vendor.region}</div>
                </td>
                <td>
                    <span class="inline-block px-2 py-1 text-xs font-medium rounded ${this.getRegionClass(vendor.region)}">
                        ${vendor.region}
                    </span>
                </td>
                <td>
                    <div class="flex items-center gap-2">
                        ${this.renderScoreBar(vendor.final_score)}
                        <span class="font-medium">${(vendor.final_score * 100).toFixed(1)}%</span>
                    </div>
                </td>
                <td>
                    <div class="flex items-center gap-2">
                        ${this.renderScoreBar(vendor.pillar_scores.total_cost)}
                        <span class="text-sm">${(vendor.pillar_scores.total_cost * 100).toFixed(1)}%</span>
                    </div>
                </td>
                <td>
                    <div class="flex items-center gap-2">
                        ${this.renderScoreBar(vendor.pillar_scores.total_time)}
                        <span class="text-sm">${(vendor.pillar_scores.total_time * 100).toFixed(1)}%</span>
                    </div>
                </td>
                <td>
                    <div class="flex items-center gap-2">
                        ${this.renderScoreBar(vendor.pillar_scores.reliability)}
                        <span class="text-sm">${(vendor.pillar_scores.reliability * 100).toFixed(1)}%</span>
                    </div>
                </td>
                <td>
                    <div class="flex items-center gap-2">
                        ${this.renderScoreBar(vendor.pillar_scores.capacity)}
                        <span class="text-sm">${(vendor.pillar_scores.capacity * 100).toFixed(1)}%</span>
                    </div>
                </td>
                <td>$${vendor.metrics.avg_landed_cost.toFixed(2)}</td>
                <td>${vendor.metrics.part_count}</td>
                <td>
                    <div class="flex flex-wrap gap-1">
                        ${vendor.risk_flags.map(flag => 
                            `<span class="risk-badge ${flag.severity}">${flag.type.replace('_', ' ')}</span>`
                        ).join('')}
                    </div>
                </td>
                <td>
                    <span class="status-indicator ${vendor.staleness ? 'stale' : 'fresh'}">
                        <i class="fas ${vendor.staleness ? 'fa-exclamation-triangle' : 'fa-check-circle'}"></i>
                        ${vendor.staleness ? 'Stale' : 'Fresh'}
                    </span>
                </td>
            `;

            tbody.appendChild(row);
        });
    }

    renderScoreBar(score) {
        const percentage = Math.round(score * 100);
        let colorClass = 'poor';
        
        if (percentage >= 80) colorClass = 'excellent';
        else if (percentage >= 60) colorClass = 'good';
        else if (percentage >= 40) colorClass = 'fair';
        
        return `
            <div class="score-bar">
                <div class="score-fill ${colorClass}" style="width: ${percentage}%"></div>
            </div>
        `;
    }

    getRegionClass(region) {
        const classes = {
            'US': 'bg-blue-100 text-blue-800',
            'CN': 'bg-red-100 text-red-800',
            'KR': 'bg-green-100 text-green-800',
            'EU': 'bg-purple-100 text-purple-800',
            'VN': 'bg-yellow-100 text-yellow-800',
            'MX': 'bg-orange-100 text-orange-800',
            'IN': 'bg-indigo-100 text-indigo-800'
        };
        return classes[region] || 'bg-gray-100 text-gray-800';
    }

    renderExecutiveSummary(summary) {
        const container = document.querySelector('.summary-content');
        container.innerHTML = `
            <p><strong>Key Insights:</strong> ${summary.summary}</p>
            <p style="margin-top: 1rem;"><strong>Recommendation:</strong> ${summary.recommendation}</p>
        `;
    }

    async showVendorDetail(vendorId) {
        try {
            const response = await fetch(`/api/vendors/${vendorId}`);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            this.renderVendorModal(data);
            document.getElementById('vendor-modal').style.display = 'flex';
        } catch (error) {
            this.showError('Failed to load vendor details: ' + error.message);
        }
    }

    renderVendorModal(data) {
        // Header
        document.getElementById('modal-vendor-name').textContent = data.vendor.name;
        
        // Vendor info
        document.getElementById('modal-vendor-region').textContent = data.vendor.region;
        document.getElementById('modal-vendor-email').textContent = data.vendor.contact_email || 'N/A';
        document.getElementById('modal-vendor-verified').textContent = data.vendor.last_verified || 'N/A';
        document.getElementById('modal-vendor-status').innerHTML = `
            <span class="status-indicator ${data.vendor.is_stale ? 'stale' : 'fresh'}">
                <i class="fas ${data.vendor.is_stale ? 'fa-exclamation-triangle' : 'fa-check-circle'}"></i>
                ${data.vendor.is_stale ? 'Stale Data' : 'Current'}
            </span>
        `;

        // Risk flags
        const riskContainer = document.getElementById('modal-risk-flags');
        riskContainer.innerHTML = '';
        
        if (data.risk_flags.length > 0) {
            data.risk_flags.forEach(flag => {
                const badge = document.createElement('span');
                badge.className = `risk-badge ${flag.severity}`;
                badge.textContent = flag.description;
                riskContainer.appendChild(badge);
            });
        } else {
            riskContainer.innerHTML = '<p class="text-success">No risk flags detected</p>';
        }

        // Parts table
        const partsBody = document.getElementById('modal-parts-body');
        partsBody.innerHTML = '';
        
        data.parts.forEach(part => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${part.component_name}</td>
                <td>$${part.unit_price.toFixed(2)}</td>
                <td>$${part.total_landed_cost.toFixed(2)}</td>
                <td>${part.lead_time_weeks}w</td>
                <td>${part.transit_days}d ${part.shipping_mode}</td>
                <td>${part.monthly_capacity.toLocaleString()}</td>
            `;
            partsBody.appendChild(row);
        });

        // Charts
        setTimeout(() => {
            this.renderScoreBreakdownChart(data.current_score);
            this.renderVendorTrendChart(data.historical_trend);
        }, 100);
    }

    renderScoreBreakdownChart(scoreData) {
        const ctx = document.getElementById('score-breakdown-chart');
        
        if (this.charts.scoreBreakdown) {
            this.charts.scoreBreakdown.destroy();
        }

        this.charts.scoreBreakdown = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Total Cost', 'Total Time', 'Reliability', 'Capacity'],
                datasets: [{
                    data: [
                        scoreData.contributions.total_cost * 100,
                        scoreData.contributions.total_time * 100,
                        scoreData.contributions.reliability * 100,
                        scoreData.contributions.capacity * 100
                    ],
                    backgroundColor: [
                        '#ef4444',
                        '#f59e0b', 
                        '#10b981',
                        '#3b82f6'
                    ]
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    renderVendorTrendChart(trendData) {
        const ctx = document.getElementById('vendor-trend-chart');
        
        if (this.charts.vendorTrend) {
            this.charts.vendorTrend.destroy();
        }

        this.charts.vendorTrend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: trendData.map(point => point.date),
                datasets: [{
                    label: 'Final Score',
                    data: trendData.map(point => point.final_score * 100),
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37, 99, 235, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }

    closeModal() {
        document.getElementById('vendor-modal').style.display = 'none';
        
        // Clean up charts
        if (this.charts.scoreBreakdown) {
            this.charts.scoreBreakdown.destroy();
            delete this.charts.scoreBreakdown;
        }
        if (this.charts.vendorTrend) {
            this.charts.vendorTrend.destroy();
            delete this.charts.vendorTrend;
        }
    }

    async applyFilters() {
        this.currentFilters = {
            sort: document.getElementById('sort-filter').value,
            range: '30d',
            component: document.getElementById('component-filter').value,
            region: document.getElementById('region-filter').value,
            mode: ''
        };

        this.showLoading(true);
        try {
            await this.loadVendors();
        } catch (error) {
            this.showError('Failed to apply filters: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }

    setupWeightSliders() {
        const sliders = ['cost', 'time', 'reliability', 'capacity'];
        
        // Settings view sliders
        sliders.forEach(type => {
            const slider = document.getElementById(`${type}-weight`);
            const value = document.getElementById(`${type}-weight-value`);
            
            if (slider) {
                slider.addEventListener('input', (e) => {
                    const newValue = parseInt(e.target.value);
                    this.weights[`total_${type}`] = newValue;
                    value.textContent = newValue;
                    this.updateTotalWeight();
                    // Sync with main interface
                    this.syncMainWeightSliders();
                });
            }
        });

        // Main scoring interface sliders (PDF page 11 style)
        sliders.forEach(type => {
            const slider = document.getElementById(`main-${type}-weight`);
            const value = document.getElementById(`main-${type}-weight-value`);
            
            if (slider) {
                slider.addEventListener('input', (e) => {
                    const newValue = parseInt(e.target.value);
                    this.weights[`total_${type}`] = newValue;
                    value.textContent = newValue + '%';
                    // Sync with settings sliders
                    this.syncSettingsWeightSliders();
                });
            }
        });
    }

    syncMainWeightSliders() {
        // Sync settings changes to main interface
        ['cost', 'time', 'reliability', 'capacity'].forEach(type => {
            const slider = document.getElementById(`main-${type}-weight`);
            const value = document.getElementById(`main-${type}-weight-value`);
            if (slider && value) {
                slider.value = this.weights[`total_${type}`];
                value.textContent = this.weights[`total_${type}`] + '%';
            }
        });
    }

    syncSettingsWeightSliders() {
        // Sync main interface changes to settings
        ['cost', 'time', 'reliability', 'capacity'].forEach(type => {
            const slider = document.getElementById(`${type}-weight`);
            const value = document.getElementById(`${type}-weight-value`);
            if (slider && value) {
                slider.value = this.weights[`total_${type}`];
                value.textContent = this.weights[`total_${type}`];
            }
        });
        this.updateTotalWeight();
    }

    updateWeightSliders() {
        // Update settings sliders
        document.getElementById('cost-weight').value = this.weights.total_cost;
        document.getElementById('cost-weight-value').textContent = this.weights.total_cost;
        
        document.getElementById('time-weight').value = this.weights.total_time;
        document.getElementById('time-weight-value').textContent = this.weights.total_time;
        
        document.getElementById('reliability-weight').value = this.weights.reliability;
        document.getElementById('reliability-weight-value').textContent = this.weights.reliability;
        
        document.getElementById('capacity-weight').value = this.weights.capacity;
        document.getElementById('capacity-weight-value').textContent = this.weights.capacity;
        
        // Update main scoring interface sliders
        this.syncMainWeightSliders();
        
        this.updateTotalWeight();
    }

    updateTotalWeight() {
        const total = this.weights.total_cost + this.weights.total_time + 
                     this.weights.reliability + this.weights.capacity;
        document.getElementById('total-weight').textContent = total;
        
        // Color coding for total
        const element = document.getElementById('total-weight');
        if (total === 100) {
            element.className = 'text-success';
        } else {
            element.className = 'text-warning';
        }
    }

    async updateWeights() {
        try {
            const weights = {
                total_cost: this.weights.total_cost / 100,
                total_time: this.weights.total_time / 100,
                reliability: this.weights.reliability / 100,
                capacity: this.weights.capacity / 100
            };

            const response = await fetch('/api/weights', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ weights })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Recompute scores
            await fetch('/api/recompute', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            this.showSuccess('Weights updated and scores recomputed');
            await this.loadVendors();
        } catch (error) {
            this.showError('Failed to update weights: ' + error.message);
        }
    }

    async updateMainWeights() {
        try {
            const weights = {
                total_cost: this.weights.total_cost / 100,
                total_time: this.weights.total_time / 100,
                reliability: this.weights.reliability / 100,
                capacity: this.weights.capacity / 100
            };

            const response = await fetch('/api/weights', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ weights })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            // Recompute scores
            await fetch('/api/recompute', { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });
            
            // Update timestamp
            const now = new Date();
            document.getElementById('last-updated-time').textContent = now.toLocaleDateString() + ' ' + now.toLocaleTimeString();
            
            this.showSuccess('Scores updated successfully');
            await this.loadVendors();
        } catch (error) {
            this.showError('Failed to update scores: ' + error.message);
        }
    }

    resetWeights() {
        this.weights = {
            total_cost: 40,
            total_time: 30,
            reliability: 20,
            capacity: 10
        };
        this.updateWeightSliders();
    }


    async updateAnalytics() {
        // Update KPIs
        document.getElementById('total-vendors').textContent = this.vendors.length;
        
        const highRiskCount = this.vendors.filter(v => 
            v.risk_flags.some(flag => flag.severity === 'high')
        ).length;
        document.getElementById('high-risk-vendors').textContent = highRiskCount;
        
        const avgScore = this.vendors.reduce((sum, v) => sum + v.final_score, 0) / this.vendors.length;
        document.getElementById('avg-score').textContent = (avgScore * 100).toFixed(1) + '%';
        
        const totalCapacity = this.vendors.reduce((sum, v) => sum + v.metrics.total_capacity, 0);
        document.getElementById('total-capacity').textContent = totalCapacity.toLocaleString();

        // Load trend data for charts
        try {
            const response = await fetch('/api/analytics/trends');
            if (response.ok) {
                const data = await response.json();
                this.renderAnalyticsCharts(data.trends);
            }
        } catch (error) {
            console.error('Error loading analytics:', error);
        }
    }

    renderAnalyticsCharts(trends) {
        // Vendor rankings trend
        const trendCtx = document.getElementById('trend-chart');
        if (this.charts.trend) {
            this.charts.trend.destroy();
        }

        this.charts.trend = new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: trends.vendor_rankings[0].months,
                datasets: trends.vendor_rankings.map((vendor, index) => ({
                    label: vendor.vendor,
                    data: vendor.scores.map(s => s * 100),
                    borderColor: ['#2563eb', '#dc2626', '#16a34a'][index],
                    backgroundColor: ['rgba(37, 99, 235, 0.1)', 'rgba(220, 38, 38, 0.1)', 'rgba(22, 163, 74, 0.1)'][index],
                    fill: false,
                    tension: 0.4
                }))
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            callback: function(value) {
                                return value + '%';
                            }
                        }
                    }
                }
            }
        });

        // Cost trends
        const costCtx = document.getElementById('cost-chart');
        if (this.charts.cost) {
            this.charts.cost.destroy();
        }

        this.charts.cost = new Chart(costCtx, {
            type: 'bar',
            data: {
                labels: trends.cost_trends.months,
                datasets: [{
                    label: 'Average Landed Cost',
                    data: trends.cost_trends.avg_landed_cost,
                    backgroundColor: '#f59e0b',
                    borderColor: '#d97706',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '$' + value.toFixed(2);
                            }
                        }
                    }
                }
            }
        });

        // Capacity utilization
        const capacityCtx = document.getElementById('capacity-chart');
        if (this.charts.capacity) {
            this.charts.capacity.destroy();
        }

        const utilizationRate = trends.capacity_utilization.utilization_rate;
        this.charts.capacity = new Chart(capacityCtx, {
            type: 'doughnut',
            data: {
                labels: ['Utilized', 'Available'],
                datasets: [{
                    data: [utilizationRate * 100, (1 - utilizationRate) * 100],
                    backgroundColor: ['#10b981', '#e5e7eb']
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }

    showView(viewName) {
        // Update navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        document.getElementById(`nav-${viewName}`).classList.add('active');

        // Show/hide views
        document.querySelectorAll('.view-container').forEach(view => {
            view.style.display = 'none';
        });
        document.getElementById(`${viewName}-view`).style.display = 'block';

        this.currentView = viewName;

        // Load view-specific data
        if (viewName === 'analytics') {
            setTimeout(() => this.updateAnalytics(), 100);
        }
    }

    showLoading(show) {
        document.getElementById('loading').style.display = show ? 'flex' : 'none';
    }

    showMessage(message, type = 'success') {
        const container = document.getElementById('status-messages');
        const messageEl = document.createElement('div');
        messageEl.className = `status-message ${type}`;
        messageEl.textContent = message;
        
        container.appendChild(messageEl);
        
        setTimeout(() => {
            messageEl.remove();
        }, 5000);
    }

    showSuccess(message) {
        this.showMessage(message, 'success');
    }

    showError(message) {
        this.showMessage(message, 'error');
    }

    showWarning(message) {
        this.showMessage(message, 'warning');
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.vendorApp = new VendorApp();
});