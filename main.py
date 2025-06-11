import os
import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from werkzeug.utils import secure_filename

from flask import Flask, request, jsonify, render_template, send_from_directory, url_for
from flask_cors import CORS
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from config import (
    LOG_DIR, WEB_HOST, WEB_PORT, MAX_WORKERS,
    logger
)
from analyzer import ProjectAnalyzer
from models import (
    init_db, get_session, Project, Analysis, File,
    Dependency, Issue, LearningEntry
)

# Initialize Flask application
app = Flask(__name__, static_folder='ui/static', template_folder='ui/templates')
CORS(app)

# Initialize Rich console for beautiful CLI output
console = Console()

class SystemOrganizer:
    def __init__(self):
        self.analyzer = None
        self.session = get_session()
    
    def analyze_directory(self, path: Path, save_to_db: bool = True) -> Dict:
        """Analyze a directory and optionally save results to database."""
        try:
            path = Path(path).resolve()
            if not path.exists():
                raise FileNotFoundError(f"Directory not found: {path}")
            
            # Initialize analyzer for this directory
            self.analyzer = ProjectAnalyzer(path)
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                # Analyze project
                progress.add_task(description="Analyzing project structure...", total=None)
                results = self.analyzer.analyze_project()
                
                if save_to_db:
                    progress.add_task(description="Saving results to database...", total=None)
                    self._save_results_to_db(path, results)
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to analyze directory {path}: {e}", exc_info=True)
            raise

    def _save_results_to_db(self, path: Path, results: Dict):
        """Save analysis results to database."""
        try:
            # Create or update project entry
            project = self.session.query(Project).filter_by(path=str(path)).first()
            if not project:
                project = Project(
                    path=str(path),
                    name=path.name,
                    created_at=datetime.now()
                )
                self.session.add(project)
            
            # Update project metadata
            project.total_files = results['summary']['total_files']
            project.total_size = results['summary']['total_size']
            project.languages = results['summary']['languages']
            project.last_analyzed = datetime.now()
            
            # Create new analysis entry
            analysis = Analysis(
                project=project,
                total_loc=results['summary']['code_stats']['total_loc'],
                avg_complexity=results['summary']['code_stats']['avg_complexity'],
                avg_maintainability=results['summary']['code_stats']['avg_maintainability'],
                total_issues=results['summary']['code_stats']['total_issues'],
                code_metrics=results['metrics'],
                issues=results['summary']['code_stats']
            )
            self.session.add(analysis)
            
            # Process file entries
            self._process_file_entries(project, results['files'])
            
            # Commit changes
            self.session.commit()
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to save results to database: {e}", exc_info=True)
            raise

    def _process_file_entries(self, project: Project, files_data: Dict):
        """Process and save file entries to database."""
        try:
            # Clear existing file entries for this project
            self.session.query(File).filter_by(project_id=project.id).delete()
            
            # Create new file entries
            for category, category_data in files_data.items():
                for file_info in category_data['files']:
                    file_path = Path(file_info['path'])
                    
                    file = File(
                        project=project,
                        path=file_info['path'],
                        name=file_path.name,
                        size=file_info['size'],
                        mime_type=file_info['mime_type'],
                        category=category,
                        modified_at=datetime.fromisoformat(file_info['modified'])
                    )
                    self.session.add(file)
            
        except Exception as e:
            logger.error(f"Failed to process file entries: {e}", exc_info=True)
            raise

    def get_project_history(self, path: Path) -> List[Dict]:
        """Get analysis history for a project."""
        try:
            project = self.session.query(Project).filter_by(path=str(path)).first()
            if not project:
                return []
            
            return [analysis.to_dict() for analysis in project.analyses]
            
        except Exception as e:
            logger.error(f"Failed to get project history: {e}", exc_info=True)
            return []

    def search_similar_projects(self, path: Path) -> List[Dict]:
        """Find projects with similar structure or functionality."""
        try:
            current_project = self.session.query(Project).filter_by(path=str(path)).first()
            if not current_project:
                return []
            
            # Find projects with similar languages and size
            similar_projects = self.session.query(Project).filter(
                Project.id != current_project.id,
                Project.languages.overlap(current_project.languages)
            ).all()
            
            return [
                {
                    **project.to_dict(),
                    'similarity_score': self._calculate_similarity(current_project, project)
                }
                for project in similar_projects
            ]
            
        except Exception as e:
            logger.error(f"Failed to search similar projects: {e}", exc_info=True)
            return []

    def _calculate_similarity(self, project1: Project, project2: Project) -> float:
        """Calculate similarity score between two projects."""
        try:
            # Calculate based on:
            # 1. Language overlap
            # 2. Similar file structure
            # 3. Code metrics
            
            languages1 = set(project1.languages)
            languages2 = set(project2.languages)
            language_similarity = len(languages1 & languages2) / len(languages1 | languages2)
            
            # Get latest analyses
            analysis1 = project1.analyses[-1] if project1.analyses else None
            analysis2 = project2.analyses[-1] if project2.analyses else None
            
            if not (analysis1 and analysis2):
                return language_similarity
            
            # Compare code metrics
            metrics_similarity = 1 - abs(
                analysis1.avg_complexity - analysis2.avg_complexity
            ) / max(analysis1.avg_complexity, analysis2.avg_complexity)
            
            # Weighted average
            return 0.6 * language_similarity + 0.4 * metrics_similarity
            
        except Exception as e:
            logger.error(f"Failed to calculate project similarity: {e}")
            return 0.0

# Flask routes
@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/api/files')
def list_files():
    """API endpoint to list files in a directory."""
    try:
        path = request.args.get('path', '.')
        path = Path(path).resolve()
        
        # Security check to prevent directory traversal
        if not str(path).startswith(str(Path.cwd())):
            return jsonify({'error': 'Access denied'}), 403
        
        files = []
        for item in path.iterdir():
            if not item.name.startswith('.'):  # Skip hidden files
                files.append({
                    'name': item.name,
                    'isDirectory': item.is_dir(),
                    'path': str(item.relative_to(Path.cwd()))
                })
        return jsonify(sorted(files, key=lambda x: (not x['isDirectory'], x['name'])))
        
    except Exception as e:
        logger.error(f"API error in list_files: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """API endpoint to analyze a directory."""
    try:
        data = request.get_json()
        if not data or 'path' not in data:
            return jsonify({'error': 'No path provided'}), 400
        
        path = Path(data['path'])
        organizer = SystemOrganizer()
        results = organizer.analyze_directory(path)
        
        # Format the response to match what the frontend expects
        formatted_results = {
            'summary': {
                'total_files': results.get('total_files', 0),
                'languages': results.get('languages', []),
                'code_stats': {
                    'total_loc': sum(
                        metrics.get('total_loc', 0) 
                        for metrics in results.get('metrics', {}).values()
                    ),
                    'total_issues': sum(
                        len(metrics.get('issues', [])) 
                        for metrics in results.get('metrics', {}).values()
                    ),
                    'avg_complexity': sum(
                        metrics.get('avg_complexity', 0) 
                        for metrics in results.get('metrics', {}).values()
                    ) / len(results.get('metrics', {})) if results.get('metrics') else 0,
                    'avg_maintainability': sum(
                        metrics.get('avg_maintainability', 0) 
                        for metrics in results.get('metrics', {}).values()
                    ) / len(results.get('metrics', {})) if results.get('metrics') else 0
                }
            },
            'metrics': results.get('metrics', {}),
            'timestamp': results.get('timestamp', '')
        }
        
        logger.info(f"Analysis results: {formatted_results}")  # Debug log
        return jsonify(formatted_results)
        
    except Exception as e:
        logger.error(f"API error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/history/<path:project_path>')
def project_history(project_path):
    """API endpoint to get project analysis history."""
    try:
        organizer = SystemOrganizer()
        history = organizer.get_project_history(Path(project_path))
        return jsonify(history)
        
    except Exception as e:
        logger.error(f"API error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/similar/<path:project_path>')
def similar_projects(project_path):
    """API endpoint to find similar projects."""
    try:
        organizer = SystemOrganizer()
        similar = organizer.search_similar_projects(Path(project_path))
        return jsonify(similar)
        
    except Exception as e:
        logger.error(f"API error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def run_cli(args):
    """Run the system in CLI mode."""
    try:
        organizer = SystemOrganizer()
        
        with console.status("[bold green]Analyzing project..."):
            results = organizer.analyze_directory(args.path)
        
        # Display results in a beautiful table
        table = Table(title=f"Analysis Results for {args.path}")
        
        # Add summary information
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        
        summary = results['summary']
        table.add_row("Total Files", str(summary['total_files']))
        table.add_row("Languages", ", ".join(summary['languages']))
        table.add_row("Total Lines of Code", str(summary['code_stats']['total_loc']))
        table.add_row("Average Complexity", f"{summary['code_stats']['avg_complexity']:.2f}")
        table.add_row("Total Issues", str(summary['code_stats']['total_issues']))
        
        console.print(table)
        
        # Display issues if any
        if summary['code_stats']['total_issues'] > 0:
            console.print("\n[bold red]Issues Found:[/bold red]")
            for lang, metrics in results['metrics'].items():
                if metrics['issues']:
                    console.print(f"\n[bold]{lang}:[/bold]")
                    for issue in metrics['issues']:
                        console.print(f"  • {issue}")
        
        # Display similar projects if found
        similar = organizer.search_similar_projects(args.path)
        if similar:
            console.print("\n[bold blue]Similar Projects Found:[/bold blue]")
            for proj in similar:
                console.print(f"  • {proj['name']} (Similarity: {proj['similarity_score']:.2%})")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        sys.exit(1)

def run_web():
    """Run the system in web mode."""
    try:
        # Ensure the database is initialized
        init_db()
        
        # Start the Flask application
        app.run(host=WEB_HOST, port=WEB_PORT, debug=True)
        
    except Exception as e:
        logger.error(f"Failed to start web server: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="Developer Project Analysis and Organization System"
    )
    parser.add_argument(
        '--mode',
        choices=['cli', 'web'],
        default='cli',
        help="Mode to run the system in (cli or web)"
    )
    parser.add_argument(
        '--path',
        type=Path,
        help="Path to the project directory to analyze (required in CLI mode)"
    )
    
    args = parser.parse_args()
    
    # Ensure the logs directory exists
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    if args.mode == 'web':
        run_web()
    else:
        if not args.path:
            parser.error("--path is required in CLI mode")
        run_cli(args)
