// API Base URL - use CloudFront /api route (which proxies to API Gateway)
const API_BASE = window.API_BASE_URL || '/api';

// State
let currentJobId = null;
let statusPollInterval = null;
let logsPollInterval = null;

// DOM Elements
const analysisForm = document.getElementById('analysis-form');
const urlInput = document.getElementById('url-input');
const submitBtn = document.getElementById('submit-btn');
const statusSection = document.getElementById('status-section');
const resultsSection = document.getElementById('results-section');
const errorSection = document.getElementById('error-section');
const progressFill = document.getElementById('progress-fill');
const statusMessage = document.getElementById('status-message');
const statusDetails = document.getElementById('status-details');
const refreshHistoryBtn = document.getElementById('refresh-history-btn');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    refreshHistoryBtn.addEventListener('click', loadHistory);
    analysisForm.addEventListener('submit', handleFormSubmit);
});

// Handle form submission
async function handleFormSubmit(e) {
    e.preventDefault();
    
    const url = urlInput.value.trim();
    if (!url) {
        showError('Please enter a valid URL');
        return;
    }
    
    try {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Submitting...';
        hideError();
        hideResults();
        
        // Show loading animation immediately
        showStatus();
        updateStatusDisplay({
            progress: 0,
            message: 'Submitting analysis request...',
            status: 'processing'
        });
        
        const response = await fetch(`${API_BASE}/analyze`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url })
        });
        
        if (!response.ok) {
            throw new Error('Failed to submit analysis');
        }
        
        const data = await response.json();
        currentJobId = data.job_id;
        
        // Start polling with loading animation
            startStatusPolling(data.job_id);
            startLogsPolling(data.job_id);
            
            // Reset form
            urlInput.value = '';
            submitBtn.disabled = false;
            submitBtn.textContent = 'Analyze Website';
            
            // Refresh history
            loadHistory();
        
    } catch (error) {
        hideStatus();
        showError(`Error: ${error.message}`);
        submitBtn.disabled = false;
        submitBtn.textContent = 'Analyze Website';
    }
}

    // Poll for status updates
    function startStatusPolling(jobId) {
        if (statusPollInterval) {
            clearInterval(statusPollInterval);
        }
        
        statusPollInterval = setInterval(async () => {
            try {
                const response = await fetch(`${API_BASE}/status/${jobId}`);
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: Failed to get status`);
                }
                
                // Check if response is JSON (not HTML error page)
                const contentType = response.headers.get('content-type');
                if (!contentType || !contentType.includes('application/json')) {
                    const text = await response.text();
                    console.error('Non-JSON response received:', text.substring(0, 200));
                    throw new Error('Server returned non-JSON response');
                }
                
                const status = await response.json();
                updateStatusDisplay(status);
                
                if (status.status === 'completed' || status.status === 'failed') {
                    clearInterval(statusPollInterval);
                    statusPollInterval = null;
                    
                    // Stop logs polling
                    if (logsPollInterval) {
                        clearInterval(logsPollInterval);
                        logsPollInterval = null;
                    }
                    
                    if (status.status === 'completed') {
                        await loadResults(jobId);
                    } else {
                        showError('Analysis failed. Please try again.');
                    }
                }
            } catch (error) {
                console.error('Error polling status:', error);
                // Don't stop polling on first error - might be temporary
                // Only stop after multiple consecutive errors
                if (!statusPollInterval) {
                    return; // Already stopped
                }
                // Continue polling - might be temporary network issue
            }
        }, 2000); // Poll every 2 seconds
    }

// Update status display
function updateStatusDisplay(status) {
    const progress = status.progress || 0;
    
    // If progress is 0 or very low, show animated loading
    if (progress < 5) {
        progressFill.style.width = '100%';
        progressFill.classList.add('loading-animation');
    } else {
        progressFill.style.width = `${progress}%`;
        progressFill.classList.remove('loading-animation');
    }
    
    statusMessage.textContent = status.message || `Status: ${status.status}`;
    statusDetails.textContent = progress > 0 ? `Progress: ${progress}%` : 'Processing...';
}

// Load and display results
async function loadResults(jobId) {
    try {
        const response = await fetch(`${API_BASE}/results/${jobId}`);
        if (!response.ok) {
            throw new Error('Failed to get results');
        }
        
        const data = await response.json();
        
        if (data.error) {
            showError(data.error);
            return;
        }
        
        if (data.result) {
            displayResults(data.result);
            hideStatus();
            showResults();
        }
        
    } catch (error) {
        showError(`Error loading results: ${error.message}`);
    }
}

// Display results
function displayResults(result) {
    // Business Summary
    const summaryDiv = document.getElementById('business-summary');
    summaryDiv.innerHTML = `
        <p><strong>Nature:</strong> ${result.summary.nature}</p>
        <p><strong>Products/Services:</strong> ${result.summary.products_services}</p>
        <p><strong>Countries Operating:</strong> ${result.summary.countries_operating.join(', ') || 'N/A'}</p>
        <p><strong>Countries Dealing With:</strong> ${result.summary.countries_dealing_with.join(', ') || 'N/A'}</p>
    `;
    
    // Flags with risk levels and evidence
    const flagsDiv = document.getElementById('flags-display');
    flagsDiv.innerHTML = `
        ${renderFlagItem('Sanctions Check', result.flags.sanctions)}
        ${renderFlagItem('Military/Weapons Check', result.flags.military)}
        ${renderFlagItem('Dual-Use Goods Check', result.flags.dual_use)}
    `;
    
    // NAICS
    const naicsDiv = document.getElementById('naics-display');
    naicsDiv.innerHTML = `
        <p><strong>Primary Code:</strong> <span class="naics-code naics-primary">${result.naics_codes.primary_code}</span></p>
        <p><strong>All Codes:</strong></p>
        <div class="naics-codes">
            ${result.naics_codes.codes.map(code => 
                `<span class="naics-code">${code}</span>`
            ).join('')}
        </div>
        <p style="margin-top: 15px;"><strong>Explanation:</strong> ${result.naics_codes.explanation}</p>
    `;
    
    // Address
    const addressDiv = document.getElementById('address-display');
    if (result.address.address) {
        const validation = result.address.validation;
        const isCommercial = validation.is_commercial;
        const plausibilityNote = validation.plausibility_note || '';
        const addressTypes = validation.address_types || [];
        
        // Build address types display
        let typesDisplay = '';
        if (addressTypes && addressTypes.length > 0) {
            typesDisplay = `
                <div style="margin-top: 10px;">
                    <strong>Location Types:</strong>
                    <div style="display: flex; flex-wrap: wrap; gap: 5px; margin-top: 5px;">
                        ${addressTypes.map(type => 
                            `<span style="background: #e3f2fd; padding: 4px 8px; border-radius: 4px; font-size: 0.85em;">${type}</span>`
                        ).join('')}
                    </div>
                </div>
            `;
        }
        
        // Commercial classification badge
        let commercialBadge = '';
        if (isCommercial !== null && isCommercial !== undefined) {
            const badgeClass = isCommercial ? 'commercial-badge' : 'residential-badge';
            const badgeText = isCommercial ? '🏢 COMMERCIAL/INDUSTRIAL' : '🏠 RESIDENTIAL';
            commercialBadge = `
                <div style="margin: 10px 0; padding: 10px; background: ${isCommercial ? '#e8f5e9' : '#fff3e0'}; border-left: 4px solid ${isCommercial ? '#4caf50' : '#ff9800'}; border-radius: 4px;">
                    <strong style="color: ${isCommercial ? '#2e7d32' : '#e65100'};">
                        ${badgeText}
                    </strong>
                </div>
            `;
        }
        
        addressDiv.innerHTML = `
            <p><strong>Address:</strong> ${result.address.address}</p>
            <p><strong>Validation Status:</strong> 
                <span style="color: ${validation.valid ? '#4caf50' : '#f44336'}; font-weight: bold;">
                    ${validation.valid ? '✓ Verified' : '✗ Not Verified'}
                </span>
            </p>
            ${commercialBadge}
            ${plausibilityNote ? `<p style="margin-top: 10px; padding: 8px; background: #f5f5f5; border-radius: 4px;"><strong>Analysis:</strong> ${plausibilityNote}</p>` : ''}
            ${typesDisplay}
            ${validation.image_path ? `
                <img src="/${validation.image_path}" alt="Address" class="address-image" style="margin-top: 10px;">
            ` : ''}
            <div style="margin-top: 15px; padding: 10px; background: #e3f2fd; border-left: 4px solid #2196f3; border-radius: 4px; font-size: 0.9em;">
                <strong>🤖 AI Analysis:</strong> This classification uses AI-powered address analysis. For production use with real-time geospatial data and enhanced accuracy, enable Google Places API with a paid plan.
            </div>
        `;
    } else {
        addressDiv.innerHTML = '<p>No address found on website.</p>';
    }
    
    // Company Registration
    const companyRegDiv = document.getElementById('company-registration-display');
    if (companyRegDiv) {
        if (result.company_registration && Object.values(result.company_registration).some(v => v)) {
            const reg = result.company_registration;
            companyRegDiv.innerHTML = `
                ${reg.company_number ? `<p><strong>Company Number:</strong> ${reg.company_number}</p>` : ''}
                ${reg.vat_number ? `<p><strong>VAT Number:</strong> ${reg.vat_number}</p>` : ''}
                ${reg.eori_number ? `<p><strong>EORI Number:</strong> ${reg.eori_number}</p>` : ''}
                ${reg.company_name ? `<p><strong>Company Name:</strong> ${reg.company_name}</p>` : ''}
                ${reg.established_date ? `<p><strong>Established:</strong> ${reg.established_date}</p>` : ''}
                ${reg.country_of_registration ? `<p><strong>Country of Registration:</strong> ${reg.country_of_registration}</p>` : ''}
            `;
        } else {
            companyRegDiv.innerHTML = '<p>No company registration details found.</p>';
        }
    }
    
    // Screenshots section removed
}

// Load history
async function loadHistory() {
    try {
        const response = await fetch(`${API_BASE}/history?limit=20`);
        if (!response.ok) {
            throw new Error('Failed to load history');
        }
        
        const data = await response.json();
        displayHistory(data.items);
        
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

// Render flag item with risk levels and evidence
function renderFlagItem(title, flag) {
    const isFlagged = flag.flags_raised;
    const riskLevel = flag.risk_level || 'NONE';
    const riskScore = flag.risk_score || 0;
    const riskExplanation = flag.risk_explanation || '';
    
    // Risk level styling
    const riskClass = riskLevel === 'HIGH' ? 'risk-high' : 
                     riskLevel === 'MEDIUM' ? 'risk-medium' : 
                     riskLevel === 'LOW' ? 'risk-low' : 'risk-none';
    const riskIcon = riskLevel === 'HIGH' ? '🔴' : 
                    riskLevel === 'MEDIUM' ? '🟡' : 
                    riskLevel === 'LOW' ? '🟢' : '✓';
    
    return `
        <div class="flag-item ${isFlagged ? 'flag-raised' : 'flag-clear'}">
            <h4>${title} ${isFlagged ? '⚠️ FLAGGED' : '✓ CLEAR'}</h4>
            ${riskLevel !== 'NONE' ? `
                <div class="risk-indicator ${riskClass}">
                    <span class="risk-icon">${riskIcon}</span>
                    <span class="risk-level">Risk: ${riskLevel}</span>
                    <span class="risk-score">Score: ${riskScore}/100</span>
                </div>
                ${riskExplanation ? `<p class="risk-explanation"><em>${riskExplanation}</em></p>` : ''}
            ` : ''}
            ${flag.matches && flag.matches.length > 0 ? `
                <p><strong>Matches:</strong> ${flag.matches.join(', ')}</p>
            ` : ''}
            ${flag.evidence && flag.evidence.length > 0 ? `
                <details class="evidence-details">
                    <summary><strong>Evidence (${flag.evidence.length} snippet${flag.evidence.length > 1 ? 's' : ''})</strong></summary>
                    <div class="evidence-list">
                        ${flag.evidence.map((snippet, idx) => `
                            <div class="evidence-item">
                                <span class="evidence-number">${idx + 1}.</span>
                                <span class="evidence-text">"...${snippet}..."</span>
                            </div>
                        `).join('')}
                    </div>
                </details>
            ` : ''}
        </div>
    `;
}

// Display history
function displayHistory(items) {
    const tbody = document.getElementById('history-tbody');
    
    if (items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center;">No analysis history</td></tr>';
        return;
    }
    
    tbody.innerHTML = items.map(item => {
        const createdDate = new Date(item.created_at).toLocaleString();
        return `
            <tr>
                <td>${item.url}</td>
                <td><span class="status-badge status-${item.status}">${item.status}</span></td>
                <td>${createdDate}</td>
                <td>
                    ${item.status === 'completed' ? `
                        <button class="btn-small" onclick="viewResults('${item.job_id}')">View Results</button>
                    ` : ''}
                </td>
            </tr>
        `;
    }).join('');
}

// View results from history
async function viewResults(jobId) {
    currentJobId = jobId;
    await loadResults(jobId);
    // Scroll to results
    document.getElementById('results-section').scrollIntoView({ behavior: 'smooth' });
}

// Show/hide sections
function showStatus() {
    statusSection.style.display = 'block';
    // Smooth scroll to status section
    setTimeout(() => {
        statusSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
}

function hideStatus() {
    statusSection.style.display = 'none';
}

function showResults() {
    resultsSection.style.display = 'block';
}

function hideResults() {
    resultsSection.style.display = 'none';
}

function showError(message) {
    errorSection.style.display = 'block';
    document.getElementById('error-message').textContent = message;
}

function hideError() {
    errorSection.style.display = 'none';
}

// Poll for logs
function startLogsPolling(jobId) {
    if (logsPollInterval) {
        clearInterval(logsPollInterval);
    }
    
    // Show logs section
    const logsSection = document.getElementById('logs-section');
    if (logsSection) {
        logsSection.style.display = 'block';
    }
    
    logsPollInterval = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/logs/${jobId}`);
            if (!response.ok) {
                return; // Don't spam errors if endpoint doesn't exist yet
            }
            
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                return;
            }
            
            const data = await response.json();
            displayLogs(data.logs || []);
            
            // Stop polling if job is done
            const statusResponse = await fetch(`${API_BASE}/status/${jobId}`);
            if (statusResponse.ok) {
                const status = await statusResponse.json();
                if (status.status === 'completed' || status.status === 'failed') {
                    clearInterval(logsPollInterval);
                    logsPollInterval = null;
                }
            }
        } catch (error) {
            // Silently fail - logs are optional
            console.debug('Error polling logs:', error);
        }
    }, 2000); // Poll every 2 seconds
}

// Display logs
function displayLogs(logs) {
    const container = document.getElementById('logs-container');
    if (!container) return;
    
    // Clear and add all logs
    container.innerHTML = logs.map(log => {
        let className = 'log-line';
        if (log.includes('[WORKER]')) className += ' worker';
        else if (log.includes('[SCRAPER]')) className += ' scraper';
        else if (log.includes('[EXTRACTOR]')) className += ' extractor';
        else if (log.includes('✗') || log.includes('ERROR') || log.includes('Error')) className += ' error';
        else if (log.includes('✓') || log.includes('completed')) className += ' success';
        
        return `<div class="${className}">${escapeHtml(log)}</div>`;
    }).join('');
    
    // Auto-scroll to bottom
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Make viewResults available globally
window.viewResults = viewResults;

