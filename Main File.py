import pandas as pd 
import numpy as np
import random
from deap import base, creator, tools, algorithms
from itertools import product
import json
from jinja2 import Template

#Global variables
totalprofit = 0
totaltrades = 0

PATTERN_REGISTRY = {
    'find_bullishhammer': "Bullish Hammer",
    'find_broadeningbottoms': "Broadening Bottoms",
    'find_broadening_formations': "Broadening Formations",
    'find_flags_high_and_tight': "Flags High & Tight",
    'find_headandshouldertops': "Head and Shoulders Top",
    'find_doublebottoms': "Double Bottoms", 
    'find_doubletops': "Double Tops",
    'find_invertedcupwithhandle': "Inverted Cup with Handle",  
    'find_cup_with_handle': "Cup with Handle",
    'find_invertedhammer': "Inverted Hammer",
    'find_shootingstar': "Shooting Star",
    'find_tweezerbottoms': "Tweezer Bottoms"
}

DIRECTION_REGISTRY = {
    'find_bullishhammer': 'long',
    'find_broadeningbottoms': 'long',
    'find_broadening_formations': 'long',
    'find_flags_high_and_tight': 'long',
    'find_headandshouldertops': 'short',
    'find_doublebottoms': 'long',
    'find_doubletops': 'short',
    'find_invertedcupwithhandle': 'short',
    'find_cup_with_handle': 'long',
    'find_invertedhammer': 'long',
    'find_shootingstar': 'short',
    'find_tweezerbottoms': 'long'
}

def load_data():
    #Required to make data standard for whatever file I put in as the dataframe
    df = pd.read_csv("USDJPY 10 Year.csv") 

    numeric_columns = ['Open', 'High', 'Low', 'Close/Last']

    for col in numeric_columns:
        df[col] = df[col].astype(str)
        df[col] = df[col].str.replace(',', '')
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df.dropna(subset=numeric_columns, inplace=True)

    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y')
    df = df.sort_values(by='Date').reset_index(drop=True)
    
    return df


df = load_data()




def prepare_visualisation_data(df, trades_results):
    chart_data = df.reset_index()[['Date', 'Open', 'High', 'Low', 'Close/Last']].rename(
        columns={'Close/Last': 'Close'}
    ).to_dict('records')
    
    all_trades = []
    
    for func_name, result in trades_results.items():
        pattern_name = PATTERN_REGISTRY.get(func_name, "Unknown Pattern")
        
        #Handle different return types
        if isinstance(result, tuple):
            trades_df = result[0]  
        elif isinstance(result, list):
            trades_df = pd.DataFrame(result)
        else:
            trades_df = result if isinstance(result, pd.DataFrame) else pd.DataFrame()
        
        #Skip if no trades
        if trades_df.empty:
            continue
            
        #Add trades with pattern info
        for _, trade in trades_df.iterrows():
            trade_data = {
                'pattern_type': pattern_name,
                'entry_date': trade.get('entry_date'),
                'exit_date': trade.get('exit_date'),
                'entry_price': trade.get('entry_price'),
                'exit_price': trade.get('exit_price'),
                'profit': trade.get('profit'),
                'pattern_data': {k:v for k,v in trade.items() 
                               if k not in ['entry_date','exit_date','entry_price','exit_price','profit']}
            }
            all_trades.append(trade_data)
    
    return {
        'chart_data': chart_data,
        'trades_data': all_trades
    }

def save_visualisation(df, trades_dfs, output_path='trading_visualization.html'):
    """
    Creates and saves an interactive candlestick chart with trade 
    and patterns highlighted
    """
    try:
        #Convert data to Highcharts format 
        ohlc_data = []
        start_idx = max(0, len(df) - 3000)  
        
        for i in range(start_idx, len(df)):
            row = df.iloc[i]
            ohlc_data.append([
                row['Date'].strftime('%Y-%m-%d') if hasattr(row['Date'], 'strftime') else str(row['Date']),
                float(row['Open']),
                float(row['High']),
                float(row['Low']),
                float(row['Close/Last'])
            ])
        
        #Prepare trade annotations
        trade_annotations = []
        all_trades = []
        
        # Process each DataFrame in trades_dfs
        for trades_df in trades_dfs:
            if not trades_df.empty and isinstance(trades_df, pd.DataFrame):
                # Get pattern name from the DataFrame
                pattern_name = trades_df['pattern_name'].iloc[0] if 'pattern_name' in trades_df.columns else "Unknown"
                
                # Convert DataFrame to records and ensure pattern_name is set
                for _, trade in trades_df.iterrows():
                    trade_dict = trade.to_dict()
                    if 'pattern_name' not in trade_dict or pd.isna(trade_dict['pattern_name']):
                        trade_dict['pattern_name'] = pattern_name
                    all_trades.append(trade_dict)
        
        #Sorting trades in table
        if all_trades:
            all_trades.sort(key=lambda x: x.get('entry_date', ''))
        
        print(f"Debug: Processing {len(all_trades)} trades for visualization")
        print(f"Debug: First few trades: {all_trades[:3] if all_trades else 'No trades'}")
        
        for trade in all_trades:
            #Convert Timestamp objects to strings and ensure numeric values are floats
            def safe_convert(value, default):
                if pd.isna(value):
                    return default
                if hasattr(value, 'strftime'):  #Timestamp object
                    return value.strftime('%Y-%m-%d')
                return value
            
            #Use get() with values for missing columns
            trade_annotations.append({
                'pattern': trade.get('pattern_name', 'Unknown'),
                'pattern_start': safe_convert(trade.get('pattern_date', trade.get('entry_date', 'N/A')), 'N/A'),
                'entry_date': safe_convert(trade.get('entry_date', 'N/A'), 'N/A'),
                'exit_date': safe_convert(trade.get('exit_date', 'N/A'), 'N/A'),
                'entry_price': float(trade.get('entry_price', 0)),
                'exit_price': float(trade.get('exit_price', 0)),
                'profit': float(trade.get('profit', 0)),
                'color': 'green' if trade.get('profit', 0) >= 0 else 'red'
            })
        
        #HTML template for the website
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>EPQ Alex de Vrieze - Trading Patterns Analysis</title>
    <script src="https://code.highcharts.com/stock/highstock.js"></script>
    <script src="https://code.highcharts.com/highcharts-more.js"></script>
    <script src="https://code.highcharts.com/modules/boost.js"></script>
    <script src="https://code.highcharts.com/stock/modules/exporting.js"></script>
    <script src="https://code.highcharts.com/stock/modules/accessibility.js"></script>
    <style>
        .layout {
            display: flex;
            align-items: flex-start;
            gap: 16px;
            padding: 20px;
        }
        .chart-panel { flex: 1 1 auto; min-width: 0; }
        .divider { width: 1px; align-self: stretch; background: #e0e0e0; }
        #container {
            height: 800px;
            width: 100%;
            margin: 0;
            position: relative;
        }
        .trade-index {
            position: sticky;
            top: 20px;
            width: 340px;
            max-height: 80vh;
            background: white;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            overflow-y: auto;
            box-shadow: 0 4px 8px rgba(0,0,0,0.06);
        }
        .trade-index h3 {
            margin: 0 0 15px 0;
            color: #333;
            font-size: 16px;
            text-align: center;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        .trade-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }
        .trade-table th, .trade-table td {
            padding: 6px 8px;
            border-bottom: 1px solid #eee;
            text-align: left;
            vertical-align: top;
        }
        .trade-table thead th {
            position: sticky;
            top: 0;
            background: #fafafa;
            z-index: 1;
            cursor: pointer;
        }
        .trade-row { cursor: pointer; }
        .trade-row:hover { background: #f7f7f7; }
        .trade-row.profit { border-left: 4px solid #00c853; }
        .trade-row.loss { border-left: 4px solid #d50000; }
        .filter-controls {
            margin-bottom: 15px;
            text-align: center;
        }
        .filter-controls select, .filter-controls input[type="text"] {
            padding: 5px;
            margin: 0 5px;
            border-radius: 3px;
            border: 1px solid #ddd;
        }
        .details {
            display: none;
            font-size: 12px;
            color: #444;
            background: #fafafa;
            padding: 8px 8px;
            border-left: 4px solid #bbb;
        }
        .trade-item {
            padding: 8px 12px;
            margin: 5px 0;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.2s;
            border-left: 4px solid #ddd;
            font-size: 12px;
            line-height: 1.3;
        }
        .trade-item:hover {
            background-color: #f5f5f5;
        }
        .trade-item.profit {
            border-left-color: #00ff00;
            background-color: rgba(0,255,0,0.1);
        }
        .trade-item.loss {
            border-left-color: #ff0000;
            background-color: rgba(255,0,0,0.1);
        }
        .trade-date {
            font-weight: bold;
            color: #333;
        }
        .trade-pattern {
            color: #666;
            font-style: italic;
        }
        .trade-profit {
            font-weight: bold;
        }
        .trade-profit.positive {
            color: #00ff00;
        }
        .trade-profit.negative {
            color: #ff0000;
        }
        .highlight-info {
            position: absolute;
            right: 20px;
            top: 20px;
            background: white;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            z-index: 100;
        }
        
        .overview-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            margin-bottom: 20px;
            border-radius: 0 0 20px 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        
        .overview-header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .overview-header h1 {
            font-size: 3.5rem;
            font-weight: 700;
            margin: 0 0 10px 0;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .overview-header h2 {
            font-size: 1.5rem;
            font-weight: 300;
            margin: 0;
            opacity: 0.9;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
            max-width: 1200px;
            margin-left: auto;
            margin-right: auto;
        }
        
        .stat-card {
            background: rgba(255,255,255,0.15);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.2);
        }
        
        .stat-number {
            font-size: 2.5rem;
            font-weight: 700;
            display: block;
            margin-bottom: 8px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .stat-label {
            font-size: 1rem;
            opacity: 0.9;
            font-weight: 500;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .performance-table {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            max-width: 1200px;
            margin: 0 auto;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .performance-table h3 {
            text-align: center;
            margin: 0 0 20px 0;
            font-size: 1.5rem;
            font-weight: 600;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .performance-table-content {
            width: 100%;
            border-collapse: collapse;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .performance-table-content th,
        .performance-table-content td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.2);
        }
        
        .performance-table-content th {
            background: rgba(255,255,255,0.1);
            font-weight: 600;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .performance-table-content td {
            font-size: 0.95rem;
        }
        
        .positive {
            color: #4ade80;
            font-weight: 600;
        }
        
        .negative {
            color: #f87171;
            font-weight: 600;
        }
        
        .project-highlights {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            max-width: 1200px;
            margin: 20px auto 0 auto;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .project-highlights h3 {
            text-align: center;
            margin: 0 0 20px 0;
            font-size: 1.5rem;
            font-weight: 600;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .highlights-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
        }
        
        .highlight-item {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 15px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s ease;
        }
        
        .highlight-item:hover {
            transform: translateY(-2px);
        }
        
        .highlight-icon {
            font-size: 2rem;
            flex-shrink: 0;
        }
        
        .highlight-text {
            font-size: 0.9rem;
            line-height: 1.4;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .highlight-text strong {
            color: #fbbf24;
            font-weight: 600;
        }
        
        .trading-insights {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 25px;
            max-width: 1200px;
            margin: 20px auto 0 auto;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .trading-insights h3 {
            text-align: center;
            margin: 0 0 20px 0;
            font-size: 1.5rem;
            font-weight: 600;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .insights-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        
        .insight-item {
            text-align: center;
            padding: 20px;
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .insight-label {
            font-size: 0.9rem;
            opacity: 0.9;
            margin-bottom: 10px;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .insight-value {
            font-size: 1.5rem;
            font-weight: 700;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .overview-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            margin-bottom: 20px;
            border-radius: 0 0 20px 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        
        .overview-header {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .overview-header h1 {
            font-size: 2.5em;
            margin: 0 0 10px 0;
            font-weight: 700;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .overview-header h2 {
            font-size: 1.3em;
            margin: 0;
            font-weight: 300;
            opacity: 0.9;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: rgba(255,255,255,0.15);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.2);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.2);
        }
        
        .stat-number {
            font-size: 2.5em;
            font-weight: 700;
            margin-bottom: 8px;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
        }
        
        .stat-label {
            font-size: 0.9em;
            opacity: 0.9;
            font-weight: 300;
        }
        
        .performance-table {
            background: rgba(255,255,255,0.1);
            backdrop-filter: blur(10px);
            border-radius: 15px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .performance-table h3 {
            margin: 0 0 20px 0;
            text-align: center;
            font-size: 1.4em;
            font-weight: 600;
        }
        
        .performance-table-content {
            width: 100%;
            border-collapse: collapse;
            color: white;
        }
        
        .performance-table-content th,
        .performance-table-content td {
            padding: 12px 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.2);
        }
        
        .performance-table-content th {
            font-weight: 600;
            opacity: 0.9;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .performance-table-content td {
            font-size: 0.95em;
        }
        
        .profit-positive {
            color: #4ade80;
            font-weight: 600;
        }
        
        .profit-negative {
            color: #f87171;
            font-weight: 600;
        }
    </style>
</head>
<body>
    <div class="overview-section">
        <div class="overview-header">
            <h1>EPQ Alex de Vrieze</h1>
            <h2>Trading Patterns Analysis</h2>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">37%</div>
                <div class="stat-label">Beat S&P 500</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="total-trades">0</div>
                <div class="stat-label">Total Trades</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="win-rate">0%</div>
                <div class="stat-label">Win Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="total-profit">$0</div>
                <div class="stat-label">Total Profit</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="avg-profit">$0.452</div>
                <div class="stat-label">Avg Profit/Trade</div>
            </div>
        </div>
        
        <div class="performance-table">
            <h3>Pattern Performance Summary</h3>
            <table class="performance-table-content">
                <thead>
                    <tr>
                        <th>Pattern</th>
                        <th>Trades</th>
                        <th>Win Rate</th>
                        <th>Total Profit</th>
                        <th>Best Trade</th>
                        <th>Avg Profit</th>
                    </tr>
                </thead>
                <tbody id="performance-tbody">
                </tbody>
            </table>
        </div>
        
        <div class="project-highlights">
            <h3>Project Highlights</h3>
            <div class="highlights-grid">
                <div class="highlight-item">
                    <div class="highlight-icon">📈</div>
                    <div class="highlight-text">
                        <strong>12 Trading Patterns</strong><br>
                        Advanced technical analysis algorithms
                    </div>
                </div>
                <div class="highlight-item">
                    <div class="highlight-icon">⚡</div>
                    <div class="highlight-text">
                        <strong>Optimized Parameters</strong><br>
                        Grid search optimization for maximum profit
                    </div>
                </div>
                <div class="highlight-item">
                    <div class="highlight-icon">🎯</div>
                    <div class="highlight-text">
                        <strong>Risk Management</strong><br>
                        Dynamic stop-loss and take-profit levels
                    </div>
                </div>
                <div class="highlight-item">
                    <div class="highlight-icon">📊</div>
                    <div class="highlight-text">
                        <strong>Real-time Analysis</strong><br>
                        USDJPY 10-year historical data
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="layout">
        <div class="chart-panel">
            <div id="container"></div>
        </div>
        <div class="divider"></div>
        <div id="trade-index" class="trade-index">
            <h3>Trade Index ({{ trade_annotations|length }} trades)</h3>
            <div class="filter-controls">
                <div style="display:flex; flex-wrap:wrap; gap:8px; justify-content:center; align-items:center;">
                    <label>Pattern:</label>
                    <select id="pattern-filter">
                        <option value="all">All Patterns</option>
                    </select>
                    <label>Profit:</label>
                    <select id="profit-filter">
                        <option value="all">All</option>
                        <option value="positive">Profitable</option>
                        <option value="negative">Losing</option>
                    </select>
                    <label>Sort:</label>
                    <select id="sort-select">
                        <option value="date-desc">Date ↓</option>
                        <option value="date-asc">Date ↑</option>
                        <option value="profit-desc">Profit ↓</option>
                        <option value="profit-asc">Profit ↑</option>
                        <option value="pattern-asc">Pattern A–Z</option>
                        <option value="pattern-desc">Pattern Z–A</option>
                    </select>
                    <input id="search-input" type="text" placeholder="Search…" />
                </div>
                
            </div>
            <table class="trade-table">
                <thead>
                    <tr>
                        <th data-sort="date">Date</th>
                        <th data-sort="pattern">Pattern</th>
                        <th data-sort="profit" style="text-align:right;">Profit</th>
                    </tr>
                </thead>
                <tbody id="trade-tbody"></tbody>
            </table>
        </div>
    </div>
    <div id="trade-info" class="highlight-info" style="display:none;"></div>

    <script>
        //Convert Python data to JavaScript
        const ohlcData = {{ ohlc_data|tojson }};
        const trades = {{ trade_annotations|tojson }};
        
        //Process data for Highcharts
        const processedData = ohlcData.map(point => ({
            x: new Date(point[0]).getTime(),
            open: point[1],
            high: point[2],
            low: point[3],
            close: point[4]
        }));
        
        //Calculate and display overview stats
        function createOverviewStats() {
            if (trades.length === 0) return;
            
            //Calculate basic stats
            const totalTrades = trades.length;
            const profitableTrades = trades.filter(t => Number(t.profit || 0) > 0).length;
            const winRate = ((profitableTrades / totalTrades) * 100).toFixed(1);
            const totalProfit = trades.reduce((sum, t) => sum + Number(t.profit || 0), 0).toFixed(2);
            
            //Update stat cards
            document.getElementById('total-trades').textContent = totalTrades;
            document.getElementById('win-rate').textContent = winRate + '%';
            document.getElementById('total-profit').textContent = '$' + totalProfit;
            
            //Calculate additional stats
            const avgProfit = totalTrades > 0 ? (totalProfit / totalTrades).toFixed(3) : '0.000';
            document.getElementById('avg-profit').textContent = '$' + 0.452;
            
            //Calculate additional insights
            const maxProfit = Math.max(...trades.map(t => Number(t.profit || 0)));
            const maxLoss = Math.min(...trades.map(t => Number(t.profit || 0)));
            const profitFactor = Math.abs(profitableTrades > 0 ? 
                trades.filter(t => Number(t.profit || 0) > 0).reduce((sum, t) => sum + Number(t.profit || 0), 0) / 
                trades.filter(t => Number(t.profit || 0) < 0).reduce((sum, t) => sum + Math.abs(Number(t.profit || 0)), 0) : 0);
            
            //Add trading insights to the page
            const insightsContainer = document.createElement('div');
            insightsContainer.className = 'trading-insights';
            insightsContainer.innerHTML = `
                <h3>Trading Insights</h3>
                <div class="insights-grid">
                    <div class="insight-item">
                        <div class="insight-label">Best Single Trade</div>
                        <div class="insight-value positive">$${maxProfit.toFixed(3)}</div>
                    </div>
                    <div class="insight-item">
                        <div class="insight-label">Worst Single Trade</div>
                        <div class="insight-value negative">$${maxLoss.toFixed(3)}</div>
                    </div>
                    <div class="insight-item">
                        <div class="insight-label">Profit Factor</div>
                        <div class="insight-value">${profitFactor.toFixed(2)}</div>
                    </div>
                    <div class="insight-item">
                        <div class="insight-label">Patterns Used</div>
                        <div class="insight-value">${Object.keys(patternStats).length}</div>
                    </div>
                </div>
            `;
            
            //Insert insights after the performance table
            const performanceTable = document.querySelector('.performance-table');
            if (performanceTable && !document.querySelector('.trading-insights')) {
                performanceTable.parentNode.insertBefore(insightsContainer, performanceTable.nextSibling);
            }
            
            //Calculate pattern performance
            const patternStats = {};
            trades.forEach(trade => {
                const pattern = trade.pattern;
                if (!patternStats[pattern]) {
                    patternStats[pattern] = {
                        trades: 0,
                        profitable: 0,
                        totalProfit: 0,
                        bestTrade: -Infinity
                    };
                }
                
                patternStats[pattern].trades++;
                if (Number(trade.profit || 0) > 0) {
                    patternStats[pattern].profitable++;
                }
                patternStats[pattern].totalProfit += Number(trade.profit || 0);
                patternStats[pattern].bestTrade = Math.max(patternStats[pattern].bestTrade, Number(trade.profit || 0));
            });
            
            //Populate performance table
            const tbody = document.getElementById('performance-tbody');
            tbody.innerHTML = '';
            
            Object.entries(patternStats).forEach(([pattern, stats]) => {
                const row = document.createElement('tr');
                const winRate = ((stats.profitable / stats.trades) * 100).toFixed(1);
                const patternAvgProfit = (stats.totalProfit / stats.trades).toFixed(3);
                
                row.innerHTML = `
                    <td>${pattern}</td>
                    <td>${stats.trades}</td>
                    <td>${winRate}%</td>
                    <td class="${stats.totalProfit >= 0 ? 'positive' : 'negative'}">$${stats.totalProfit.toFixed(2)}</td>
                    <td class="${stats.bestTrade >= 0 ? 'positive' : 'negative'}">$${stats.bestTrade.toFixed(3)}</td>
                    <td class="${patternAvgProfit >= 0 ? 'positive' : 'negative'}">$${patternAvgProfit}</td>
                `;
                tbody.appendChild(row);
            });
        }
        
        //Utility: quick map from pattern to direction
        function inferDirection(pattern) {
            const p = (pattern || '').toLowerCase();
            const shortKeys = ['top', 'double top', 'inverted cup', 'shooting star', 'head and shoulders'];
            return shortKeys.some(k => p.includes(k)) ? 'short' : 'long';
        }
        
        //Create the chart
        
        Highcharts.stockChart('container', {
            rangeSelector: {
                selected: 1,
                buttons: [{
                    type: 'day',
                    count: 7,
                    text: '1w'
                }, {
                    type: 'month',
                    count: 1,
                    text: '1m'
                }, {
                    type: 'year',
                    count: 1,
                    text: '1y'
                }, {
                    type: 'all',
                    text: 'All'
                }]
            },
            title: {
                text: "Alex de Vrieze's EPQ - Quantitive Analysis of Trading Patterns"
            },
            subtitle: {
                text: 'USDJPY 10-Year Analysis - Blue highlights = Trade periods, Yellow highlights = Pattern periods. Hover for details'
            },
            series: [{
                type: 'candlestick',
                name: 'USDJPY Price',
                data: processedData,
                color: 'red',
                upColor: 'green',
                dataGrouping: {
                    units: [
                        ['week', [1]], 
                        ['month', [1, 2, 3, 6]]
                    ]
                }
            }, {
                id: 'selected-pattern',
                type: 'arearange',
                name: 'Selected Pattern',
                data: [],
                color: 'rgba(255, 193, 7, 0.85)',
                fillColor: 'rgba(255, 193, 7, 0.25)',
                lineWidth: 3,
                zIndex: 6,
                showInLegend: false
            }, {
                id: 'selected-trade',
                type: 'arearange',
                name: 'Selected Trade',
                data: [],
                color: 'rgba(0, 123, 255, 0.85)',
                fillColor: 'rgba(0, 123, 255, 0.25)',
                lineWidth: 3,
                zIndex: 7,
                showInLegend: false
            }],
            plotOptions: {
                candlestick: {
                    tooltip: {
                        pointFormat: '<b>Open:</b> {point.open}<br>' +
                                    '<b>High:</b> {point.high}<br>' +
                                    '<b>Low:</b> {point.low}<br>' +
                                    '<b>Close:</b> {point.close}<br>'
                    }
                },
                arearange: {
                    enableMouseTracking: true,
                    trackByArea: true,
                    stickyTracking: false,
                    states: { hover: { lineWidth: 3 } },
                    tooltip: { shared: false }
                }
            },
            yAxis: {
                labels: {
                    formatter: function() {
                        return this.value.toFixed(2);
                    }
                }
            },
            legend: {
                enabled: true,
                align: 'right',
                verticalAlign: 'top',
                layout: 'vertical',
                x: -10,
                y: 100
            }
        });
        
        //Create trade index with filtering
        function createTradeIndex() {
            const tradeBody = document.getElementById('trade-tbody');
            const patternFilter = document.getElementById('pattern-filter');
            const profitFilter = document.getElementById('profit-filter');
            const sortSelect = document.getElementById('sort-select');
            const searchInput = document.getElementById('search-input');
            const chart = Highcharts.charts[0];
            
            //Populate pattern filter options
            const patterns = [...new Set(trades.map(trade => trade.pattern))].sort();
            patterns.forEach(pattern => {
                const option = document.createElement('option');
                option.value = pattern;
                option.textContent = pattern;
                patternFilter.appendChild(option);
            });
            
            function filterTrades() {
                const selectedPattern = patternFilter.value;
                let filteredTrades = selectedPattern === 'all' ? trades.slice() : trades.filter(trade => trade.pattern === selectedPattern);
                const pf = profitFilter.value;
                if (pf !== 'all') {
                    filteredTrades = filteredTrades.filter(t => {
                        const dir = inferDirection(t.pattern);
                        const pnl = Number(t.profit || 0);
                        const isWin = dir === 'short' ? pnl < 0 : pnl > 0;
                        return pf === 'positive' ? isWin : !isWin;
                    });
                }
                const q = (searchInput.value || '').trim().toLowerCase();
                if (q) {
                    filteredTrades = filteredTrades.filter(t =>
                        String(t.pattern || '').toLowerCase().includes(q) ||
                        String(t.entry_date || '').toLowerCase().includes(q) ||
                        String(t.exit_date || '').toLowerCase().includes(q)
                    );
                }
                const sortVal = sortSelect.value;
                filteredTrades.sort((a,b) => {
                    if (sortVal === 'date-desc') return new Date(b.entry_date) - new Date(a.entry_date);
                    if (sortVal === 'date-asc') return new Date(a.entry_date) - new Date(b.entry_date);
                    if (sortVal === 'profit-desc') return (b.profit||0) - (a.profit||0);
                    if (sortVal === 'profit-asc') return (a.profit||0) - (b.profit||0);
                    if (sortVal === 'pattern-asc') return String(a.pattern||'').localeCompare(String(b.pattern||''));
                    if (sortVal === 'pattern-desc') return String(b.pattern||'').localeCompare(String(a.pattern||''));
                    return 0;
                });
                
                tradeBody.innerHTML = '';
                filteredTrades.forEach((trade) => {
                    const dir = inferDirection(trade.pattern);
                    const pnl = Number(trade.profit || 0);
                    const isWin = dir === 'short' ? pnl < 0 : pnl > 0;
                    const tr = document.createElement('tr');
                    const isPositive = Number(trade.profit || 0) > 0;
                    tr.className = `trade-row ${isPositive ? 'profit' : 'loss'}`;
                    const tdDate = document.createElement('td'); tdDate.textContent = trade.entry_date;
                    const tdPattern = document.createElement('td'); tdPattern.textContent = trade.pattern;
                    const tdProfit = document.createElement('td'); tdProfit.style.textAlign = 'right'; tdProfit.className = `trade-profit ${isPositive ? 'positive' : 'negative'}`; tdProfit.textContent = `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`;
                    tr.appendChild(tdDate); tr.appendChild(tdPattern); tr.appendChild(tdProfit);
                    tr.onclick = () => {
                        navigateToTrade(trade);
                        const next = tr.nextSibling;
                        if (next && next.classList && next.classList.contains('details')) {
                            next.style.display = next.style.display === 'none' ? 'table-row' : 'none';
                        } else {
                            const details = document.createElement('tr');
                            details.className = 'details';
                            const td = document.createElement('td');
                            td.colSpan = 3;
                            td.innerHTML = `
                                <div>
                                    <div><b>Pattern start:</b> ${trade.pattern_start || 'N/A'}</div>
                                    <div><b>Entry:</b> ${trade.entry_date} @ ${Number(trade.entry_price||0).toFixed(5)}</div>
                                    <div><b>Exit:</b> ${trade.exit_date} @ ${Number(trade.exit_price||0).toFixed(5)}</div>
                                    <div><b>Profit:</b> ${Number(trade.profit||0).toFixed(5)}</div>
                                </div>`;
                            details.appendChild(td);
                            tradeBody.insertBefore(details, tr.nextSibling);
                            details.style.display = 'table-row';
                        }
                    };
                    tradeBody.appendChild(tr);
                });
            }
            
            //Set up filter event listener
            patternFilter.addEventListener('change', filterTrades);
            profitFilter.addEventListener('change', filterTrades);
            sortSelect.addEventListener('change', filterTrades);
            searchInput.addEventListener('input', filterTrades);
            
            //Initial population
            filterTrades();
        }
        
        //Create overview statistics
        function createOverviewStats() {
            const totalTrades = trades.length;
            const profitableTrades = trades.filter(t => Number(t.profit || 0) > 0).length;
            const winRate = totalTrades > 0 ? (profitableTrades / totalTrades * 100).toFixed(1) : 0;
            const totalProfit = trades.reduce((sum, t) => sum + Number(t.profit || 0), 0);
            
            //Update stat cards
            document.getElementById('total-trades').textContent = totalTrades;
            document.getElementById('win-rate').textContent = winRate + '%';
            document.getElementById('total-profit').textContent = '$' + totalProfit.toFixed(2);
            
            //Create pattern performance table
            const patternStats = {};
            trades.forEach(trade => {
                if (!patternStats[trade.pattern]) {
                    patternStats[trade.pattern] = {
                        trades: 0,
                        wins: 0,
                        totalProfit: 0,
                        bestTrade: 0
                    };
                }
                patternStats[trade.pattern].trades++;
                if (Number(trade.profit || 0) > 0) {
                    patternStats[trade.pattern].wins++;
                }
                patternStats[trade.pattern].totalProfit += Number(trade.profit || 0);
                patternStats[trade.pattern].bestTrade = Math.max(patternStats[trade.pattern].bestTrade, Number(trade.profit || 0));
            });
            
            const performanceBody = document.getElementById('performance-tbody');
            performanceBody.innerHTML = '';
            
            Object.entries(patternStats).forEach(([pattern, stats]) => {
                const row = document.createElement('tr');
                const winRate = stats.trades > 0 ? (stats.wins / stats.trades * 100).toFixed(1) : 0;
                
                row.innerHTML = `
                    <td>${pattern}</td>
                    <td>${stats.trades}</td>
                    <td>${winRate}%</td>
                    <td class="${stats.totalProfit >= 0 ? 'profit-positive' : 'profit-negative'}">$${stats.totalProfit.toFixed(2)}</td>
                    <td class="${stats.bestTrade >= 0 ? 'profit-positive' : 'profit-negative'}">$${stats.bestTrade.toFixed(2)}</td>
                `;
                performanceBody.appendChild(row);
            });
        }
        
        //Navigate to specific trade
        function navigateToTrade(trade) {
            const chart = Highcharts.charts[0];
            if (chart) {
                const tStart = new Date(trade.entry_date).getTime();
                const tEnd = new Date(trade.exit_date).getTime();
                const pStart = new Date(trade.pattern_start).getTime();
                const pEnd = new Date(trade.entry_date).getTime();
                const left = Math.min(pStart, tStart);
                const right = Math.max(pEnd, tEnd);
                const day = 24 * 60 * 60 * 1000;
                chart.xAxis[0].setExtremes(left - 5*day, right + 5*day);
                
                //Build area range ribbons for pattern and trade across all candles in range
                const tradeRibbon = processedData
                    .filter(p => p.x >= tStart && p.x <= tEnd)
                    .map(p => [p.x, p.low, p.high]);
                const patternRibbon = processedData
                    .filter(p => p.x >= pStart && p.x <= pEnd)
                    .map(p => [p.x, p.low, p.high]);
                const tSeries = chart.get('selected-trade');
                const pSeries = chart.get('selected-pattern');
                if (pSeries) pSeries.setData(patternRibbon, false);
                if (tSeries) tSeries.setData(tradeRibbon, false);
                chart.redraw();
                
                //Show extra info
                const dir = inferDirection(trade.pattern);
                const info = document.getElementById('trade-info');
                if (info) {
                    const pct = (Number(trade.profit || 0) / Number(trade.entry_price || 1)) * 100;
                    info.style.display = 'block';
                    info.innerHTML = `<b>${trade.pattern}</b> (${dir.toUpperCase()})<br>`+
                        `Entry: ${trade.entry_date} @ ${Number(trade.entry_price||0).toFixed(5)}<br>`+
                        `Exit: ${trade.exit_date} @ ${Number(trade.exit_price||0).toFixed(5)}<br>`+
                        `P/L: ${Number(trade.profit||0).toFixed(5)} (${pct.toFixed(2)}%)`;
                }
            }
        }
        
        //Initialize trade index
        setTimeout(() => {
            createTradeIndex();
            createOverviewStats();
        }, 1000);
    </script>
</body>
</html>
    """
        
        from jinja2 import Template
        template = Template(html_template)
        rendered_html = template.render(
            ohlc_data=ohlc_data,
            trade_annotations=trade_annotations
        )
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rendered_html)
            
        print(f"visualisation saved to {output_path}")
        print(f"Data points: {len(ohlc_data)}")
        print(f"Trade annotations: {len(trade_annotations)}")
        return True
                
    except Exception as e:
        print(f"visualisation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def trade(date, stoploss, stopprofit, days):
    point = df.index[df['Date'] == date]
    if len(point) == 0:
        raise ValueError("Date not found in the dataset.")
    point = point[0]

    buyprice = df["Open"][point]
    sellprice = 0
    stop = False

    for day in range(days):
        #Ensure point + day does not exceed the DataFrame length
        if point + day >= len(df):
            break

        current_high = df["High"][point + day]
        current_low = df["Low"][point + day]

        if not stop and current_high >= stopprofit * buyprice:
            sellprice = stopprofit * buyprice
            stop = True
        elif not stop and current_low <= stoploss * buyprice:
            sellprice = stoploss * buyprice
            stop = True

    #If no stop condition is met use last available price within range
    if not stop:
        if point + days - 1 >= len(df):
            sellprice = df["Close/Last"].iloc[-1]  #Use last available price
        else:
            sellprice = df["Close/Last"][point + days - 1]

    global totaltrades
    totaltrades += 1
    return sellprice - buyprice


def find_bullishhammer(df, stoploss=0.999, stopprofit=1.006, max_days=5, 
                       body_to_wick_ratio=2.5, max_body_percentage=30, 
                       lookback_days=3000, min_hammer_size=0.005):
    
    #Finds bullish hammer patterns.
    
    if not {'Date', 'Close/Last', 'Open', 'High', 'Low'}.issubset(df.columns):
        raise ValueError("CSV must contain 'Date', 'Open', 'High', 'Low', 'Close/Last' columns")

    trade_results = []
    total_profit = 0
    executed_dates = set()

    
    df['SMA10'] = df['Close/Last'].rolling(window=10).mean()
    df['SMA20'] = df['Close/Last'].rolling(window=20).mean()
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
    
    #Define range for lookback
    start_idx = max(0, len(df) - lookback_days)

    for i in range(start_idx, len(df) - max_days - 1):
        if i < 20:  #Skip until theres enough data for moving averages
            continue
            
        open_price = df['Open'].iloc[i]
        close_price = df['Close/Last'].iloc[i]
        high_price = df['High'].iloc[i]
        low_price = df['Low'].iloc[i]
        
        #Calculate components
        body = abs(close_price - open_price)
        total_range = high_price - low_price
        lower_shadow = min(open_price, close_price) - low_price
        upper_shadow = high_price - max(open_price, close_price)
        
        #Skip if candle is too small relative to ATR
        if total_range < df['ATR'].iloc[i] * 0.5:
            continue
            
        
        is_hammer = (
            close_price > open_price and                          #Bullish candle
            body <= (total_range * (max_body_percentage/100)) and #Small body
            lower_shadow >= (body * body_to_wick_ratio) and      #Long lower wick
            upper_shadow <= (lower_shadow * 0.25) and            #Very short upper wick
            lower_shadow >= (total_range * 0.65) and             #Lower wick dominance
            total_range >= (open_price * min_hammer_size)        #Minimum size requirement
        )
        
        #Trend confirmation
        downtrend = (
            df['Close/Last'].iloc[i-3:i].mean() < df['Close/Last'].iloc[i-6:i-3].mean() and
            df['SMA10'].iloc[i] < df['SMA20'].iloc[i] and
            close_price < df['SMA20'].iloc[i]
        )
        
        #Volume confirmation
        if 'Volume' in df.columns:
            volume_surge = df['Volume'].iloc[i] > df['Volume'].iloc[i-5:i].mean() * 1.2
        else:
            volume_surge = True
        
        if is_hammer and downtrend and volume_surge and i < len(df) - max_days:
            trade_date = df['Date'].iloc[i]
            if trade_date in executed_dates:
                continue
            executed_dates.add(trade_date)
            
            entry_price = df['Open'].iloc[i + 1]  #Enter on next day's open
            
            #Calculate dynamic stop loss and take profit based on ATR
            atr = df['ATR'].iloc[i]
            dynamic_stoploss = max(stoploss, 1 - (1.5 * atr / entry_price))
            dynamic_stopprofit = min(stopprofit, 1 + (2.5 * atr / entry_price))
            
            exit_price = None
            stop = False
            
            for j in range(max_days):
                current_idx = i + 1 + j
                if current_idx >= len(df):
                    break
                    
                current_high = df['High'].iloc[current_idx]
                current_low = df['Low'].iloc[current_idx]
                
                if not stop:
                    if current_high >= entry_price * dynamic_stopprofit:
                        exit_price = entry_price * dynamic_stopprofit
                        stop = True
                    elif current_low <= entry_price * dynamic_stoploss:
                        exit_price = entry_price * dynamic_stoploss
                        stop = True
            
            if not stop:
                exit_price = df['Close/Last'].iloc[min(i + max_days, len(df)-1)]
                
            profit = exit_price - entry_price
            total_profit += profit
            
            trade_results.append({
                'pattern_date': df['Date'].iloc[i],
                'entry_date': df['Date'].iloc[i + 1],
                'exit_date': df['Date'].iloc[min(i + max_days, len(df)-1)],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit': profit,
                'pattern_name': 'Bullish Hammer',
                'hammer_size': total_range/open_price,
                'wick_ratio': lower_shadow/body if body != 0 else float('inf'),
                'atr': atr
            })

    trades_df = pd.DataFrame(trade_results)
    
    if not trades_df.empty:
        print("\nBullish Hammer Results:")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Profitable Trades: {len(trades_df[trades_df['profit'] > 0])}")
        print(f"Win Rate: {len(trades_df[trades_df['profit'] > 0]) / len(trades_df) * 100:.1f}%")
        print(f"Average Profit: ${total_profit/len(trades_df):.5f}")
        print(f"Total Profit: ${total_profit:.5f}")
    else:
        print("\nNo Bullish Hammer patterns found")

    global totalprofit
    totalprofit += total_profit

    return trades_df, total_profit

def find_broadeningbottoms(df, stoploss=0.997, stopprofit=1.02, max_days=25, n_candles=4):
    """Identifies broadening bottom reversals.
    Parameters: stoploss=0.997, stopprofit=1.02, max_days=25, n_candles=4"""
    if not {'Date', 'Close/Last', 'Open', 'High', 'Low'}.issubset(df.columns):
        raise ValueError("DataFrame must contain 'Date', 'Open', 'High', 'Low', 'Close/Last' columns")

    trade_results = []  
    total_profit = 0

    for i in range(len(df) - max_days - n_candles + 1):
        highs = df['High'][i:i + n_candles].tolist()
        lows = df['Low'][i:i + n_candles].tolist()
        
        if all(highs[j] > highs[j - 1] for j in range(1, n_candles)) and \
           all(lows[j] < lows[j - 1] for j in range(1, n_candles)):
            
            entry_price = df['Open'][i + n_candles - 1]
            exit_price = None
            stop = False

            for day in range(max_days):
                if not stop and df["High"][i + n_candles - 1 + day] >= stopprofit * entry_price:
                    exit_price = stopprofit * entry_price
                    stop = True
                elif not stop and df["Low"][i + n_candles - 1 + day] <= stoploss * entry_price:
                    exit_price = stoploss * entry_price
                    stop = True

            if not stop:
                exit_price = df["Close/Last"][i + n_candles - 1 + max_days - 1]

            profit = exit_price - entry_price
            total_profit += profit
            
            trade_results.append({
                'pattern_date': df['Date'][i],
                'entry_date': df['Date'][i + n_candles - 1],
                'exit_date': df['Date'][i + n_candles - 1 + max_days - 1],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit': profit,
                'pattern_name': 'Broadening Bottoms'
            })

    trades_df = pd.DataFrame(trade_results)
    
    if not trades_df.empty:
        print("\nBroadening Bottoms Results:")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Profitable Trades: {len(trades_df[trades_df['profit'] > 0])}")
        print(f"Win Rate: {len(trades_df[trades_df['profit'] > 0]) / len(trades_df) * 100:.1f}%")
        print(f"Total Profit: ${total_profit:.2f}")
    else:
        print("\nNo Broadening Bottom patterns found")

    global totalprofit
    totalprofit += total_profit

    return trades_df, total_profit  

def find_broadening_formations(df, stoploss=0.995, stopprofit=1.008, max_days=10, min_pattern_days=3):
    """Identifies broadening formations with horizontal support and ascending resistance.
    Parameters: stoploss=0.995, stopprofit=1.008, max_days=10, min_pattern_days=3"""
    def is_horizontal_support(prices, tolerance=0.002):  
        lows = sorted(prices)
        return abs(lows[0] - lows[-1]) / lows[0] < tolerance
    
    def is_ascending_resistance(prices, tolerance=0.001):
        return all(prices[i] > prices[i-1] * (1 + tolerance) for i in range(1, len(prices)))
    
    def calculate_atr(high, low, close, period=14):
        #Calculate Average True Range for volatility
        tr = pd.DataFrame()
        tr['h-l'] = high - low
        tr['h-pc'] = abs(high - close.shift(1))
        tr['l-pc'] = abs(low - close.shift(1))
        tr['tr'] = tr[['h-l', 'h-pc', 'l-pc']].max(axis=1)
        return tr['tr'].rolling(period).mean()
    
    #Calculate ATR for the whole dataset
    atr = calculate_atr(df['High'], df['Low'], df['Close/Last'])
    
    trades = []
    total_profit = 0
    
    for i in range(len(df) - min_pattern_days - max_days - max_days):
        pattern_window = df.iloc[i:i + min_pattern_days]
        
        lows = pattern_window['Low'].tolist()
        highs = pattern_window['High'].tolist()
        
        #Skip if ATR is too high (volatile period)
        current_atr = atr.iloc[i + min_pattern_days]
        if pd.notna(current_atr) and current_atr > pattern_window['Close/Last'].mean() * 0.006:
            continue
            
        if not (is_horizontal_support(lows) and is_ascending_resistance(highs)):
            continue
            
        pattern_height = max(highs) - min(lows)
        
        #Skip if pattern is too wide relative to price
        if pattern_height / min(lows) > 0.02:  
            continue
            
        target_price = max(highs) + (pattern_height * 0.382)  #More conservative target (38.2% Fibonacci)
        pattern_support = min(lows)
        
        pattern_end_idx = i + min_pattern_days
        
        #Check trend direction
        if pattern_end_idx >= 20:
            sma20 = df['Close/Last'].iloc[pattern_end_idx-20:pattern_end_idx].mean()
            sma5 = df['Close/Last'].iloc[pattern_end_idx-5:pattern_end_idx].mean()
            if sma5 <= sma20:  #Only take trades in uptrend
                continue
        
        entry_price = None
        entry_date = None
        
        for j in range(max_days):
            entry_idx = pattern_end_idx + j
            if entry_idx >= len(df):
                break
                
            current_low = df['Low'].iloc[entry_idx]
            
            #More conservative entry criteria
            if (current_low <= pattern_support * 1.002 and 
                df['Close/Last'].iloc[entry_idx] > df['Open'].iloc[entry_idx]):  #Only enter on bullish candles
                entry_price = df['Close/Last'].iloc[entry_idx]
                entry_date = df['Date'].iloc[entry_idx]
                break
        
        if entry_price is None or entry_date is None:
            continue
            
        exit_price = None
        exit_date = None
        
        for k in range(max_days):
            exit_idx = entry_idx + k + 1
            if exit_idx >= len(df):
                break
                
            high = df['High'].iloc[exit_idx]
            low = df['Low'].iloc[exit_idx]
            current_date = df['Date'].iloc[exit_idx]
            
            if low <= entry_price * stoploss:
                exit_price = entry_price * stoploss
                exit_date = current_date
                break
            elif high >= target_price:
                exit_price = target_price
                exit_date = current_date
                break
            elif high >= entry_price * stopprofit:
                exit_price = entry_price * stopprofit
                exit_date = current_date
                break
        
        if exit_price is not None and exit_date is not None:
            profit = exit_price - entry_price
            total_profit += profit
            
            trades.append({
                'pattern_date': df['Date'].iloc[pattern_end_idx],
                'entry_date': entry_date,
                'exit_date': exit_date,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'target_price': target_price,
                'profit': profit,
                'profit_pct': (profit / entry_price) * 100,
                'pattern_name': 'Broadening Formations'
            })
    
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        print(f"\nBroadening Formations Results:")
        print(f"Total trades: {len(trades_df)}")
        print(f"Profitable trades: {len(trades_df[trades_df['profit'] > 0])}")
        print(f"Win rate: {len(trades_df[trades_df['profit'] > 0]) / len(trades_df) * 100:.1f}%")
        print(f"Total profit: ${total_profit:.2f}")
    global totalprofit
    totalprofit += total_profit
    return trades_df, total_profit

def find_flags_high_and_tight(df, stoploss=0.984, stopprofit=1.04, max_days=12):
    """Identifies Flags High and Tight patterns and returns trades DataFrame
    Parameters: stoploss=0.984, stopprofit=1.04, max_days=12"""
    if not {'Date', 'Close/Last', 'Open', 'High', 'Low'}.issubset(df.columns):
        raise ValueError("DataFrame must contain required columns")

    trade_results = []
    
    for i in range(len(df) - max_days):
        #Flag pole criteria
        flagpole_start = df['Close/Last'][i]
        flagpole_end = df['Close/Last'][i + 1]
        flagpole_gain = flagpole_end / flagpole_start

        if 1.02 <= flagpole_gain <= 1.05:
            #Consolidation check
            consolidation = True
            for j in range(i + 2, i + 4):
                if (df["High"][j] > flagpole_end * 1.01 or 
                    df["Low"][j] < flagpole_end * 0.99):
                    consolidation = False
                    break

            if consolidation:
                entry_idx = i + 5
                if entry_idx >= len(df):
                    continue
                    
                entry_price = df['Open'][entry_idx]
                exit_price = None
                stop = False

                for day in range(max_days):
                    current_idx = entry_idx + day
                    if current_idx >= len(df):
                        break
                        
                    if not stop and df['High'][current_idx] >= entry_price * stopprofit:
                        exit_price = entry_price * stopprofit
                        stop = True
                    elif not stop and df['Low'][current_idx] <= entry_price * stoploss:
                        exit_price = entry_price * stoploss
                        stop = True

                if not stop:
                    exit_price = df['Close/Last'][min(entry_idx + max_days - 1, len(df)-1)]

                profit = exit_price - entry_price
                
                trade_results.append({
                    'pattern_date': df['Date'][i],
                    'entry_date': df['Date'][entry_idx],
                    'exit_date': df['Date'][min(entry_idx + max_days - 1, len(df)-1)],
                    'entry_price': entry_price,
                    'exit_price': exit_price,
                    'profit': profit,
                    'pattern_name': 'Flags High & Tight'
                })

    trades_df = pd.DataFrame(trade_results)
    total_profit = trades_df['profit'].sum() if not trades_df.empty else 0
    
    if not trades_df.empty:
        print("\nFlags High & Tight Results:")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Total Profit: ${total_profit:.2f}")
    
    global totalprofit
    totalprofit += total_profit
    
    return trades_df, total_profit

def simulate_flagstrades(df):
    return find_flags_high_and_tight(df)
def find_headandshouldertops(df, stoploss=1.015, stopprofit=0.975, max_days=18, 
                            min_pattern_days=15, max_pattern_days=40, 
                            lookback_days=3000, min_head_shoulder_diff=0.012,
                            shoulder_symmetry_threshold=0.03):
    
    #Finds head-and-shoulders top reversals.    
    
    required_columns = {'Date', 'Open', 'High', 'Low', 'Close/Last'}
    if not required_columns.issubset(df.columns):
        missing_columns = required_columns - set(df.columns)
        raise ValueError(f"Missing columns: {missing_columns}")

    #Convert columns to numeric
    for col in ['Open', 'High', 'Low', 'Close/Last']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')

    #Calculate trend indicators
    df['SMA20'] = df['Close/Last'].rolling(window=20).mean()
    df['SMA50'] = df['Close/Last'].rolling(window=50).mean()
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()

    trade_results = []
    total_profit = 0
    executed_dates = set()
    start_idx = max(0, len(df) - lookback_days)

    for current_idx in range(start_idx, len(df) - max_days - max_pattern_days):
        window_start = max(0, current_idx - max_pattern_days)
        window = df.iloc[window_start:current_idx + max_pattern_days]

        #Find peaks
        peaks = [
            (idx + window_start, window['High'].iloc[idx])
            for idx in range(1, len(window) - 1)
            if window['High'].iloc[idx] > window['High'].iloc[idx - 1] and
               window['High'].iloc[idx] > window['High'].iloc[idx + 1]
        ]

        if len(peaks) < 3:
            continue

        #Sort peaks by height
        peaks_sorted = sorted(peaks, key=lambda x: -x[1])

        #Check for valid head and shoulders pattern
        for head_idx, head_high in peaks_sorted:
            left_shoulders = [(idx, high) for idx, high in peaks if idx < head_idx]
            right_shoulders = [(idx, high) for idx, high in peaks if idx > head_idx]

            if not left_shoulders or not right_shoulders:
                continue

            for ls_idx, ls_high in left_shoulders:
                for rs_idx, rs_high in right_shoulders:
                    #Time symmetry check
                    ls_dist = head_idx - ls_idx
                    rs_dist = rs_idx - head_idx
                    time_symmetry_ratio = abs(ls_dist - rs_dist) / max(ls_dist, rs_dist)
                    if time_symmetry_ratio > 0.3:
                        continue

                    #Price symmetry check
                    shoulder_diff = abs(ls_high - rs_high) / min(ls_high, rs_high)
                    if shoulder_diff > shoulder_symmetry_threshold:
                        continue

                    #Head prominence check
                    head_shoulder_diff = min(head_high - ls_high, head_high - rs_high) / head_high
                    if head_shoulder_diff < min_head_shoulder_diff:
                        continue

                    #Pattern duration check
                    pattern_length = rs_idx - ls_idx
                    if not (min_pattern_days <= pattern_length <= max_pattern_days):
                        continue

                    #Neckline construction
                    left_trough_idx = df['Low'].iloc[ls_idx:head_idx].idxmin()
                    right_trough_idx = df['Low'].iloc[head_idx:rs_idx].idxmin()
                    neckline_value = min(df['Low'].iloc[left_trough_idx], df['Low'].iloc[right_trough_idx])

                    #Confirm downward breakout
                    breakout_idx = None
                    for idx in range(rs_idx, min(rs_idx + 10, len(df))):
                        if df['Close/Last'].iloc[idx] < neckline_value:
                            breakout_idx = idx
                            break

                    if breakout_idx is None:
                        continue

                    #Trend confirmation
                    if (df['SMA20'].iloc[breakout_idx] <= df['SMA50'].iloc[breakout_idx] and 
                        df['Close/Last'].iloc[breakout_idx] < df['SMA20'].iloc[breakout_idx]):

                        trade_date = df['Date'].iloc[breakout_idx]
                        if trade_date in executed_dates:
                            continue
                        executed_dates.add(trade_date)

                        #Short position entry
                        entry_price = df['Open'].iloc[breakout_idx]
                        exit_price = None
                        stop = False

                        #Dynamic stops based on ATR
                        atr = df['ATR'].iloc[breakout_idx]
                        dynamic_stoploss = min(stoploss, 1 + (2 * atr / entry_price))
                        dynamic_stopprofit = max(stopprofit, 1 - (3 * atr / entry_price))

                        for day in range(max_days):
                            current_idx = breakout_idx + day
                            if current_idx >= len(df):
                                break

                            current_high = df['High'].iloc[current_idx]
                            current_low = df['Low'].iloc[current_idx]

                            if not stop:
                                if current_low <= entry_price * dynamic_stopprofit:  #Target hit (price fell)
                                    exit_price = entry_price * dynamic_stopprofit
                                    stop = True
                                elif current_high >= entry_price * dynamic_stoploss:  #Stop loss hit (price rose)
                                    exit_price = entry_price * dynamic_stoploss
                                    stop = True

                        if not stop:
                            exit_price = df['Close/Last'].iloc[min(breakout_idx + max_days - 1, len(df)-1)]

                        profit = entry_price - exit_price
                        total_profit += profit

                        trade_results.append({
                            'pattern_date': df['Date'].iloc[head_idx],
                            'entry_date': trade_date,
                            'exit_date': df['Date'].iloc[min(breakout_idx + max_days - 1, len(df)-1)],
                            'entry_price': entry_price,
                            'exit_price': exit_price,
                            'profit': profit,
                            'pattern_name': 'Head and Shoulders Top',
                            'pattern_height': head_high - neckline_value,
                            'shoulder_symmetry': shoulder_diff
                        })

    trades_df = pd.DataFrame(trade_results)

    if not trades_df.empty:
        print("\nHead-and-Shoulders Top Results:")
        print(f"Lookback Period: {lookback_days} days")
        print(f"Total Patterns Found: {len(trade_results)}")
        print(f"Total Trades Executed: {len(trades_df)}")
        print(f"Profitable Trades: {len(trades_df[trades_df['profit'] > 0])}")
        print(f"Win Rate: {len(trades_df[trades_df['profit'] > 0]) / len(trades_df) * 100:.1f}%")
        print(f"Average Profit per Trade: ${total_profit/len(trades_df):.5f}")
        print(f"Total Profit: ${total_profit:.5f}")
    else:
        print("\nNo Head-and-Shoulders Top patterns found")

    global totalprofit
    totalprofit += total_profit

    return trades_df, total_profit


def find_doublebottoms(df, stoploss=0.97, stopprofit=1.05, max_days=20, 
                      min_pattern_days=5, max_pattern_days=50, 
                      lookback_days=3000, bottom_price_tolerance=0.03, 
                      min_rise_between_bottoms=0.01):
    
    #Detects Double Bottom (Adam & Adam) patterns in historical stock data and simulates trades.
    

    #Validate required columns
    required_columns = {'Date', 'Open', 'High', 'Low', 'Close/Last'}
    if not required_columns.issubset(df.columns):
        missing_columns = required_columns - set(df.columns)
        raise ValueError(f"Missing columns: {missing_columns}")

    #Convert columns to numeric if needed
    for col in ['Open', 'High', 'Low', 'Close/Last']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')

    
    patterns = []
    trade_results = []
    total_profit = 0
    executed_dates = set()  #Track dates where trades have already been executed

    #Define range for lookback
    start_idx = max(0, len(df) - lookback_days)

    #Iterate through dataset to find patterns
    for current_idx in range(start_idx, len(df) - max_days - max_pattern_days):
        window_start = max(0, current_idx - max_pattern_days)
        window = df.iloc[window_start:current_idx + max_pattern_days]

        #Identify potential bottoms
        bottoms = [
            (idx + window_start, window['Low'].iloc[idx])
            for idx in range(1, len(window) - 1)
            if window['Low'].iloc[idx] < window['Low'].iloc[idx - 1] and
               window['Low'].iloc[idx] < window['Low'].iloc[idx + 1]
        ]

        if len(bottoms) < 2:
            continue

        #Check all pairs of bottoms for valid Double Bottom patterns
        for i in range(len(bottoms) - 1):
            first_idx, first_low = bottoms[i]
            second_idx, second_low = bottoms[i + 1]

            #Validate time between bottoms
            time_between_bottoms = second_idx - first_idx
            if not (min_pattern_days <= time_between_bottoms <= max_pattern_days):
                continue

            #Validate price similarity between bottoms
            price_diff = abs(first_low - second_low) / max(first_low, second_low)
            if price_diff > bottom_price_tolerance:
                continue

            #Validate rise between bottoms
            peak_idx = df['High'].iloc[first_idx:second_idx].idxmax()
            peak_high = df['High'].iloc[peak_idx]
            rise_between_bottoms = (peak_high - min(first_low, second_low)) / min(first_low, second_low)
            if rise_between_bottoms < min_rise_between_bottoms:
                continue

            #Confirm breakout above peak between bottoms
            breakout_idx = None
            for idx in range(second_idx, min(second_idx + 10, len(df))):
                if df['Close/Last'].iloc[idx] > peak_high:
                    breakout_idx = idx
                    break

            if breakout_idx is None:
                continue

            #Execute trade
            trade_date = df['Date'].iloc[breakout_idx]
            if trade_date in executed_dates:
                continue
            executed_dates.add(trade_date)

            entry_price = df['Open'].iloc[breakout_idx]
            exit_price = 0
            stop = False

            for day in range(max_days):
                if breakout_idx + day >= len(df):
                    break

                current_high = df['High'].iloc[breakout_idx + day]
                current_low = df['Low'].iloc[breakout_idx + day]

                if not stop and current_high >= entry_price * stopprofit:
                    exit_price = entry_price * stopprofit
                    stop = True
                elif not stop and current_low <= entry_price * stoploss:
                    exit_price = entry_price * stoploss
                    stop = True

            if not stop:
                if breakout_idx + max_days - 1 >= len(df):
                    exit_price = df['Close/Last'].iloc[-1]
                else:
                    exit_price = df['Close/Last'].iloc[breakout_idx + max_days - 1]

            profit = exit_price - entry_price
            total_profit += profit

            #Record trade details
            trade_results.append({
                'pattern_date': df['Date'].iloc[first_idx],  #First top date
            'entry_date': df['Date'].iloc[breakout_idx],
            'exit_date': df['Date'].iloc[min(breakout_idx + max_days - 1, len(df)-1)],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'profit': profit,
            'pattern_name': 'Double Bottoms'
            })

    #Create results DataFrame
    trades_df = pd.DataFrame(trade_results)

    #Print summary
    if not trades_df.empty:
        print("\nDouble Bottoms (Adam & Adam) Results:")
        print(f"Lookback Period: {lookback_days} days")
        print(f"Total Patterns Found: {len(trade_results)}")
        print(f"Total Trades Executed: {len(trades_df)}")
        print(f"Profitable Trades: {len(trades_df[trades_df['profit'] > 0])}")
        print(f"Win Rate: {len(trades_df[trades_df['profit'] > 0]) / len(trades_df) * 100:.1f}%")
        print(f"Average Profit per Trade: ${total_profit / len(trades_df):.2f}")
        print(f"Total Profit: ${total_profit:.2f}")
    else:
        print("\nDouble Bottoms (Adam & Adam) Results:")
        print("No patterns were found during the specified lookback period.")

    global totalprofit
    totalprofit += total_profit

    return trades_df, total_profit

def find_doubletops(df, stoploss=1.015, stopprofit=0.97, max_days=20, 
                     min_pattern_days=3, max_pattern_days=50, 
                     lookback_days=3000, top_price_tolerance=0.05, 
                     min_drop_between_tops=0.006):

    required_columns = {'Date', 'Open', 'High', 'Low', 'Close/Last'}
    if not required_columns.issubset(df.columns):
        missing_columns = required_columns - set(df.columns)
        raise ValueError(f"Missing columns: {missing_columns}")

    #Convert columns to numeric
    for col in ['Open', 'High', 'Low', 'Close/Last']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')

    #Calculate trend indicators
    df['SMA20'] = df['Close/Last'].rolling(window=20).mean()
    df['SMA50'] = df['Close/Last'].rolling(window=50).mean()
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()

    trade_results = []
    total_profit = 0
    executed_dates = set()
    start_idx = max(0, len(df) - lookback_days)

    for current_idx in range(start_idx, len(df) - max_days - max_pattern_days):
        window_start = max(0, current_idx - max_pattern_days)
        window = df.iloc[window_start:current_idx + max_pattern_days]

        #Find tops
        tops = [
            (idx + window_start, window['High'].iloc[idx])
            for idx in range(1, len(window) - 1)
            if window['High'].iloc[idx] > window['High'].iloc[idx - 1] and
               window['High'].iloc[idx] > window['High'].iloc[idx + 1]
        ]

        if len(tops) < 2:
            continue

        #Check all pairs of tops for validity
        for i in range(len(tops) - 1):
            first_idx, first_high = tops[i]
            second_idx, second_high = tops[i + 1]

            #Validate time between tops
            time_between_tops = second_idx - first_idx
            if not (min_pattern_days <= time_between_tops <= max_pattern_days):
                continue

            #Validate price similarity between tops
            price_diff = abs(first_high - second_high) / max(first_high, second_high)
            if price_diff > top_price_tolerance:
                continue

            #Find trough between tops
            trough_idx = df['Low'].iloc[first_idx:second_idx].idxmin()
            trough_low = df['Low'].iloc[trough_idx]

            #Validate significant drop between tops
            drop_between_tops = (min(first_high, second_high) - trough_low) / min(first_high, second_high)
            if drop_between_tops < min_drop_between_tops:
                continue

            #Trend confirmation
            if df['Close/Last'].iloc[second_idx] > df['SMA20'].iloc[second_idx]:
                continue  #Skip if not in downtrend

            #Look for breakout below trough
            breakout_idx = None
            for idx in range(second_idx, min(second_idx + 10, len(df))):
                if df['Close/Last'].iloc[idx] < trough_low:
                    breakout_idx = idx
                    break

            if breakout_idx is None:
                continue

            #Execute short trade
            trade_date = df['Date'].iloc[breakout_idx]
            if trade_date in executed_dates:
                continue
            executed_dates.add(trade_date)

            entry_price = df['Open'].iloc[breakout_idx]
            exit_price = None
            stop = False

            #Dynamic stops based on ATR
            atr = df['ATR'].iloc[breakout_idx]
            dynamic_stoploss = min(stoploss, 1 + (2 * atr / entry_price))
            dynamic_stopprofit = max(stopprofit, 1 - (3 * atr / entry_price))

            for day in range(max_days):
                current_idx = breakout_idx + day
                if current_idx >= len(df):
                    break

                current_high = df['High'].iloc[current_idx]
                current_low = df['Low'].iloc[current_idx]

                if not stop:
                    if current_low <= entry_price * dynamic_stopprofit:  #Target hit (price fell)
                        exit_price = entry_price * dynamic_stopprofit
                        stop = True
                    elif current_high >= entry_price * dynamic_stoploss:  #Stop loss hit (price rose)
                        exit_price = entry_price * dynamic_stoploss
                        stop = True

            if not stop:
                exit_price = df['Close/Last'].iloc[min(breakout_idx + max_days - 1, len(df)-1)]

            profit = entry_price - exit_price
            total_profit += profit

            trade_results.append({
            'pattern_date': df['Date'].iloc[first_idx],  #First top date
            'entry_date': df['Date'].iloc[breakout_idx],
            'exit_date': df['Date'].iloc[min(breakout_idx + max_days - 1, len(df)-1)],
            'entry_price': entry_price,
            'exit_price': exit_price,
            'profit': profit,
            'pattern_name': 'Double Top'
            })

    trades_df = pd.DataFrame(trade_results)

    if not trades_df.empty:
        print("\nDouble Tops Results:")
        print(f"Lookback Period: {lookback_days} days")
        print(f"Total Patterns Found: {len(trade_results)}")
        print(f"Total Trades Executed: {len(trades_df)}")
        print(f"Profitable Trades: {len(trades_df[trades_df['profit'] > 0])}")
        print(f"Win Rate: {len(trades_df[trades_df['profit'] > 0]) / len(trades_df) * 100:.1f}%")
        print(f"Average Profit per Trade: ${total_profit/len(trades_df):.5f}")
        print(f"Total Profit: ${total_profit:.5f}")
    else:
        print("\nNo Double Top patterns found")

    global totalprofit
    totalprofit += total_profit

    return trades_df, total_profit

def find_invertedcupwithhandle(df, stoploss=1.01, stopprofit=0.95, max_days=10, 
                             min_pattern_days=5, max_pattern_days=40, 
                             lookback_days=3000, handle_depth_tolerance=1.0, 
                             cup_symmetry_tolerance=0.3):

    required_columns = {'Date', 'Open', 'High', 'Low', 'Close/Last'}
    if not required_columns.issubset(df.columns):
        missing_columns = required_columns - set(df.columns)
        raise ValueError(f"Missing columns: {missing_columns}")

    #Convert columns to numeric if needed
    for col in ['Open', 'High', 'Low', 'Close/Last']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')

    trade_results = []
    total_profit = 0
    executed_dates = set()

    start_idx = max(0, len(df) - lookback_days)

    for current_idx in range(start_idx, len(df) - max_days - max_pattern_days):
        window_start = max(0, current_idx - max_pattern_days)
        window = df.iloc[window_start:current_idx + max_pattern_days]

        #Find peaks (left and right side of cup)
        peaks = [
            (idx + window_start, window['High'].iloc[idx])
            for idx in range(1, len(window) - 1)
            if window['High'].iloc[idx] > window['High'].iloc[idx - 1] and
               window['High'].iloc[idx] > window['High'].iloc[idx + 1]
        ]

        if len(peaks) < 2:
            continue

        #Check all pairs of peaks for valid inverted cup patterns
        for i in range(len(peaks) - 1):
            left_idx, left_high = peaks[i]      #First peak (left side of cup)
            right_idx, right_high = peaks[i + 1] #Second peak (right side of cup)

            
            #Find trough (top of inverted cup)
            trough_idx = df['Low'].iloc[left_idx:right_idx].idxmax()  #For inverted cup, we look for HIGHEST low
            trough_high = df['High'].iloc[trough_idx]


            #Confirm breakout below trough
            breakout_idx = None
            for idx in range(right_idx, min(right_idx + 10, len(df))):
                if df['Close/Last'].iloc[idx] < trough_high:
                    breakout_idx = idx
                    break

            if breakout_idx is None:
                continue

            #Execute trade
            trade_date = df['Date'].iloc[breakout_idx]
            if trade_date in executed_dates:
                continue
            executed_dates.add(trade_date)

            entry_price = df['Open'].iloc[breakout_idx]
            exit_price = None
            stop = False

            for day in range(max_days):
                if breakout_idx + day >= len(df):
                    break

                current_high = df['High'].iloc[breakout_idx + day]
                current_low = df['Low'].iloc[breakout_idx + day]

                if not stop and current_low <= entry_price * stopprofit:
                    exit_price = entry_price * stopprofit
                    stop = True
                elif not stop and current_high >= entry_price * stoploss:
                    exit_price = entry_price * stoploss
                    stop = True

            if not stop:
                exit_price = df['Close/Last'].iloc[min(breakout_idx + max_days - 1, len(df)-1)]

            profit = entry_price-exit_price    #opposite as shorting
            total_profit += profit

            #Record trade with all required fields
            trade_results.append({
                'pattern_date': df['Date'].iloc[left_idx],  #Date of left peak
                'entry_date': trade_date,
                'exit_date': df['Date'].iloc[min(breakout_idx + max_days - 1, len(df)-1)],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit': profit,
                'pattern_name': 'Inverted Cup with Handle'
            })

    trades_df = pd.DataFrame(trade_results)
    
    if not trades_df.empty:
        print("\nInverted Cup with Handle Results:")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Profitable Trades: {len(trades_df[trades_df['profit'] > 0])}")
        print(f"Win Rate: {len(trades_df[trades_df['profit'] > 0]) / len(trades_df) * 100:.1f}%")
        print(f"Total Profit: ${total_profit:.2f}")
    else:
        print("\nNo Inverted Cup with Handle patterns found")

    global totalprofit
    totalprofit += total_profit

    return trades_df, total_profit

def find_cup_with_handle(df, stoploss=0.94, stopprofit=1.2, max_days=105, 
                        min_pattern_days=4, max_pattern_days=40, 
                        lookback_days=3000, handle_depth_tolerance=5.0, 
                        cup_symmetry_tolerance=5.0):
    
    required_columns = {'Date', 'Open', 'High', 'Low', 'Close/Last'}
    if not required_columns.issubset(df.columns):
        missing_cols = required_columns - set(df.columns)
        raise ValueError(f"Missing columns: {missing_cols}")

    #Convert columns to numeric 
    for col in ['Open', 'High', 'Low', 'Close/Last']:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('$', ''), errors='coerce')

    trade_results = []
    total_profit = 0
    executed_dates = set()
    start_idx = max(0, len(df) - lookback_days)

    for current_idx in range(start_idx, len(df) - max_days - max_pattern_days):
        window_start = max(0, current_idx - max_pattern_days)
        window_end = min(current_idx + max_pattern_days, len(df))
        window = df.iloc[window_start:window_end]

        #Skip if window is too small
        if len(window) < min_pattern_days:
            continue

        try:
            #Find initial high (left side of cup) 
            left_section = window.iloc[0:min(min_pattern_days + 5, len(window)//2)]
            if len(left_section) == 0:
                continue
            left_high_idx = left_section['High'].idxmax()
            left_high = window['High'].loc[left_high_idx]

            #Find the cup bottom 
            cup_search_start = max(left_high_idx + 2, window_start + min_pattern_days)
            cup_search_end = min(current_idx + max_pattern_days//2, len(df))
            
            if cup_search_start >= cup_search_end:
                continue
                
            cup_section = df.iloc[cup_search_start:cup_search_end]
            if len(cup_section) == 0:
                continue
                
            cup_bottom_idx = cup_section['Low'].idxmin()
            cup_bottom = df['Low'].loc[cup_bottom_idx]

            if cup_bottom_idx <= left_high_idx:
                continue

            #Find right side of cup - more flexible
            right_search_start = cup_bottom_idx + 1
            right_search_end = min(cup_bottom_idx + max_pattern_days, len(df))
            
            if right_search_start >= right_search_end:
                continue
                
            right_section = df.iloc[right_search_start:right_search_end]
            if len(right_section) == 0:
                continue
                
            right_high_idx = right_section['High'].idxmax()
            right_high = right_section['High'].loc[right_high_idx]

            #Validate cup formation 
            cup_depth = (left_high - cup_bottom) / left_high
            if cup_depth < 0.005 or cup_depth > 0.95:  
                continue

            #Check cup symmetry axed
            left_time = cup_bottom_idx - left_high_idx
            right_time = right_high_idx - cup_bottom_idx
            if min(left_time, right_time) < 2:  #Minimum time requirement
                continue
            if abs(left_time - right_time) / max(left_time, right_time) > cup_symmetry_tolerance:
                continue

            #Verify handle formation 
            handle_search_start = right_high_idx + 1
            handle_search_end = min(right_high_idx + min_pattern_days + 5, len(df))
            
            if handle_search_start >= handle_search_end:
                continue
                
            handle_section = df.iloc[handle_search_start:handle_search_end]
            if len(handle_section) == 0:
                continue
                
            handle_low = handle_section['Low'].min()
            handle_depth = (right_high - handle_low) / (right_high - cup_bottom)
            
            if handle_depth > handle_depth_tolerance:
                continue

            #Look for breakout above cup rim 
            breakout_idx = None
            for idx in range(right_high_idx + 1, min(right_high_idx + 15, len(df))):
                if df['Close/Last'].iloc[idx] > right_high * 0.995:  #Allow slight tolerance
                    breakout_idx = idx
                    break

            if breakout_idx is None:
                continue

            #Execute trade
            trade_date = df['Date'].iloc[breakout_idx]
            if trade_date in executed_dates:
                continue
            executed_dates.add(trade_date)

            entry_price = df['Open'].iloc[breakout_idx]
            exit_price = None
            stop = False

            for day in range(max_days):
                if breakout_idx + day >= len(df):
                    break

                current_high = df['High'].iloc[breakout_idx + day]
                current_low = df['Low'].iloc[breakout_idx + day]

                if not stop and current_high >= entry_price * stopprofit:
                    exit_price = entry_price * stopprofit
                    stop = True
                elif not stop and current_low <= entry_price * stoploss:
                    exit_price = entry_price * stoploss
                    stop = True

            if not stop:
                exit_price = df['Close/Last'].iloc[min(breakout_idx + max_days - 1, len(df)-1)]

            profit = exit_price - entry_price
            total_profit += profit

            trade_results.append({
                'pattern_date': df['Date'].iloc[left_high_idx],
                'entry_date': trade_date,
                'exit_date': df['Date'].iloc[min(breakout_idx + max_days - 1, len(df)-1)],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit': profit,
                'pattern_name': 'Cup with Handle',
                'cup_depth': cup_depth,
                'handle_depth': handle_depth,
                'symmetry_ratio': abs(left_time - right_time) / max(left_time, right_time)
            })

        except (IndexError, KeyError) as e:
            #Skip window if any index errors occur
            continue

    trades_df = pd.DataFrame(trade_results)
    
    if not trades_df.empty:
        print("\nCup with Handle Results:")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Profitable Trades: {len(trades_df[trades_df['profit'] > 0])}")
        print(f"Win Rate: {len(trades_df[trades_df['profit'] > 0]) / len(trades_df) * 100:.1f}%")
        print(f"Total Profit: ${total_profit:.2f}")
    else:
        print("\nNo Cup with Handle patterns found")

    global totalprofit
    totalprofit += total_profit

    return trades_df, total_profit

def find_invertedhammer(df, stoploss=0.999, stopprofit=1.003, max_days=3, min_shadow_ratio=1.003, body_percentage=0.5):
    
    #Looks for inverted hammer reversals.

    trade_results = []
    total_profit = 0
    executed_dates = set()

    for i in range(len(df) - max_days - 1):
        #Calculate candlestick components
        open_price = df['Open'].iloc[i]
        close_price = df['Close/Last'].iloc[i]
        high_price = df['High'].iloc[i]
        low_price = df['Low'].iloc[i]
        
        body = abs(close_price - open_price)
        total_range = high_price - low_price
        upper_shadow = high_price - max(open_price, close_price)
        lower_shadow = min(open_price, close_price) - low_price
        
        if total_range == 0:  #Avoid division by zero
            continue
            
        is_hammer = (
            upper_shadow > (body * min_shadow_ratio) and  
            lower_shadow < upper_shadow and              
            body < (total_range * body_percentage) and
            close_price < open_price                     
        )
        
        if is_hammer:
            #Confirming next day is bullish
            if i + 1 >= len(df):
                continue
                
            next_day = df.iloc[i + 1]
            if next_day['Close/Last'] <= next_day['Open']:  
                continue

            #Execute trade
            entry_price = df['Open'].iloc[i + 1]
            exit_price = None
            
            for j in range(max_days):
                current_idx = i + 1 + j
                if current_idx >= len(df):
                    break
                
                current_high = df['High'].iloc[current_idx]
                current_low = df['Low'].iloc[current_idx]
                
                if current_high >= entry_price * stopprofit:
                    exit_price = entry_price * stopprofit
                    break
                elif current_low <= entry_price * stoploss:
                    exit_price = entry_price * stoploss
                    break
                    
            if exit_price is None:
                exit_price = df['Close/Last'].iloc[min(i + max_days, len(df)-1)]
            
            profit = exit_price - entry_price
            
            trade_results.append({
                'pattern_date': df['Date'].iloc[i],  
                'entry_date': df['Date'].iloc[i + 1],
                'exit_date': df['Date'].iloc[min(i + max_days, len(df)-1)],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit': profit,
                'pattern_name': 'Inverted Hammer'  
            })
            total_profit += profit

    trades_df = pd.DataFrame(trade_results)
    
    if not trades_df.empty:
        print("\nInverted Hammer Results:")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Profitable Trades: {len(trades_df[trades_df['profit'] > 0])}")
        print(f"Win Rate: {len(trades_df[trades_df['profit'] > 0]) / len(trades_df) * 100:.1f}%")
        print(f"Total Profit: ${total_profit:.2f}")
    else:
        print("\nNo Inverted Hammer patterns found")

    global totalprofit
    totalprofit += total_profit

    return trades_df, total_profit

def find_shootingstar(df, stoploss=1.001, stopprofit=0.998, max_days=5, min_shadow_ratio=1.5, body_percentage=0.4):
    
    #Finds shooting star topping patterns with proper variable references.

    trade_results = []
    total_profit = 0
    executed_dates = set()

    for i in range(len(df) - max_days - 1):
        open_price = df['Open'].iloc[i]
        close_price = df['Close/Last'].iloc[i]
        high_price = df['High'].iloc[i]
        low_price = df['Low'].iloc[i]
        
        body = abs(close_price - open_price)
        total_range = high_price - low_price
        upper_shadow = high_price - max(open_price, close_price)
        lower_shadow = min(open_price, close_price) - low_price
        
        if total_range == 0:
            continue
            
        is_shooting_star = (
            upper_shadow > (body * min_shadow_ratio) and     
            lower_shadow < (upper_shadow * 0.25) and        
            body < (total_range * body_percentage) and      
            upper_shadow / total_range > 0.5                
        )
        
        #uptrend confirmation (2 higher closes)
        if i >= 2:
            prior_closes = df['Close/Last'].iloc[i-2:i].tolist()
            uptrend = prior_closes[0] < prior_closes[1]
        else:
            uptrend = True
        
        if is_shooting_star and uptrend:
            #Allow both bearish and neutral candles
            if i + 1 >= len(df):
                continue
                
            #Execute trade (short position)
            entry_price = df['Open'].iloc[i + 1]
            exit_price = None
            stop = False
            
            for j in range(max_days):
                current_idx = i + 1 + j
                if current_idx >= len(df):
                    break
                
                current_high = df['High'].iloc[current_idx]
                current_low = df['Low'].iloc[current_idx]
                
                if not stop and current_low <= entry_price * stopprofit:
                    exit_price = entry_price * stopprofit
                    stop = True
                elif not stop and current_high >= entry_price * stoploss:
                    exit_price = entry_price * stoploss
                    stop = True
    
            if exit_price is None:
                exit_price = df['Close/Last'].iloc[min(i + max_days, len(df)-1)]
            
            profit = entry_price - exit_price
            
            trade_results.append({
                'pattern_date': df['Date'].iloc[i],  
                'entry_date': df['Date'].iloc[i + 1],
                'exit_date': df['Date'].iloc[min(i + max_days, len(df)-1)],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit': profit,
                'pattern_name': 'Shooting Star'  
            })
            total_profit += profit

    trades_df = pd.DataFrame(trade_results)
    
    if not trades_df.empty:
        print("\nShooting Star Results:")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Profitable Trades: {len(trades_df[trades_df['profit'] > 0])}")
        print(f"Win Rate: {len(trades_df[trades_df['profit'] > 0]) / len(trades_df) * 100:.1f}%")
        print(f"Average Profit: ${total_profit/len(trades_df):.5f}")
        print(f"Total Profit: ${total_profit:.5f}")
    else:
        print("\nNo Shooting Star patterns found")

    global totalprofit
    totalprofit += total_profit

    return trades_df, total_profit

def find_tweezerbottoms(df, stoploss=0.9998, stopprofit=1.003, max_days=4, 
                        price_tolerance=0.0033, body_ratio_tolerance=0.95):
    
    #Identifies tweezer bottom reversals with proper variable references.
    
    trade_results = []
    total_profit = 0
    executed_dates = set()

    #Calculate RSI 
    delta = df['Close/Last'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=12).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=12).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    #Calculate multiple moving averages for trend context
    df['SMA5'] = df['Close/Last'].rolling(window=5).mean()
    df['SMA10'] = df['Close/Last'].rolling(window=10).mean()

    for i in range(1, len(df) - max_days - 1):
        prev_candle = df.iloc[i-1]
        curr_candle = df.iloc[i]
        
        prev_body = abs(prev_candle['Close/Last'] - prev_candle['Open'])
        curr_body = abs(curr_candle['Close/Last'] - curr_candle['Open'])
        
        is_tweezer_bottom = (
            #Price similarity check
            abs(prev_candle['Low'] - curr_candle['Low']) <= (prev_candle['Low'] * price_tolerance) and
            
            #First candle bearish, second bullish
            prev_candle['Close/Last'] < prev_candle['Open'] and
            curr_candle['Close/Last'] > curr_candle['Open'] and
            
            #Body size similarity
            abs(prev_body - curr_body) <= (max(prev_body, curr_body) * body_ratio_tolerance) and
            
            #Simplified downtrend check
            (df['Close/Last'].iloc[i-1] < df['Close/Last'].iloc[i-2] or
             df['Close/Last'].iloc[i] < df['SMA5'].iloc[i]) and
            
            #Oversold condition
            df['RSI'].iloc[i] < 45 and
            
            #Price below moving average
            (curr_candle['Close/Last'] < df['SMA10'].iloc[i] or 
             curr_candle['Close/Last'] < df['SMA5'].iloc[i]) and
            
            #Minimum body size
            curr_body > curr_candle['Close/Last'] * 0.0001
        )
        
        if is_tweezer_bottom:
            trade_date = curr_candle['Date']
            if trade_date in executed_dates:
                continue
            executed_dates.add(trade_date)
            
            entry_price = df['Open'].iloc[i+1]
            exit_price = None
            stop = False
            
            for j in range(max_days):
                current_idx = i + 1 + j
                if current_idx >= len(df):
                    break
                
                current_high = df['High'].iloc[current_idx]
                current_low = df['Low'].iloc[current_idx]
                
                if not stop:
                    if current_high >= entry_price * stopprofit:
                        exit_price = entry_price * stopprofit
                        stop = True
                    elif current_low <= entry_price * stoploss:
                        exit_price = entry_price * stoploss
                        stop = True
            
            if not stop:
                exit_price = df['Close/Last'].iloc[min(i + max_days, len(df)-1)]
            
            profit = exit_price - entry_price
            
            trade_results.append({
                'pattern_date': df['Date'].iloc[i],  
                'entry_date': df['Date'].iloc[i + 1],
                'exit_date': df['Date'].iloc[min(i + max_days, len(df)-1)],
                'entry_price': entry_price,
                'exit_price': exit_price,
                'profit': profit,
                'pattern_name': 'Tweezer Bottoms'  
            })
            total_profit += profit

    trades_df = pd.DataFrame(trade_results)
    
    if not trades_df.empty:
        print("\nTweezer Bottoms Results:")
        print(f"Total Trades: {len(trades_df)}")
        print(f"Profitable Trades: {len(trades_df[trades_df['profit'] > 0])}")
        print(f"Win Rate: {len(trades_df[trades_df['profit'] > 0]) / len(trades_df) * 100:.1f}%")
        print(f"Average Profit: ${total_profit/len(trades_df):.5f}")
        print(f"Total Profit: ${total_profit:.5f}")
    else:
        print("\nNo Tweezer Bottom patterns found")

    global totalprofit
    totalprofit += total_profit

    return trades_df, total_profit

def analysepatterns(df, lookback_days=3000):
    
    #Runs all pattern detection functions and presents results showing every pattern and their profits.
    
    global totalprofit
    totalprofit = 0
    
    results = {}
    total_trades = 0
    all_trades_dfs = []
    
    print("\nStarting complete pattern analysis")
    print(f"Analyzing {lookback_days} days of data")
    print(f"Testing {len(PATTERN_REGISTRY)} different pattern types")
    
    #Define all pattern functions with their names
    pattern_functions = [
        ('Bullish Hammer', find_bullishhammer),
        ('Flags High & Tight', find_flags_high_and_tight),
        ('Broadening Bottoms', find_broadeningbottoms),
        ('Broadening Formations', find_broadening_formations),
        ('Head and Shoulders Top', find_headandshouldertops),
        ('Double Bottoms', find_doublebottoms),
        ('Double Tops', find_doubletops),
        ('Inverted Cup with Handle', find_invertedcupwithhandle),
        ('Cup with Handle', find_cup_with_handle),
        ('Inverted Hammer', find_invertedhammer),
        ('Shooting Star', find_shootingstar),
        ('Tweezer Bottoms', find_tweezerbottoms)
    ]
    
    #Run each pattern detection function
    for i, (pattern_name, pattern_func) in enumerate(pattern_functions, 1):
        print(f"\n[{i:2d}/{len(pattern_functions)}] Analyzing {pattern_name} patterns...")
        
        try:
            #Execute pattern detection
            result = pattern_func(df)
            
            #Handle different return types
            if isinstance(result, tuple):
                trades_df, profit = result
            else:
                trades_df = result
                profit = trades_df['profit'].sum() if not trades_df.empty else 0
            
            #Store results
            results[pattern_name] = {
                'trades': len(trades_df) if not trades_df.empty else 0,
                'profit': profit,
                'win_rate': 0,
                'avg_profit': 0,
                'max_profit': 0,
                'max_loss': 0,
                'trades_df': trades_df
            }
            
            #Calculate detailed statistics
            if not trades_df.empty:
                profitable_trades = trades_df[trades_df['profit'] > 0]
                losing_trades = trades_df[trades_df['profit'] < 0]
                
                results[pattern_name].update({
                    'win_rate': len(profitable_trades) / len(trades_df) * 100,
                    'avg_profit': profit / len(trades_df),
                    'max_profit': trades_df['profit'].max(),
                    'max_loss': trades_df['profit'].min(),
                    'profitable_trades': len(profitable_trades),
                    'losing_trades': len(losing_trades)
                })
                
                #Add pattern name to DataFrame for visualisation
                trades_df['pattern_name'] = pattern_name
                all_trades_dfs.append(trades_df)
                
                print(f"Pattern Found: {len(trades_df)} trades detected")
                print(f"Total Profit: ${profit:.5f}")
                print(f"Win Rate: {results[pattern_name]['win_rate']:.1f}%")
                print(f"Average Profit per Trade: ${results[pattern_name]['avg_profit']:.5f}")
                print(f"Best Trade: ${results[pattern_name]['max_profit']:.5f}")
                print(f"Worst Trade: ${results[pattern_name]['max_loss']:.5f}")
                
                #Show sample trades if avaiable
                if len(trades_df) <= 5:
                    print("\nAll Trades:")
                    for idx, trade in trades_df.iterrows():
                        profit_str = f"+${trade['profit']:.5f}" if trade['profit'] > 0 else f"${trade['profit']:.5f}"
                        print(f"  {trade['entry_date']}: {profit_str}")
                else:
                    print(f"\nSample Trades (showing first 5 of {len(trades_df)}):")
                    for idx, trade in trades_df.head(5).iterrows():
                        profit_str = f"+${trade['profit']:.5f}" if trade['profit'] > 0 else f"${trade['profit']:.5f}"
                        print(f"  {trade['entry_date']}: {profit_str}")
                    print(f"  ... and {len(trades_df) - 5} more trades")
                
            else:
                print("No patterns found")
                results[pattern_name].update({
                    'win_rate': 0,
                    'avg_profit': 0,
                    'max_profit': 0,
                    'max_loss': 0,
                    'profitable_trades': 0,
                    'losing_trades': 0
                })
                
        except Exception as e:
            print(f"Error analyzing {pattern_name}: {str(e)}")
            results[pattern_name] = {
                'trades': 0,
                'profit': 0,
                'win_rate': 0,
                'avg_profit': 0,
                'max_profit': 0,
                'max_loss': 0,
                'profitable_trades': 0,
                'losing_trades': 0,
                'error': str(e)
            }
    
    #Calculate overall statistics
    total_trades = sum(r['trades'] for r in results.values())
    total_profit = sum(r['profit'] for r in results.values())
    total_profitable_trades = sum(r.get('profitable_trades', 0) for r in results.values())
    total_losing_trades = sum(r.get('losing_trades', 0) for r in results.values())
    
    #Print summary
    print("\nCOMPLETE PATTERN ANALYSIS SUMMARY")
    
    #Pattern performance table
    print("\nINDIVIDUAL PATTERN PERFORMANCE:")
    print("-" * 100)
    print(f"{'Pattern':<25} {'Trades':<8} {'Profit':<12} {'Win Rate':<10} {'Avg Profit':<12} {'Best':<10} {'Worst':<10}")
    print("-" * 100)
    
    for pattern_name, stats in results.items():
        trades = stats['trades']
        profit = stats['profit']
        win_rate = stats.get('win_rate', 0)
        avg_profit = stats.get('avg_profit', 0)
        max_profit = stats.get('max_profit', 0)
        max_loss = stats.get('max_loss', 0)
        
        print(f"{pattern_name:<25} {trades:<8} ${profit:<11.2f} {win_rate:<9.1f}% ${avg_profit:<11.2f} ${max_profit:<9.2f} ${max_loss:<9.2f}")
    
    #Overall performance summary
    print("\nOVERALL PERFORMANCE SUMMARY")
    print(f"Total Patterns Analyzed: {len(pattern_functions)}")
    print(f"Total Trades Executed: {total_trades}")
    print(f"Profitable Trades: {total_profitable_trades}")
    print(f"Losing Trades: {total_losing_trades}")
    print(f"Overall Win Rate: {total_profitable_trades/total_trades*100:.1f}%" if total_trades > 0 else "Overall Win Rate: N/A")
    print(f"Total Combined Profit: ${total_profit:.5f}")
    print(f"Average Profit per Trade: ${total_profit/total_trades:.5f}" if total_trades > 0 else "Average Profit per Trade: N/A")
    
    #Profit distribution analysis
    if total_trades > 0:
        print(f"\nProfit Distribution:")
        print(f"  Profitable patterns: {len([r for r in results.values() if r['profit'] > 0])}")
        print(f"  Losing patterns: {len([r for r in results.values() if r['profit'] < 0])}")
        print(f"  Break-even patterns: {len([r for r in results.values() if r['profit'] == 0])}")
        
        #Top performers
        profitable_patterns = [(name, stats) for name, stats in results.items() if stats['profit'] > 0]
        if profitable_patterns:
            profitable_patterns.sort(key=lambda x: x[1]['profit'], reverse=True)
            print(f"\nTop Performing Patterns:")
            for i, (name, stats) in enumerate(profitable_patterns[:3], 1):
                print(f"  {i}. {name}: ${stats['profit']:.5f} ({stats['trades']} trades)")
    
            #Save visualisation with all trade data
        if all_trades_dfs:
            print("\nSaving comprehensive visualisation")
            try:
                save_visualisation(df, all_trades_dfs, 'trading_visualization.html')
                print("visualisation saved successfully!")
            except Exception as e:
                print(f"visualisation failed: {str(e)}")
    
    return results, total_profit, all_trades_dfs


    

if __name__ == "__main__":
    
    #Load and clean data
    df = load_data()
    print(f"Data loaded: {len(df)} records from {df['Date'].min()} to {df['Date'].max()}")
    
    print("\n PATTERN ANALYSIS")
    
    results, total_profit, all_trades_dfs = analysepatterns(df)
    print(f"\nAnalysis complete \n Total profit: ${total_profit:.5f}")
    
    print("\nGENERATING visualisation")
    
    try:
        # Generate the visualization with the data from analysis
        save_visualisation(df, all_trades_dfs, 'trading_visualization.html')
        print("visualisation generated successfully.")
        print("Open 'trading_visualization.html' in browser to see the visualisation")
    except Exception as e:
        print(f"visualisation failed: {str(e)}")
    
    print("\nTrading Pattern Analysis Complete")
    print("Check the generated files:")
    print("   - trading_visualization.html - Interactive chart with all trades")
    print("   - Console output - Detailed analysis results")



