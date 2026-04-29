async function loadData() {
    try {
        // Try to load from API first, fallback to local JSON
        const portfolio = await fetchData('portfolio.json');
        const equity = await fetchData('equity_curve.json');
        const backtest = await fetchLatestBacktest();
        
        updateDashboard(portfolio, equity, backtest);
    } catch (e) {
        console.error('Failed to load data:', e);
        document.getElementById('capital').textContent = 'No Data';
    }
}

async function fetchData(filename) {
    try {
        const response = await fetch(`http://localhost:8000/${filename}`);
        if (response.ok) return await response.json();
    } catch (e) {}
    // Fallback to local file
    const response = await fetch(`data/${filename}`);
    return await response.json();
}

async function fetchLatestBacktest() {
    // For now, return null - in real use, scan for latest backtest file
    return null;
}

function updateElementIfChanged(id, newValue) {
    const el = document.getElementById(id);
    if (el && el.textContent !== newValue) {
        el.textContent = newValue;
    }
}

function positionsChanged(newPositions) {
    const tbody = document.getElementById('positions-table');
    const rows = tbody.querySelectorAll('tr');
    if (!newPositions && rows.length === 0) return false;
    if (!newPositions || rows.length !== newPositions.length) return true;
    
    for (let i = 0; i < newPositions.length; i++) {
        const pos = newPositions[i];
        const cells = rows[i].querySelectorAll('td');
        if (cells[0].textContent !== pos.instrument) return true;
        const dir = pos.units > 0 ? 'LONG' : 'SHORT';
        if (cells[1].textContent !== dir) return true;
        if (cells[2].textContent !== String(Math.abs(pos.units))) return true;
        if (cells[3].textContent !== String(pos.entry_price || '-')) return true;
    }
    return false;
}

function updateDashboard(portfolio, equity, backtest) {
    let changed = false;
    
    if (portfolio) {
        const newCapital = portfolio.capital ? `¥${portfolio.capital.toLocaleString()}` : '-';
        if (document.getElementById('capital').textContent !== newCapital) {
            updateElementIfChanged('capital', newCapital);
            changed = true;
        }
        
        const newPnl = portfolio.daily_pnl ? `${portfolio.daily_pnl > 0 ? '+' : ''}${portfolio.daily_pnl.toLocaleString()}` : '-';
        const pnlEl = document.getElementById('daily-pnl');
        if (pnlEl.textContent !== newPnl || !pnlEl.className.includes(portfolio.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400')) {
            pnlEl.textContent = newPnl;
            pnlEl.className = `text-2xl font-bold ${portfolio.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`;
            changed = true;
        }
        
        // Update positions table only if changed
        if (positionsChanged(portfolio.positions)) {
            const tbody = document.getElementById('positions-table');
            tbody.innerHTML = '';
            if (portfolio.positions) {
                portfolio.positions.forEach(pos => {
                    const row = document.createElement('tr');
                    row.className = 'border-b border-gray-700';
                    row.innerHTML = `
                        <td class="py-2">${pos.instrument}</td>
                        <td class="py-2 ${pos.units > 0 ? 'text-green-400' : 'text-red-400'}">${pos.units > 0 ? 'LONG' : 'SHORT'}</td>
                        <td class="py-2">${Math.abs(pos.units)}</td>
                        <td class="py-2">${pos.entry_price || '-'}</td>
                    `;
                    tbody.appendChild(row);
                });
            }
            changed = true;
        }
    }
    
    if (equity && equity.length > 0) {
        renderEquityChart(equity);
        changed = true;
    }
    
    if (backtest) {
        const newWinRate = backtest.win_rate ? `${(backtest.win_rate * 100).toFixed(1)}%` : '-';
        if (document.getElementById('win-rate').textContent !== newWinRate) {
            updateElementIfChanged('win-rate', newWinRate);
            changed = true;
        }
    }
    
    if (changed) {
        const now = new Date();
        const timeStr = now.toTimeString().split(' ')[0];
        document.getElementById('last-updated').textContent = `Last updated: ${timeStr}`;
    }
}

function renderEquityChart(equityData) {
    const ctx = document.getElementById('equity-chart').getContext('2d');
    const labels = equityData.map((_, i) => i);
    const data = equityData.map(d => d.capital || d);
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Capital',
                data: data,
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                fill: true,
                tension: 0.4,
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { display: false },
                y: { 
                    grid: { color: '#334155' },
                    ticks: { color: '#94a3b8' }
                }
            }
        }
    });
}

// Load data on page load and refresh every 5 seconds
loadData();
setInterval(loadData, 5000);
