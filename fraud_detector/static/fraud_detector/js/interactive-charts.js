// static/fraud_detector/js/interactive-charts.js

class FraudChartsManager {
    constructor(analysisId) {
        this.analysisId = analysisId;
        this.chartsData = {};
        this.currentFilters = {
            dateRange: 'all',
            riskLevel: 'all'
        };
        this.charts = {};
        this.init();
    }

    async init() {
        try {
            await this.loadChartsData();
            this.setupEventListeners();
            this.renderAllCharts();
        } catch (error) {
            console.error('Error initializing charts:', error);
            this.showChartsError();
        }
    }

    async loadChartsData() {
        try {
            // Use the base URL if defined, otherwise default to current path
            const baseUrl = window.API_BASE_URL || '';
            const response = await fetch(`${baseUrl}/api/charts-data/${this.analysisId}/`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            this.chartsData = await response.json();
            console.log('Charts data loaded:', this.chartsData);
        } catch (error) {
            console.error('Error loading charts data:', error);
            throw error;
        }
    }

    setupEventListeners() {
        // Date range filter
        const dateRangeSelect = document.getElementById('dateRange');
        if (dateRangeSelect) {
            dateRangeSelect.addEventListener('change', (e) => {
                this.currentFilters.dateRange = e.target.value;
                this.refreshAllCharts();
            });
        }

        // Risk level filter
        const riskFilterSelect = document.getElementById('riskFilter');
        if (riskFilterSelect) {
            riskFilterSelect.addEventListener('change', (e) => {
                this.currentFilters.riskLevel = e.target.value;
                this.refreshAllCharts();
            });
        }

        // Refresh button
        const refreshBtn = document.getElementById('refreshCharts');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', async () => {
                refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i>Refreshing...';
                refreshBtn.disabled = true;
                try {
                    await this.loadChartsData();
                    this.refreshAllCharts();
                } finally {
                    refreshBtn.innerHTML = '<i class="fas fa-sync-alt me-1"></i>Refresh Charts';
                    refreshBtn.disabled = false;
                }
            });
        }

        // Chart-specific controls
        const claimantLimitSelect = document.getElementById('claimantLimit');
        if (claimantLimitSelect) {
            claimantLimitSelect.addEventListener('change', () => {
                this.renderClaimantsChart();
            });
        }

        const mapMetricSelect = document.getElementById('mapMetric');
        if (mapMetricSelect) {
            mapMetricSelect.addEventListener('change', () => {
                this.renderMapChart();
            });
        }
    }

    renderAllCharts() {
        this.renderFraudScoreChart();
        this.renderTimelineChart();
        this.renderClaimantsChart();
        this.renderIndicatorsChart();
        this.renderInjuryChart();
        this.renderTimeLagChart();
        this.renderMapChart();
    }

    refreshAllCharts() {
        this.renderAllCharts();
    }

    renderFraudScoreChart() {
        const filteredData = this.applyFilters(this.chartsData.fraudScores || []);
        
        if (filteredData.length === 0) {
            this.showEmptyChart('fraudScoreChart', 'No data available for current filters');
            return;
        }

        const scores = filteredData.map(d => d.score);
        
        const trace1 = {
            x: scores,
            type: 'histogram',
            nbinsx: 30,
            opacity: 0.7,
            marker: {
                color: 'rgba(66, 165, 245, 0.7)',
                line: {
                    color: 'rgba(66, 165, 245, 1)',
                    width: 1
                }
            },
            name: 'Claims Count',
            hovertemplate: 'Score Range: %{x}<br>Count: %{y}<extra></extra>'
        };

        const shapes = [
            {
                type: 'line',
                x0: 6, x1: 6, y0: 0, y1: 1,
                yref: 'paper',
                line: { color: 'orange', width: 2, dash: 'dash' }
            },
            {
                type: 'line',
                x0: 10, x1: 10, y0: 0, y1: 1,
                yref: 'paper',
                line: { color: 'red', width: 2, dash: 'dash' }
            }
        ];

        const annotations = [
            {
                x: 6, y: 0.9, yref: 'paper',
                text: 'High Risk', showarrow: false,
                font: { color: 'orange', size: 12 }
            },
            {
                x: 10, y: 0.9, yref: 'paper',
                text: 'Critical Risk', showarrow: false,
                font: { color: 'red', size: 12 }
            }
        ];

        const layout = {
            title: {
                text: 'Distribution of Fraud Risk Scores',
                font: { size: 16, family: 'Arial, sans-serif' }
            },
            xaxis: { 
                title: 'Fraud Risk Score',
                gridcolor: '#e5e5e5'
            },
            yaxis: { 
                title: 'Number of Claims',
                gridcolor: '#e5e5e5'
            },
            showlegend: false,
            height: 400,
            margin: { t: 50, b: 50, l: 60, r: 30 },
            shapes: shapes,
            annotations: annotations,
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        };

        const config = {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToRemove: ['pan2d', 'lasso2d', 'select2d'],
            displaylogo: false
        };

        Plotly.newPlot('fraudScoreChart', [trace1], layout, config);
        this.charts.fraudScoreChart = true;
    }

    renderTimelineChart() {
        const filteredData = this.applyFilters(this.chartsData.timeline || []);
        
        if (filteredData.length === 0) {
            this.showEmptyChart('timelineChart', 'No timeline data available');
            return;
        }

        // Group by date and calculate statistics
        const timelineData = {};
        filteredData.forEach(d => {
            const date = d.date_of_loss;
            if (!timelineData[date]) {
                timelineData[date] = { scores: [], count: 0, highRiskCount: 0 };
            }
            timelineData[date].scores.push(d.fraud_score);
            timelineData[date].count++;
            if (d.risk_level === 'High' || d.risk_level === 'Critical') {
                timelineData[date].highRiskCount++;
            }
        });

        const dates = Object.keys(timelineData).sort();
        const avgScores = dates.map(date => {
            const scores = timelineData[date].scores;
            return scores.reduce((a, b) => a + b, 0) / scores.length;
        });
        const counts = dates.map(date => timelineData[date].count);

        const trace1 = {
            x: dates,
            y: avgScores,
            type: 'scatter',
            mode: 'lines+markers',
            name: 'Avg Fraud Score',
            yaxis: 'y',
            line: { color: '#ff6b6b', width: 3 },
            marker: { size: 6 },
            hovertemplate: 'Date: %{x}<br>Avg Score: %{y:.2f}<extra></extra>'
        };

        const trace2 = {
            x: dates,
            y: counts,
            type: 'bar',
            name: 'Total Claims',
            yaxis: 'y2',
            opacity: 0.6,
            marker: { color: '#4ecdc4' },
            hovertemplate: 'Date: %{x}<br>Claims: %{y}<extra></extra>'
        };

        const layout = {
            title: 'Claims Timeline with Fraud Score Trends',
            xaxis: { 
                title: 'Date',
                type: 'date'
            },
            yaxis: { 
                title: 'Average Fraud Score',
                side: 'left',
                color: '#ff6b6b'
            },
            yaxis2: { 
                title: 'Number of Claims',
                side: 'right',
                overlaying: 'y',
                color: '#4ecdc4'
            },
            showlegend: true,
            height: 400,
            margin: { t: 50, b: 50, l: 60, r: 60 },
            hovermode: 'x unified',
            plot_bgcolor: 'rgba(0,0,0,0)'
        };

        Plotly.newPlot('timelineChart', [trace1, trace2], layout, { responsive: true });
        this.charts.timelineChart = true;
    }

    renderClaimantsChart() {
        const limit = parseInt(document.getElementById('claimantLimit')?.value || 10);
        const filteredData = this.applyFilters(this.chartsData.claimants || []);

        if (filteredData.length === 0) {
            this.showEmptyChart('claimantsChart', 'No claimant data available');
            return;
        }

        // Count claims per claimant
        const claimantCounts = {};
        const claimantScores = {};
        
        filteredData.forEach(d => {
            const name = d.claimant_name;
            claimantCounts[name] = (claimantCounts[name] || 0) + 1;
            if (!claimantScores[name]) {
                claimantScores[name] = [];
            }
            claimantScores[name].push(d.fraud_score);
        });

        // Sort and limit
        const topClaimants = Object.entries(claimantCounts)
            .map(([name, count]) => ({
                name,
                count,
                avgScore: claimantScores[name].reduce((a, b) => a + b, 0) / claimantScores[name].length
            }))
            .sort((a, b) => b.count - a.count)
            .slice(0, limit);

        const trace = {
            x: topClaimants.map(d => d.count),
            y: topClaimants.map(d => d.name),
            type: 'bar',
            orientation: 'h',
            marker: {
                color: topClaimants.map(d => d.avgScore),
                colorscale: 'Reds',
                showscale: true,
                colorbar: { 
                    title: 'Avg Fraud Score',
                    titleside: 'right'
                },
                line: { color: '#333', width: 1 }
            },
            text: topClaimants.map(d => `${d.count} claims (${d.avgScore.toFixed(1)} avg)`),
            textposition: 'outside',
            hovertemplate: 'Claimant: %{y}<br>Claims: %{x}<br>Avg Score: %{marker.color:.1f}<extra></extra>'
        };

        const layout = {
            title: `Top ${limit} Repeat Claimants`,
            xaxis: { title: 'Number of Claims' },
            yaxis: { 
                title: 'Claimant Name',
                automargin: true
            },
            showlegend: false,
            height: Math.max(400, limit * 30),
            margin: { t: 50, b: 50, l: 200, r: 80 },
            plot_bgcolor: 'rgba(0,0,0,0)'
        };

        Plotly.newPlot('claimantsChart', [trace], layout, { responsive: true });
        this.charts.claimantsChart = true;
    }

    renderIndicatorsChart() {
        const filteredData = this.applyFilters(this.chartsData.indicators || []);

        if (filteredData.length === 0) {
            this.showEmptyChart('indicatorsChart', 'No indicators data available');
            return;
        }

        // Calculate indicator frequencies and average scores
        const indicators = {};
        filteredData.forEach(d => {
            if (d.red_flags && Array.isArray(d.red_flags)) {
                d.red_flags.forEach(flag => {
                    // Clean flag name
                    const cleanFlag = flag.replace(/^\[.*?\]\s*/, '').trim();
                    if (!indicators[cleanFlag]) {
                        indicators[cleanFlag] = { count: 0, totalScore: 0 };
                    }
                    indicators[cleanFlag].count++;
                    indicators[cleanFlag].totalScore += d.fraud_score;
                });
            }
        });

        const indicatorData = Object.entries(indicators)
            .map(([flag, data]) => ({
                flag,
                count: data.count,
                avgScore: data.totalScore / data.count
            }))
            .sort((a, b) => b.count - a.count)
            .slice(0, 15);

        if (indicatorData.length === 0) {
            this.showEmptyChart('indicatorsChart', 'No fraud indicators found');
            return;
        }

        const trace = {
            x: indicatorData.map(d => d.count),
            y: indicatorData.map(d => d.flag),
            type: 'bar',
            orientation: 'h',
            marker: {
                color: indicatorData.map(d => d.avgScore),
                colorscale: 'Reds',
                showscale: true,
                colorbar: { 
                    title: 'Avg Fraud Score',
                    titleside: 'right'
                }
            },
            text: indicatorData.map(d => `${d.count} (${d.avgScore.toFixed(1)})`),
            textposition: 'outside',
            hovertemplate: 'Indicator: %{y}<br>Count: %{x}<br>Avg Score: %{marker.color:.1f}<extra></extra>'
        };

        const layout = {
            title: 'Most Common Fraud Indicators',
            xaxis: { title: 'Number of Claims' },
            yaxis: { 
                title: 'Fraud Indicator',
                automargin: true
            },
            showlegend: false,
            height: Math.max(500, indicatorData.length * 35),
            margin: { t: 50, b: 50, l: 300, r: 80 },
            plot_bgcolor: 'rgba(0,0,0,0)'
        };

        Plotly.newPlot('indicatorsChart', [trace], layout, { responsive: true });
        this.charts.indicatorsChart = true;
    }

    async loadChartsData() {
    try {
        // Use the correct API endpoint name
        const response = await fetch(`/fraud_detector/api/charts-data/${this.analysisId}/`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        this.chartsData = await response.json();
        console.log('Charts data loaded:', this.chartsData);
    } catch (error) {
        console.error('Error loading charts data:', error);
        throw error;
    }
}

    renderInjuryChart() {
        const filteredData = this.applyFilters(this.chartsData.injuries || []);

        if (filteredData.length === 0) {
            this.showEmptyChart('injuryChart', 'No injury data available');
            return;
        }

        // Group by injury type and calculate stats
        const injuryStats = {};
        filteredData.forEach(d => {
            const injury = d.injury_type || 'Unknown';
            if (!injuryStats[injury]) {
                injuryStats[injury] = { scores: [], count: 0, highRiskCount: 0 };
            }
            injuryStats[injury].scores.push(d.fraud_score);
            injuryStats[injury].count++;
            if (d.risk_level === 'High' || d.risk_level === 'Critical') {
                injuryStats[injury].highRiskCount++;
            }
        });

        const injuryData = Object.entries(injuryStats)
            .map(([injury, data]) => ({
                injury: injury.length > 30 ? injury.substring(0, 30) + '...' : injury,
                fullInjury: injury,
                count: data.count,
                avgScore: data.scores.reduce((a, b) => a + b, 0) / data.scores.length,
                highRiskPct: (data.highRiskCount / data.count) * 100
            }))
            .sort((a, b) => b.avgScore - a.avgScore)
            .slice(0, 20);

        const trace1 = {
            x: injuryData.map(d => d.injury),
            y: injuryData.map(d => d.avgScore),
            type: 'bar',
            name: 'Avg Fraud Score',
            marker: { 
                color: injuryData.map(d => d.avgScore),
                colorscale: 'Reds',
                showscale: false
            },
            hovertemplate: 'Injury: %{customdata}<br>Avg Score: %{y:.1f}<br>Claims: %{text}<extra></extra>',
            customdata: injuryData.map(d => d.fullInjury),
            text: injuryData.map(d => d.count)
        };

        const trace2 = {
            x: injuryData.map(d => d.injury),
            y: injuryData.map(d => d.count),
            type: 'bar',
            name: 'Claims Count',
            yaxis: 'y2',
            marker: { color: 'rgba(78, 205, 196, 0.6)' },
            hovertemplate: 'Injury: %{customdata}<br>Count: %{y}<extra></extra>',
            customdata: injuryData.map(d => d.fullInjury)
        };

        const layout = {
            title: 'Injury Types vs Fraud Risk',
            xaxis: { 
                title: 'Injury Type',
                tickangle: -45,
                automargin: true
            },
            yaxis: { 
                title: 'Average Fraud Score',
                color: '#ff6b6b'
            },
            yaxis2: { 
                title: 'Number of Claims',
                overlaying: 'y',
                side: 'right',
                color: '#4ecdc4'
            },
            showlegend: true,
            height: 500,
            margin: { t: 50, b: 120, l: 60, r: 60 },
            plot_bgcolor: 'rgba(0,0,0,0)'
        };

        Plotly.newPlot('injuryChart', [trace1, trace2], layout, { responsive: true });
        this.charts.injuryChart = true;
    }

    renderTimeLagChart() {
        const filteredData = this.applyFilters(this.chartsData.timeLag || [])
            .filter(d => d.days_to_report !== null && d.days_to_report !== undefined);

        if (filteredData.length === 0) {
            this.showEmptyChart('timeLagChart', 'No time lag data available');
            return;
        }

        // Create risk level color mapping
        const colorMap = {
            'Low': '#28a745',
            'Medium': '#17a2b8', 
            'High': '#ffc107',
            'Critical': '#dc3545'
        };

        const trace = {
            x: filteredData.map(d => d.days_to_report),
            y: filteredData.map(d => d.fraud_score),
            mode: 'markers',
            type: 'scatter',
            marker: {
                size: 8,
                color: filteredData.map(d => colorMap[d.risk_level] || '#666'),
                opacity: 0.7,
                line: { color: '#333', width: 1 }
            },
            text: filteredData.map(d => 
                `Claim: ${d.claim_number}<br>Days to Report: ${d.days_to_report}<br>Fraud Score: ${d.fraud_score}<br>Risk: ${d.risk_level}`
            ),
            hovertemplate: '%{text}<extra></extra>',
            showlegend: false
        };

        const layout = {
            title: 'Reporting Delay vs Fraud Risk Correlation',
            xaxis: { 
                title: 'Days to Report Claim',
                zeroline: true
            },
            yaxis: { 
                title: 'Fraud Risk Score',
                zeroline: true
            },
            showlegend: false,
            height: 400,
            margin: { t: 50, b: 50, l: 60, r: 30 },
            plot_bgcolor: 'rgba(0,0,0,0)'
        };

        Plotly.newPlot('timeLagChart', [trace], layout, { responsive: true });
        this.charts.timeLagChart = true;
    }

    renderMapChart() {
        const metric = document.getElementById('mapMetric')?.value || 'count';
        const filteredData = this.applyFilters(this.chartsData.geographic || []);

        if (filteredData.length === 0) {
            this.showEmptyChart('mapChart', 'No geographic data available');
            return;
        }

        // Group by state/location
        const locationStats = {};
        filteredData.forEach(d => {
            const location = d.state || 'Unknown';
            if (location === 'Unknown') return;
            
            if (!locationStats[location]) {
                locationStats[location] = { 
                    scores: [], 
                    count: 0, 
                    highRiskCount: 0 
                };
            }
            locationStats[location].scores.push(d.fraud_score);
            locationStats[location].count++;
            if (d.risk_level === 'High' || d.risk_level === 'Critical') {
                locationStats[location].highRiskCount++;
            }
        });

        const locations = Object.keys(locationStats);
        let values, colorTitle, hoverText;

        switch(metric) {
            case 'avg_score':
                values = locations.map(loc => {
                    const scores = locationStats[loc].scores;
                    return scores.reduce((a, b) => a + b, 0) / scores.length;
                });
                colorTitle = 'Average Fraud Score';
                hoverText = locations.map(loc => 
                    `${loc}<br>Avg Score: ${values[locations.indexOf(loc)].toFixed(2)}<br>Claims: ${locationStats[loc].count}`
                );
                break;
            case 'high_risk_pct':
                values = locations.map(loc => 
                    (locationStats[loc].highRiskCount / locationStats[loc].count) * 100
                );
                colorTitle = 'High Risk Percentage';
                hoverText = locations.map(loc => 
                    `${loc}<br>High Risk %: ${values[locations.indexOf(loc)].toFixed(1)}%<br>Claims: ${locationStats[loc].count}`
                );
                break;
            default:
                values = locations.map(loc => locationStats[loc].count);
                colorTitle = 'Number of Claims';
                hoverText = locations.map(loc => 
                    `${loc}<br>Claims: ${values[locations.indexOf(loc)]}<br>High Risk: ${locationStats[loc].highRiskCount}`
                );
        }

        const trace = {
            type: 'choropleth',
            locationmode: 'USA-states',
            locations: locations,
            z: values,
            text: hoverText,
            colorscale: metric === 'count' ? 'Blues' : 'Reds',
            colorbar: { 
                title: {
                    text: colorTitle,
                    side: 'right'
                }
            },
            hovertemplate: '%{text}<extra></extra>'
        };

        const layout = {
            title: `Geographic Distribution: ${colorTitle}`,
            geo: {
                scope: 'usa',
                projection: { type: 'albers usa' },
                showlakes: true,
                lakecolor: 'rgb(255, 255, 255)',
                bgcolor: 'rgba(0,0,0,0)'
            },
            height: 500,
            margin: { t: 50, b: 20, l: 20, r: 20 },
            plot_bgcolor: 'rgba(0,0,0,0)',
            paper_bgcolor: 'rgba(0,0,0,0)'
        };

        Plotly.newPlot('mapChart', [trace], layout, { responsive: true });
        this.charts.mapChart = true;
    }

    // Utility methods
    applyFilters(data) {
        let filtered = [...data];

        // Apply date range filter
        if (this.currentFilters.dateRange !== 'all') {
            const daysAgo = parseInt(this.currentFilters.dateRange);
            const cutoffDate = new Date();
            cutoffDate.setDate(cutoffDate.getDate() - daysAgo);

            filtered = filtered.filter(d => {
                if (!d.date_of_loss) return false;
                const claimDate = new Date(d.date_of_loss);
                return claimDate >= cutoffDate;
            });
        }

        // Apply risk level filter
        if (this.currentFilters.riskLevel !== 'all') {
            filtered = filtered.filter(d => d.risk_level === this.currentFilters.riskLevel);
        }

        return filtered;
    }

    showEmptyChart(chartId, message) {
        const element = document.getElementById(chartId);
        if (element) {
            element.innerHTML = `
                <div class="d-flex align-items-center justify-content-center" style="height: 400px;">
                    <div class="text-center text-muted">
                        <i class="fas fa-chart-line fa-3x mb-3"></i>
                        <p>${message}</p>
                    </div>
                </div>
            `;
        }
    }

    showChartsError() {
        const errorMessage = `
            <div class="alert alert-danger text-center">
                <i class="fas fa-exclamation-triangle"></i>
                Error loading chart data. Please refresh the page.
            </div>
        `;

        document.querySelectorAll('.plotly-chart').forEach(chart => {
            chart.innerHTML = errorMessage;
        });
    }

    downloadChart(chartId) {
        if (this.charts[chartId]) {
            Plotly.downloadImage(chartId, {
                format: 'png',
                width: 1200,
                height: 600,
                filename: `${chartId}_analysis_${this.analysisId}`
            });
        }
    }
}

// Global functions for template compatibility
function downloadChart(chartId) {
    if (window.fraudChartsManager) {
        window.fraudChartsManager.downloadChart(chartId);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the dashboard page
    if (document.getElementById('fraudScoreChart')) {
        // Extract analysis ID from the page context
        const analysisId = window.analysisId || document.querySelector('[data-analysis-id]')?.dataset.analysisId;
        
        if (analysisId) {
            window.fraudChartsManager = new FraudChartsManager(analysisId);
        } else {
            console.error('Analysis ID not found for charts initialization');
        }
    }
});