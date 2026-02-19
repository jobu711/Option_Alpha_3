/**
 * Chart factory functions for the debate viewer page.
 *
 * Uses TradingView Lightweight Charts (vendored standalone build).
 * Dark theme matches the zinc-950 background of the application.
 */

/**
 * Create a candlestick + volume chart with dark theme.
 * @param {string} containerId - DOM element ID for the chart
 * @param {Object} data - { candles: [{time, open, high, low, close}], volume: [{time, value, color}] }
 * @returns {Object|null} chart instance (caller stores for cleanup), or null if container missing
 */
function createPriceChart(containerId, data) {
    var container = document.getElementById(containerId);
    if (!container) return null;

    var chart = LightweightCharts.createChart(container, {
        layout: {
            background: { color: '#09090b' },
            textColor: '#a1a1aa',
        },
        grid: {
            vertLines: { color: '#27272a' },
            horzLines: { color: '#27272a' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
        },
        rightPriceScale: {
            borderColor: '#3f3f46',
        },
        timeScale: {
            borderColor: '#3f3f46',
            timeVisible: false,
        },
        width: container.clientWidth,
        height: 300,
    });

    // Candlestick series
    var candleSeries = chart.addCandlestickSeries({
        upColor: '#34d399',
        downColor: '#f87171',
        borderUpColor: '#34d399',
        borderDownColor: '#f87171',
        wickUpColor: '#34d399',
        wickDownColor: '#f87171',
    });
    candleSeries.setData(data.candles);

    // Volume series on a secondary price scale
    var volumeSeries = chart.addHistogramSeries({
        priceFormat: { type: 'volume' },
        priceScaleId: 'volume',
        color: '#3b82f680',
    });
    chart.priceScale('volume').applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
    });
    if (data.volume) {
        volumeSeries.setData(data.volume);
    }

    chart.timeScale().fitContent();

    // Resize handler — keep chart width in sync with container
    var resizeObserver = new ResizeObserver(function(entries) {
        for (var i = 0; i < entries.length; i++) {
            chart.applyOptions({ width: entries[i].contentRect.width });
        }
    });
    resizeObserver.observe(container);

    // Store resize observer on chart instance for cleanup
    chart._resizeObserver = resizeObserver;

    return chart;
}

/**
 * Clean up a chart instance. Call before HTMX swap to prevent memory leaks.
 * @param {Object|null} chart - chart instance returned by createPriceChart
 */
function destroyChart(chart) {
    if (chart) {
        if (chart._resizeObserver) {
            chart._resizeObserver.disconnect();
        }
        chart.remove();
    }
}
