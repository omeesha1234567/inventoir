document.addEventListener('DOMContentLoaded', function () {
    const tabButtons = Array.from(document.querySelectorAll('#analyticsTabNav .nav-link'));
    const filterSelect = document.getElementById('analytics-date-filter');
    const customRange = document.getElementById('analytics-custom-range');
    const startDateInput = document.getElementById('analytics-start-date');
    const endDateInput = document.getElementById('analytics-end-date');
    const applyRangeButton = document.getElementById('analytics-apply-range');
    const exportCsvBtn = document.getElementById('export-csv-btn');
    const exportExcelBtn = document.getElementById('export-excel-btn');
    const contentContainer = document.getElementById('analytics-tab-content');
    const dashboardShell = document.querySelector('.analytics-shell');
    const focusTitleEl = document.getElementById('analytics-focus-title');
    const focusMetaEl = document.getElementById('analytics-focus-meta');
    const resetZoomBtn = document.getElementById('analytics-reset-zoom');
    const downloadPNGBtn = document.getElementById('analytics-download-png');
    let activeTab = 'overview';
    let activeDeadStockDays = 90;
    const chartState = {};
    const chartFocusOverlay = document.getElementById('analytics-chart-focus-overlay');
    const focusChartContainer = document.getElementById('analytics-focus-chart-container');
    const focusCloseButton = document.querySelector('.analytics-focus-close');
    const sectionTooltips = {
        analytics: 'Business Intelligence dashboard providing company-specific insights into revenue, purchases, inventory, customers, vendors, payments, and overall business performance.',
        overview: 'Executive summary of your company\'s key business metrics, growth indicators, inventory value, and financial health.',
        revenue: 'Analyze revenue performance across daily, weekly, monthly, quarterly, and yearly periods. Track growth trends and revenue sources.',
        purchases: 'Monitor purchase spending, vendor-wise procurement activity, and purchasing trends over time.',
        products: 'Understand product performance, top-selling items, inventory value distribution, and dead stock analysis.',
        customers: 'Track customer lifetime value, purchasing behavior, retention, repeat purchases, and top customers.',
        vendors: 'Analyze vendor spending, contribution percentages, purchase frequency, and supplier performance.',
        payments: 'Monitor receivables, payables, outstanding balances, partially paid transactions, and payment health.',
        insights: 'AI-style business insights generated from your company data, highlighting growth opportunities, risks, trends, and recommended actions.',
    };

    function buildQueryString(params) {
        return Object.entries(params)
            .filter(([_, value]) => value !== undefined && value !== null && value !== '')
            .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`)
            .join('&');
    }

    function getCurrentFilter() {
        return filterSelect.value;
    }

    function getCurrentDates() {
        const filter = getCurrentFilter();
        if (filter === 'custom') {
            return {
                filter,
                start_date: startDateInput.value,
                end_date: endDateInput.value,
            };
        }
        return { filter };
    }

    function showCustomRange() {
        customRange.classList.toggle('d-none', filterSelect.value !== 'custom');
    }

    function saveChartState(chartId, data, layout, config, meta = {}) {
        chartState[chartId] = { data, layout, config, meta };
    }

    function getTopContributor(series) {
        if (!series || !Array.isArray(series.y) || !Array.isArray(series.x)) {
            return null;
        }
        const numericValues = series.y.map(Number);
        const maxValue = Math.max(...numericValues);
        const index = numericValues.indexOf(maxValue);
        const label = series.x[index];
        return label ? `${label} (${formatCurrency(maxValue)})` : null;
    }

    function renderPlotlyChart(chartId, data, layout, config = buildPlotlyConfig(), meta = {}) {
        const container = document.getElementById(chartId);
        if (!container) {
            return;
        }
        Plotly.newPlot(container, data, layout, config);
        saveChartState(chartId, data, layout, config, meta);
    }

    function initTooltips() {
        document.querySelectorAll('[data-tooltip-key]').forEach(element => {
            const key = element.dataset.tooltipKey;
            if (key && sectionTooltips[key]) {
                element.setAttribute('title', sectionTooltips[key]);
                element.setAttribute('data-bs-title', sectionTooltips[key]);
            }
        });

        if (typeof bootstrap !== 'undefined') {
            const tooltipTriggers = Array.from(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
            tooltipTriggers.forEach(trigger => {
                if (trigger._tooltip) {
                    trigger._tooltip.dispose();
                    trigger._tooltip = undefined;
                }
                trigger._tooltip = new bootstrap.Tooltip(trigger, {
                    container: 'body',
                    trigger: 'hover focus',
                    boundary: 'viewport',
                });
            });
        }
    }

    function getSelectedDateLabel() {
        const selectedOption = filterSelect.selectedOptions[0];
        return selectedOption ? selectedOption.textContent.trim() : 'Custom Range';
    }

    function buildChartSummary(state) {
        const label = getSelectedDateLabel();
        const values = Array.isArray(state.data) ? state.data.flatMap(series => series.y || []) : [];
        const total = values.reduce((sum, item) => sum + Number(item || 0), 0);
        const topContributor = state.meta?.topContributor || (() => {
            const topSeries = state.data[0];
            if (!topSeries || !Array.isArray(topSeries.y)) {
                return null;
            }
            const maxValue = Math.max(...topSeries.y.map(Number));
            const index = topSeries.y.findIndex(val => Number(val) === maxValue);
            const label = topSeries.x && topSeries.x[index] ? topSeries.x[index] : null;
            return label ? `${label} (${formatCurrency(maxValue)})` : null;
        })();
        const pieces = [`Date range: ${label}`];
        if (topContributor) {
            pieces.push(`Top contributor: ${topContributor}`);
        }
        pieces.push(`Total value: ${formatCurrency(total)}`);
        return pieces.join(' • ');
    }

    function openChartFocus(chartId) {
        const state = chartState[chartId];
        if (!state || !chartFocusOverlay || !focusChartContainer) {
            return;
        }
        const title = state.meta?.title || chartId.replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        focusTitleEl.textContent = title;
        focusMetaEl.textContent = buildChartSummary(state);
        focusChartContainer.innerHTML = `<div id="focus-${chartId}" class="analytics-chart" style="min-height: 60vh;"></div>`;
        const target = document.getElementById(`focus-${chartId}`);
        Plotly.newPlot(target, state.data, state.layout, state.config);
        setTimeout(() => {
            if (target) {
                Plotly.Plots.resize(target);
            }
        }, 120);
        chartFocusOverlay.classList.add('show');
        dashboardShell?.classList.add('analytics-blur-active');
        document.body.style.overflow = 'hidden';
    }

    function closeChartFocus() {
        if (!chartFocusOverlay || !focusChartContainer) {
            return;
        }
        chartFocusOverlay.classList.remove('show');
        dashboardShell?.classList.remove('analytics-blur-active');
        document.body.style.overflow = '';
        focusChartContainer.innerHTML = '';
    }

    function initChartFocus() {
        document.querySelectorAll('.analytics-chart-card').forEach(card => {
            card.addEventListener('click', event => {
                const chart = card.querySelector('.analytics-chart');
                if (!chart || !chart.id) {
                    return;
                }
                openChartFocus(chart.id);
            });
        });

        chartFocusOverlay?.addEventListener('click', event => {
            if (event.target === chartFocusOverlay) {
                closeChartFocus();
            }
        });

        focusCloseButton?.addEventListener('click', closeChartFocus);
        resetZoomBtn?.addEventListener('click', () => {
            const focusChart = focusChartContainer.querySelector('.js-plotly-plot');
            if (focusChart) {
                Plotly.relayout(focusChart, {
                    'xaxis.autorange': true,
                    'yaxis.autorange': true,
                });
            }
        });

        downloadPNGBtn?.addEventListener('click', () => {
            const focusChart = focusChartContainer.querySelector('.js-plotly-plot');
            if (focusChart) {
                Plotly.downloadImage(focusChart, {
                    format: 'png',
                    filename: focusTitleEl.textContent.replace(/\s+/g, '_').toLowerCase(),
                    width: 1400,
                    height: 800,
                });
            }
        });

        document.addEventListener('keydown', event => {
            if (event.key === 'Escape' && chartFocusOverlay?.classList.contains('show')) {
                closeChartFocus();
            }
        });
    }

    function setActiveTab(tab) {
        activeTab = tab;
        tabButtons.forEach(button => {
            button.classList.toggle('active', button.dataset.tab === tab);
        });
        loadTab(tab);
    }

    function renderError(message) {
        contentContainer.innerHTML = `<div class="alert alert-danger">${message}</div>`;
    }

    async function fetchTemplate(tab) {
        const response = await fetch(`/analytics/tab/${tab}/`);
        if (!response.ok) {
            throw new Error('Unable to load analytics tab.');
        }
        return response.text();
    }

    async function fetchData(tab, params) {
        const response = await fetch(`/analytics/data/${tab}/?${buildQueryString(params)}`);
        if (!response.ok) {
            const payload = await response.json().catch(() => ({}));
            throw new Error(payload.error || 'Failed to load analytics data.');
        }
        return response.json();
    }

    async function loadTab(tab) {
        contentContainer.innerHTML = `<div class="analytics-spinner"><div class="spinner-border text-primary" role="status"></div><span class="ms-3">Loading ${tab} data...</span></div>`;
        try {
            const templateHtml = await fetchTemplate(tab);
            contentContainer.innerHTML = templateHtml;
            attachTabEvents();
            await loadTabData(tab);
        } catch (error) {
            renderError(error.message);
        }
    }

    async function loadTabData(tab) {
        const params = getCurrentDates();
        if (tab === 'products') {
            params.dead_stock_days = activeDeadStockDays;
        }
        const data = await fetchData(tab, params);
        const renderer = tabRenderers[tab];
        if (renderer) {
            renderer(data);
        }
    }

    function formatCurrency(value) {
        const amount = Number(value || 0);
        return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(amount);
    }

    function formatNumeric(value) {
        return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(Number(value || 0));
    }

    function buildPlotlyConfig() {
        return {
            responsive: true,
            displayModeBar: true,
            modeBarButtonsToAdd: ['toImage', 'zoom2d', 'pan2d', 'toggleSpikelines'],
            displaylogo: false,
        };
    }

    function renderKpiCards(data) {
        const kpiTooltips = {
            'Total Revenue': 'Total revenue generated from sales in the selected period, including taxes and discounts.',
            'Sales Count': 'Total number of sales orders processed in the selected timeframe.',
            'Purchase Count': 'Number of purchase orders placed during the selected period.',
            'Total Customers': 'Number of unique customers who made purchases over the selected period.',
            'Total Vendors': 'Number of active vendors currently associated with your company.',
            'Inventory Value': 'Estimated value of current inventory based on item price multiplied by available quantity.',
            'Outstanding Receivables': 'Total amount customers still owe for completed sales.',
            'Outstanding Payables': 'Total amount still owed to vendors and suppliers.',
            'Average Order Value': 'Average revenue generated per sale order during the selected period.',
        };

        const cards = [
            { title: 'Total Revenue', value: formatCurrency(data.total_revenue), growth: data.revenue_growth },
            { title: 'Sales Count', value: data.sales_count, growth: data.sales_growth },
            { title: 'Purchase Count', value: data.purchase_count, growth: data.purchase_growth },
            { title: 'Total Customers', value: data.total_customers },
            { title: 'Total Vendors', value: data.total_vendors },
            { title: 'Inventory Value', value: formatCurrency(data.inventory_value) },
            { title: 'Outstanding Receivables', value: formatCurrency(data.outstanding_receivables) },
            { title: 'Outstanding Payables', value: formatCurrency(data.outstanding_payables) },
            { title: 'Average Order Value', value: formatCurrency(data.average_order_value) },
        ];
        const html = cards.map(card => {
            const growth = card.growth !== undefined ? `<div class="analytics-kpi-growth ${card.growth >= 0 ? 'positive' : 'negative'}">${card.growth >= 0 ? '+' : ''}${Number(card.growth).toFixed(2)}%</div>` : '';
            const tooltip = kpiTooltips[card.title] ? ` <span class="analytics-info-icon" data-bs-toggle="tooltip" data-bs-placement="top" data-bs-title="${kpiTooltips[card.title]}">ⓘ</span>` : '';
            return `<div class="col-lg-4 col-xl-3 mb-4"><div class="analytics-kpi-card"><div class="analytics-kpi-title">${card.title}${tooltip}</div><div class="analytics-kpi-value">${card.value}</div>${growth}</div></div>`;
        }).join('');
        const container = document.getElementById('overview-kpi-cards');
        if (container) {
            container.innerHTML = html;
            initTooltips();
        }
    }

    function renderOverviewCharts(data) {
        renderPlotlyChart(
            'overview-revenue-chart',
            [{ x: data.daily_trend.map(r => r.period), y: data.daily_trend.map(r => r.value), type: 'scatter', mode: 'lines+markers', marker: { color: '#0d6efd' }, name: 'Revenue' }],
            { title: false, margin: { t: 20 } },
            { title: 'Revenue Trend', topContributor: getTopContributor({ x: data.daily_trend.map(r => r.period), y: data.daily_trend.map(r => r.value) }) }
        );
        renderPlotlyChart(
            'overview-breakdown-chart',
            [{ labels: ['Receivables', 'Payables', 'Inventory'], values: [data.outstanding_receivables, data.outstanding_payables, data.inventory_value], type: 'pie', hole: 0.45 }],
            { margin: { t: 20 } },
            { title: 'Overview Breakdown' }
        );
    }

    function renderRevenue(data) {
        const revenueCategoryData = data.revenue_by_category || [];
        const revenueCategoryLayout = { margin: { t: 30 }, xaxis: { automargin: true }, yaxis: { automargin: true }, showlegend: revenueCategoryData.length <= 6 };
        const categorySeries = revenueCategoryData.length > 6 ? [{ x: revenueCategoryData.map(r => r.value), y: revenueCategoryData.map(r => r.category), type: 'bar', orientation: 'h', marker: { color: '#0d6efd' }, name: 'Revenue by Category' }] : [{ labels: revenueCategoryData.map(r => r.category), values: revenueCategoryData.map(r => r.value), type: 'pie', hole: 0.4 }];

        renderPlotlyChart(
            'revenue-daily-chart',
            [{ x: data.daily_trend.map(r => r.period), y: data.daily_trend.map(r => r.value), type: 'scatter', mode: 'lines+markers', fill: 'tozeroy', marker: { color: '#0d6efd' }, name: 'Daily Revenue' }],
            { margin: { t: 30 }, xaxis: { title: 'Day' }, yaxis: { title: 'Revenue' } },
            { title: 'Daily Revenue Trend', topContributor: getTopContributor({ x: data.daily_trend.map(r => r.period), y: data.daily_trend.map(r => r.value) }) }
        );

        renderPlotlyChart(
            'revenue-category-chart',
            categorySeries,
            revenueCategoryLayout,
            buildPlotlyConfig(),
            { title: 'Revenue by Category', topContributor: getTopContributor(revenueCategoryData.length > 6 ? { x: revenueCategoryData.map(r => r.category), y: revenueCategoryData.map(r => r.value) } : null) }
        );

        renderPlotlyChart(
            'revenue-customer-chart',
            [{ x: data.revenue_by_customer.map(r => r.name), y: data.revenue_by_customer.map(r => r.value), type: 'bar', marker: { color: '#198754' } }],
            { margin: { t: 30 }, xaxis: { automargin: true }, yaxis: { title: 'Revenue' } },
            { title: 'Revenue by Customer', topContributor: getTopContributor({ x: data.revenue_by_customer.map(r => r.name), y: data.revenue_by_customer.map(r => r.value) }) }
        );
    }

    function renderPurchases(data) {
        renderPlotlyChart(
            'purchase-daily-chart',
            [{ x: data.daily_trend.map(r => r.period), y: data.daily_trend.map(r => r.value), type: 'scatter', mode: 'lines+markers', fill: 'tozeroy', marker: { color: '#fd7e14' }, name: 'Daily Purchase' }],
            { margin: { t: 30 }, xaxis: { title: 'Day' }, yaxis: { title: 'Purchase Value' } },
            { title: 'Daily Purchase Trend', topContributor: getTopContributor({ x: data.daily_trend.map(r => r.period), y: data.daily_trend.map(r => r.value) }) }
        );

        renderPlotlyChart(
            'purchase-monthly-chart',
            [{ x: data.monthly_trend.map(r => r.period), y: data.monthly_trend.map(r => r.value), type: 'scatter', mode: 'lines+markers', fill: 'tozeroy', marker: { color: '#0dcaf0' }, name: 'Monthly Purchase' }],
            { margin: { t: 30 }, xaxis: { title: 'Month' }, yaxis: { title: 'Purchase Value' } },
            { title: 'Monthly Purchase Trend', topContributor: getTopContributor({ x: data.monthly_trend.map(r => r.period), y: data.monthly_trend.map(r => r.value) }) }
        );

        renderPlotlyChart(
            'purchase-vendor-chart',
            [{ x: data.vendor_trend.map(r => r.vendor), y: data.vendor_trend.map(r => r.value), type: 'bar', marker: { color: '#6f42c1' } }],
            { margin: { t: 30 }, xaxis: { automargin: true }, yaxis: { title: 'Vendor Spend' } },
            { title: 'Vendor Purchase Trend', topContributor: getTopContributor({ x: data.vendor_trend.map(r => r.vendor), y: data.vendor_trend.map(r => r.value) }) }
        );
    }

    function renderProducts(data) {
        renderPlotlyChart(
            'products-top-selling-chart',
            [{ x: data.top_selling_products.map(r => r.name), y: data.top_selling_products.map(r => r.quantity), type: 'bar', marker: { color: '#198754' } }],
            { margin: { t: 30 }, xaxis: { automargin: true }, yaxis: { title: 'Quantity' } },
            { title: 'Top Selling Products', topContributor: getTopContributor({ x: data.top_selling_products.map(r => r.name), y: data.top_selling_products.map(r => r.quantity) }) }
        );

        renderPlotlyChart(
            'products-top-revenue-chart',
            [{ x: data.top_revenue_products.map(r => r.name), y: data.top_revenue_products.map(r => r.revenue), type: 'bar', marker: { color: '#0d6efd' } }],
            { margin: { t: 30 }, xaxis: { automargin: true }, yaxis: { title: 'Revenue' } },
            { title: 'Top Revenue Products', topContributor: getTopContributor({ x: data.top_revenue_products.map(r => r.name), y: data.top_revenue_products.map(r => r.revenue) }) }
        );

        renderPlotlyChart(
            'products-worst-chart',
            [{ x: data.worst_performing_products.map(r => r.name), y: data.worst_performing_products.map(r => r.revenue), type: 'bar', marker: { color: '#dc3545' } }],
            { margin: { t: 30 }, xaxis: { automargin: true }, yaxis: { title: 'Revenue' } },
            { title: 'Worst Performing Products', topContributor: getTopContributor({ x: data.worst_performing_products.map(r => r.name), y: data.worst_performing_products.map(r => r.revenue) }) }
        );

        const categoryMeta = { title: 'Inventory Value by Category' };
        const categoryData = data.inventory_value_by_category || [];
        const categorySeries = categoryData.length > 6 ? [{ x: categoryData.map(r => r.value), y: categoryData.map(r => r.category), type: 'bar', orientation: 'h', marker: { color: '#0d6efd' }, name: 'Inventory Value' }] : [{ labels: categoryData.map(r => r.category), values: categoryData.map(r => r.value), type: 'pie', hole: 0.45 }];
        if (categoryData.length > 6) {
            categoryMeta.topContributor = getTopContributor({ x: categoryData.map(r => r.category), y: categoryData.map(r => r.value) });
        }
        renderPlotlyChart(
            'products-category-chart',
            categorySeries,
            { margin: { t: 30 }, xaxis: { automargin: true }, yaxis: { automargin: true }, showlegend: categoryData.length <= 6 },
            buildPlotlyConfig(),
            categoryMeta
        );

        const table = document.createElement('table');
        table.className = 'analytics-table';
        table.innerHTML = `
            <thead><tr><th>Product</th><th>Quantity</th><th>Last Sold</th></tr></thead>
            <tbody>${data.dead_stock.map(row => `<tr><td>${row.name}</td><td>${row.quantity}</td><td>${row.last_sold || 'Never'}</td></tr>`).join('')}</tbody>`;
        const container = document.getElementById('dead-stock-table');
        if (container) {
            container.innerHTML = '';
            container.appendChild(table);
        }
    }

    function renderCustomers(data) {
        renderPlotlyChart(
            'customers-top-revenue-chart',
            [{ x: data.top_customers_by_revenue.map(r => r.name), y: data.top_customers_by_revenue.map(r => r.value), type: 'bar', marker: { color: '#0d6efd' } }],
            { margin: { t: 30 }, xaxis: { automargin: true }, yaxis: { title: 'Revenue' } },
            { title: 'Top Customers by Revenue', topContributor: getTopContributor({ x: data.top_customers_by_revenue.map(r => r.name), y: data.top_customers_by_revenue.map(r => r.value) }) }
        );

        renderPlotlyChart(
            'customers-top-orders-chart',
            [{ x: data.top_customers_by_order_count.map(r => r.name), y: data.top_customers_by_order_count.map(r => r.orders), type: 'bar', marker: { color: '#6610f2' } }],
            { margin: { t: 30 }, xaxis: { automargin: true }, yaxis: { title: 'Orders' } },
            { title: 'Top Customers by Order Count', topContributor: getTopContributor({ x: data.top_customers_by_order_count.map(r => r.name), y: data.top_customers_by_order_count.map(r => r.orders) }) }
        );

        renderPlotlyChart(
            'customers-new-returning-chart',
            [{ labels: ['New Customers', 'Returning Customers'], values: [data.new_customers, data.returning_customers], type: 'pie', hole: 0.45 }],
            { margin: { t: 30 } },
            { title: 'Customer Composition' }
        );
    }

    function renderVendors(data) {
        renderPlotlyChart(
            'vendors-spend-chart',
            [{ x: data.vendor_spend_ranking.map(r => r.name), y: data.vendor_spend_ranking.map(r => r.spend), type: 'bar', marker: { color: '#0d6efd' } }],
            { margin: { t: 30 }, xaxis: { automargin: true }, yaxis: { title: 'Spend' } },
            { title: 'Vendor Spend Ranking', topContributor: getTopContributor({ x: data.vendor_spend_ranking.map(r => r.name), y: data.vendor_spend_ranking.map(r => r.spend) }) }
        );

        renderPlotlyChart(
            'vendors-contribution-chart',
            [{ labels: data.vendor_spend_ranking.map(r => r.name), values: data.vendor_spend_ranking.map(r => r.contribution), type: 'pie', hole: 0.45 }],
            { margin: { t: 30 } },
            { title: 'Vendor Contribution Breakdown' }
        );

        renderPlotlyChart(
            'vendors-frequency-chart',
            [{ x: data.vendor_spend_ranking.map(r => r.name), y: data.vendor_spend_ranking.map(r => r.frequency), type: 'bar', marker: { color: '#198754' } }],
            { margin: { t: 30 }, xaxis: { automargin: true }, yaxis: { title: 'Frequency' } },
            { title: 'Vendor Transaction Frequency', topContributor: getTopContributor({ x: data.vendor_spend_ranking.map(r => r.name), y: data.vendor_spend_ranking.map(r => r.frequency) }) }
        );
    }

    function renderPayments(data) {
        document.getElementById('payments-outstanding-receivables').textContent = formatCurrency(data.outstanding_receivables);
        document.getElementById('payments-partial-sales').textContent = formatNumeric(data.partial_sales);
        document.getElementById('payments-unpaid-sales').textContent = formatNumeric(data.unpaid_sales);
        document.getElementById('payments-outstanding-payables').textContent = formatCurrency(data.outstanding_payables);
        document.getElementById('payments-partial-purchases').textContent = formatNumeric(data.partial_purchases);
        document.getElementById('payments-unpaid-purchases').textContent = formatNumeric(data.unpaid_purchases);
    }

    function renderInsights(data) {
        document.getElementById('insights-health-score').textContent = `${data.business_health_score} / 100`;
        const list = document.getElementById('insights-list');
        list.innerHTML = data.insights.map(insight => `
            <li class="list-group-item">
                <strong>${insight.title}</strong>
                <span>${insight.message}</span>
            </li>
        `).join('');
    }

    const tabRenderers = {
        overview: data => {
            renderKpiCards(data);
            renderOverviewCharts(data);
        },
        revenue: renderRevenue,
        purchases: renderPurchases,
        products: renderProducts,
        customers: renderCustomers,
        vendors: renderVendors,
        payments: renderPayments,
        insights: renderInsights,
    };

    function attachTabEvents() {
        document.querySelectorAll('.dead-stock-filter').forEach(button => {
            button.addEventListener('click', async function () {
                document.querySelectorAll('.dead-stock-filter').forEach(node => node.classList.remove('active'));
                this.classList.add('active');
                activeDeadStockDays = Number(this.dataset.days);
                await loadTab('products');
            });
        });
        initTooltips();
        initChartFocus();
    }

    function attachEvents() {
        tabButtons.forEach(button => {
            button.addEventListener('click', () => setActiveTab(button.dataset.tab));
        });

        filterSelect.addEventListener('change', function () {
            showCustomRange();
            loadTab(activeTab);
        });

        applyRangeButton.addEventListener('click', function () {
            if (!startDateInput.value || !endDateInput.value) {
                return;
            }
            loadTab(activeTab);
        });

        exportCsvBtn.addEventListener('click', function () {
            const params = getCurrentDates();
            if (activeTab === 'products') params.dead_stock_days = activeDeadStockDays;
            const query = buildQueryString(params);
            window.location = `/analytics/export/csv/${activeTab}/?${query}`;
        });

        exportExcelBtn.addEventListener('click', function () {
            const params = getCurrentDates();
            if (activeTab === 'products') params.dead_stock_days = activeDeadStockDays;
            const query = buildQueryString(params);
            window.location = `/analytics/export/excel/${activeTab}/?${query}`;
        });
    }

    attachEvents();
    showCustomRange();
    loadTab(activeTab);
});
