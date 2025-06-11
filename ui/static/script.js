// Toast notification system
const Toast = {
    show(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type} animate-fade-in`;
        toast.innerHTML = `
            <div class="flex items-center">
                <span class="status-dot ${type}"></span>
                <span>${message}</span>
            </div>
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
};

// File tree component
class FileTree {
    constructor(container) {
        this.container = container;
        this.selectedPath = null;
    }

    async loadDirectory(path) {
        try {
            const response = await fetch(`/api/files?path=${encodeURIComponent(path)}`);
            if (!response.ok) throw new Error('Failed to load directory');
            
            const files = await response.json();
            this.render(files, path);
        } catch (error) {
            Toast.show(error.message, 'error');
        }
    }

    render(files, basePath) {
        const tree = document.createElement('div');
        tree.className = 'file-tree space-y-1';
        
        files.forEach(file => {
            const item = document.createElement('div');
            item.className = 'file-tree-item';
            item.dataset.path = `${basePath}/${file.name}`;
            
            item.innerHTML = `
                <div class="flex items-center">
                    <i class="fas ${file.isDirectory ? 'fa-folder' : 'fa-file'} mr-2"></i>
                    <span>${file.name}</span>
                </div>
            `;
            
            item.addEventListener('click', () => this.handleItemClick(item));
            tree.appendChild(item);
        });
        
        this.container.innerHTML = '';
        this.container.appendChild(tree);
    }

    handleItemClick(item) {
        const path = item.dataset.path;
        this.selectedPath = path;
        
        // Update selection visual
        this.container.querySelectorAll('.file-tree-item').forEach(el => {
            el.classList.remove('selected');
        });
        item.classList.add('selected');
        
        // Update input field
        document.getElementById('projectPath').value = path;
    }
}

// Analysis manager
class AnalysisManager {
    constructor() {
        this.currentAnalysis = null;
    }

    async analyze(path) {
        try {
            this.showLoading(true);
            
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ path }),
            });
            
            if (!response.ok) throw new Error('Analysis failed');
            
            const results = await response.json();
            console.log('Analysis results:', results);  // Debug log
            
            if (!results.summary) {
                throw new Error('Invalid analysis results format');
            }
            
            this.displayResults(results);
            
        } catch (error) {
            console.error('Analysis error:', error);  // Debug log
            Toast.show(error.message, 'error');
        } finally {
            this.showLoading(false);
        }
    }

    showLoading(show) {
        const loader = document.getElementById('loadingState');
        const results = document.getElementById('analysisResults');
        
        if (show) {
            loader.classList.add('visible');
            results.classList.remove('visible');
        } else {
            loader.classList.remove('visible');
        }
    }

    displayResults(results) {
        console.log('Displaying results:', results);  // Debug log
        this.currentAnalysis = results;
        
        try {
            const analysisResults = document.getElementById('analysisResults');
            analysisResults.classList.add('visible');
            
            // Update summary metrics
            document.getElementById('totalFiles').textContent = results.summary.total_files || 0;
            document.getElementById('totalLoc').textContent = results.summary.code_stats.total_loc || 0;
            document.getElementById('totalLanguages').textContent = (results.summary.languages || []).length;
            document.getElementById('totalIssues').textContent = results.summary.code_stats.total_issues || 0;
            
            // Update code quality metrics
            const metricsContainer = document.getElementById('codeQualityMetrics');
            const metrics = [
                {
                    label: 'Average Complexity',
                    value: results.summary.code_stats.avg_complexity.toFixed(2),
                    percentage: Math.min((results.summary.code_stats.avg_complexity / 10) * 100, 100)
                },
                {
                    label: 'Maintainability',
                    value: results.summary.code_stats.avg_maintainability.toFixed(2),
                    percentage: Math.min(results.summary.code_stats.avg_maintainability, 100)
                }
            ];
            
            metricsContainer.innerHTML = metrics.map(metric => `
                <div class="space-y-2">
                    <div class="flex justify-between items-center">
                        <span class="text-sm text-gray-500">${metric.label}</span>
                        <span class="text-sm font-medium">${metric.value}</span>
                    </div>
                    <div class="progress-bar">
                        <div class="progress-bar-fill" style="width: ${metric.percentage}%"></div>
                    </div>
                </div>
            `).join('');
            
            // Update issues list
            const issuesContainer = document.getElementById('issuesList');
            const issues = Object.entries(results.metrics)
                .flatMap(([lang, data]) => 
                    (data.issues || []).map(issue => ({
                        language: lang,
                        message: issue
                    }))
                );
            
            if (issues.length === 0) {
                issuesContainer.innerHTML = '<p class="text-sm text-gray-500">No issues found</p>';
            } else {
                issuesContainer.innerHTML = issues.map(issue => `
                    <div class="flex items-start space-x-3">
                        <i class="fas fa-exclamation-circle text-red-500 mt-1"></i>
                        <div>
                            <p class="text-sm font-medium text-gray-900">${issue.language}</p>
                            <p class="text-sm text-gray-500">${issue.message}</p>
                        </div>
                    </div>
                `).join('');
            }
            
            Toast.show('Analysis completed successfully', 'success');
            
        } catch (error) {
            console.error('Error displaying results:', error);  // Debug log
            Toast.show('Error displaying analysis results', 'error');
        }
    }
}

// Initialize components when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    const fileTree = new FileTree(document.getElementById('fileTree'));
    const analysisManager = new AnalysisManager();
    
    // Initialize file tree with root directory
    fileTree.loadDirectory('.');
    
    // Handle analyze button click
    document.getElementById('analyzeBtn').addEventListener('click', () => {
        const path = document.getElementById('projectPath').value.trim();
        if (!path) {
            Toast.show('Please select a project directory', 'warning');
            return;
        }
        analysisManager.analyze(path);
    });
    
    // Handle history button click
    document.getElementById('historyBtn').addEventListener('click', async () => {
        const path = document.getElementById('projectPath').value.trim();
        if (!path) {
            Toast.show('Please select a project directory', 'warning');
            return;
        }
        
        try {
            const response = await fetch(`/api/history/${encodeURIComponent(path)}`);
            if (!response.ok) throw new Error('Failed to fetch history');
            
            const history = await response.json();
            showHistoryModal(history);
        } catch (error) {
            Toast.show(error.message, 'error');
        }
    });
    
    // Handle history modal close
    document.getElementById('closeHistoryBtn').addEventListener('click', () => {
        document.getElementById('historyModal').style.display = 'none';
    });
});

// Show history modal
function showHistoryModal(history) {
    const historyList = document.getElementById('historyList');
    const modal = document.getElementById('historyModal');
    
    if (history.length === 0) {
        historyList.innerHTML = '<p class="text-sm text-gray-500">No analysis history available</p>';
    } else {
        historyList.innerHTML = history.map(entry => `
            <div class="border-l-4 border-blue-500 pl-4 py-3">
                <div class="flex justify-between items-start">
                    <div>
                        <p class="text-sm font-medium text-gray-900">
                            Analysis from ${new Date(entry.timestamp).toLocaleString()}
                        </p>
                        <p class="text-sm text-gray-500 mt-1">
                            Files: ${entry.total_files} | 
                            LOC: ${entry.total_loc} | 
                            Issues: ${entry.total_issues}
                        </p>
                    </div>
                    <span class="text-sm text-gray-400">${timeAgo(entry.timestamp)}</span>
                </div>
            </div>
        `).join('');
    }
    
    modal.style.display = 'flex';
}

// Utility function to format time ago
function timeAgo(date) {
    const seconds = Math.floor((new Date() - new Date(date)) / 1000);
    const intervals = {
        year: 31536000,
        month: 2592000,
        week: 604800,
        day: 86400,
        hour: 3600,
        minute: 60
    };
    
    for (const [unit, secondsInUnit] of Object.entries(intervals)) {
        const interval = Math.floor(seconds / secondsInUnit);
        if (interval >= 1) {
            return `${interval} ${unit}${interval === 1 ? '' : 's'} ago`;
        }
    }
    return 'Just now';
}
