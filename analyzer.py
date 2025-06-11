import os
import re
import ast
import logging
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
import magic
import chardet
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from radon.complexity import cc_visit
from radon.metrics import h_visit
from radon.raw import analyze

from config import (
    SUPPORTED_CODE_EXTENSIONS,
    MAX_FILE_SIZE,
    CHUNK_SIZE,
    MAX_WORKERS,
    SIMILARITY_THRESHOLD,
    CODE_QUALITY_METRICS,
    logger
)

# Download required NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
except Exception as e:
    logger.warning(f"Failed to download NLTK data: {e}")

@dataclass
class FileMetadata:
    path: Path
    size: int
    created: datetime
    modified: datetime
    mime_type: str
    encoding: str
    category: str
    is_binary: bool
    hash: str

@dataclass
class CodeMetrics:
    loc: int
    sloc: int
    comments: int
    complexity: float
    maintainability: float
    duplicates: List[str]
    issues: List[str]
    functions: List[str]
    dependencies: Set[str]

class ProjectAnalyzer:
    def __init__(self, root_path: Path):
        self.root_path = Path(root_path)
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 3)
        )
        self.file_cache: Dict[str, FileMetadata] = {}
        self.code_cache: Dict[str, CodeMetrics] = {}
        self.similarity_cache: Dict[Tuple[str, str], float] = {}

    def analyze_project(self) -> Dict:
        """Main entry point for project analysis."""
        try:
            logger.info(f"Starting analysis of project: {self.root_path}")
            
            # Collect all files
            files = self._collect_files()
            
            # Analyze files in parallel
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                file_metadata = list(executor.map(self._analyze_file, files))
                
            # Group files by category
            categorized_files = self._categorize_files(file_metadata)
            
            # Analyze code files for duplicates and quality
            code_metrics = self._analyze_code_files(
                [f for f in file_metadata if f.category.startswith('code/')]
            )
            
            # Generate project summary
            summary = self._generate_project_summary(
                categorized_files, code_metrics
            )
            
            return {
                'summary': summary,
                'files': categorized_files,
                'metrics': code_metrics,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Project analysis failed: {e}", exc_info=True)
            raise

    def _collect_files(self) -> List[Path]:
        """Recursively collect all relevant files in the project."""
        files = []
        for root, dirs, filenames in os.walk(self.root_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for filename in filenames:
                if filename.startswith('.'):
                    continue
                    
                filepath = Path(root) / filename
                if filepath.stat().st_size > MAX_FILE_SIZE:
                    logger.warning(f"Skipping large file: {filepath}")
                    continue
                    
                files.append(filepath)
        
        return files

    def _analyze_file(self, filepath: Path) -> FileMetadata:
        """Analyze a single file and return its metadata."""
        try:
            stat = filepath.stat()
            
            # Get file type and encoding
            mime_type = magic.from_file(str(filepath), mime=True)
            
            # Detect encoding for text files
            encoding = 'binary'
            is_binary = True
            if mime_type.startswith('text/'):
                is_binary = False
                with open(filepath, 'rb') as f:
                    raw = f.read(CHUNK_SIZE)
                    result = chardet.detect(raw)
                    encoding = result['encoding'] or 'utf-8'
            
            # Calculate file hash
            file_hash = self._calculate_file_hash(filepath)
            
            # Determine file category
            category = self._categorize_file(filepath)
            
            metadata = FileMetadata(
                path=filepath,
                size=stat.st_size,
                created=datetime.fromtimestamp(stat.st_ctime),
                modified=datetime.fromtimestamp(stat.st_mtime),
                mime_type=mime_type,
                encoding=encoding,
                category=category,
                is_binary=is_binary,
                hash=file_hash
            )
            
            self.file_cache[str(filepath)] = metadata
            return metadata
            
        except Exception as e:
            logger.error(f"Failed to analyze file {filepath}: {e}")
            return None

    def _aggregate_issues(self, file_metrics: List[CodeMetrics]) -> List[str]:
        """Aggregate issues from multiple files."""
        all_issues = []
        for metrics in file_metrics:
            if metrics and metrics.issues:
                all_issues.extend(metrics.issues)
        return all_issues

    def _analyze_code_files(self, code_files: List[FileMetadata]) -> Dict:
        """Analyze code files for quality metrics and duplicates."""
        metrics = {}
        
        # Group files by language
        by_language = {}
        for file in code_files:
            lang = file.category.split('/')[1]
            by_language.setdefault(lang, []).append(file)
        
        # Analyze each language group
        for lang, files in by_language.items():
            try:
                # Get code metrics for each file
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    file_metrics = list(executor.map(
                        self._get_code_metrics, files
                    ))
                
                # Find duplicate code
                duplicates = self._find_duplicates(files)
                
                # Filter out None values from file_metrics
                valid_metrics = [m for m in file_metrics if m]
                
                if valid_metrics:
                    metrics[lang] = {
                        'files': len(files),
                        'total_loc': sum(m.loc for m in valid_metrics),
                        'avg_complexity': sum(m.complexity for m in valid_metrics) / len(valid_metrics),
                        'avg_maintainability': sum(m.maintainability for m in valid_metrics) / len(valid_metrics),
                        'duplicates': duplicates,
                        'issues': self._aggregate_issues(valid_metrics)
                    }
                else:
                    logger.warning(f"No valid metrics found for {lang} files")
                    metrics[lang] = {
                        'files': len(files),
                        'total_loc': 0,
                        'avg_complexity': 0,
                        'avg_maintainability': 0,
                        'duplicates': [],
                        'issues': []
                    }
                
            except Exception as e:
                logger.error(f"Failed to analyze {lang} files: {e}")
                continue
        
        return metrics

    def _get_code_metrics(self, file_metadata: FileMetadata) -> Optional[CodeMetrics]:
        """Calculate code quality metrics for a single file."""
        try:
            if str(file_metadata.path) in self.code_cache:
                return self.code_cache[str(file_metadata.path)]
            
            with open(file_metadata.path, 'r', encoding=file_metadata.encoding) as f:
                content = f.read()
            
            # Initialize metrics with default values
            loc = len(content.splitlines())
            sloc = len([line for line in content.splitlines() if line.strip()])
            comments = 0
            complexity = 0
            maintainability = 100  # Default high maintainability
            functions = []
            dependencies = set()
            issues = []
            
            # Get file extension
            ext = file_metadata.path.suffix.lower()
            
            if ext in {'.py', '.pyw'}:
                # Python-specific analysis
                raw_metrics = analyze(content)
                loc = raw_metrics.loc
                sloc = raw_metrics.sloc
                comments = raw_metrics.comments
                
                try:
                    for item in cc_visit(content):
                        complexity = max(complexity, item.complexity)
                        functions.append(item.name)
                    maintainability = h_visit(content)
                except:
                    pass
                
                dependencies = self._extract_dependencies(content, file_metadata.path)
                
            elif ext in {'.js', '.jsx', '.ts', '.tsx'}:
                # JavaScript/TypeScript analysis
                # Count comments (// and /* */)
                lines = content.splitlines()
                in_multiline = False
                for line in lines:
                    line = line.strip()
                    if line.startswith('//'):
                        comments += 1
                    elif '/*' in line and '*/' in line:
                        comments += 1
                    elif '/*' in line:
                        in_multiline = True
                        comments += 1
                    elif '*/' in line:
                        in_multiline = False
                        comments += 1
                    elif in_multiline:
                        comments += 1
                
                # Extract function names
                fn_matches = re.finditer(r'function\s+(\w+)|(\w+)\s*=\s*function', content)
                functions = [m.group(1) or m.group(2) for m in fn_matches]
                
                # Find imports/requires
                dependencies = self._extract_dependencies(content, file_metadata.path)
                
            elif ext in {'.html', '.htm'}:
                # HTML analysis
                # Count comments <!-- -->
                comments = len(re.findall(r'<!--[\s\S]*?-->', content))
                
                # Extract script and style dependencies
                dependencies.update(re.findall(r'<script[^>]+src=[\'"](.*?)[\'"]', content))
                dependencies.update(re.findall(r'<link[^>]+href=[\'"](.*?)[\'"]', content))
                
            elif ext in {'.css', '.scss', '.sass'}:
                # CSS analysis
                # Count comments /* */
                comments = len(re.findall(r'/\*[\s\S]*?\*/', content))
                
                # Extract imports and urls
                dependencies.update(re.findall(r'@import\s+[\'"]([^\'"]+)[\'"]', content))
                dependencies.update(re.findall(r'url\([\'"]?([^\'"]+)[\'"]?\)', content))
            
            # Calculate basic metrics for all file types
            if sloc > 0:
                comment_ratio = comments / sloc
            else:
                comment_ratio = 0
            
            # Identify potential issues
            if sloc > CODE_QUALITY_METRICS['loc']['max']:
                issues.append(f"File too long: {sloc} lines")
            elif sloc > CODE_QUALITY_METRICS['loc']['warning']:
                issues.append(f"Warning: File approaching maximum length: {sloc} lines")
            
            if comment_ratio < CODE_QUALITY_METRICS['comment_ratio']['min']:
                issues.append(f"Low comment ratio: {comment_ratio:.2%}")
            
            metrics = CodeMetrics(
                loc=loc,
                sloc=sloc,
                comments=comments,
                complexity=complexity,
                maintainability=maintainability,
                duplicates=[],  # Will be filled later
                issues=issues,
                functions=functions,
                dependencies=dependencies
            )
            
            self.code_cache[str(file_metadata.path)] = metrics
            return metrics
            
        except Exception as e:
            logger.error(f"Failed to get metrics for {file_metadata.path}: {e}")
            return None

    def _find_duplicates(self, files: List[FileMetadata]) -> List[Dict]:
        """Find duplicate or similar code sections."""
        duplicates = []
        
        try:
            # Read file contents
            contents = []
            for file in files:
                try:
                    with open(file.path, 'r', encoding=file.encoding) as f:
                        contents.append(f.read())
                except Exception as e:
                    logger.error(f"Failed to read {file.path}: {e}")
                    contents.append("")
            
            # Calculate similarity matrix
            if contents:
                vectors = self.vectorizer.fit_transform(contents)
                similarity_matrix = cosine_similarity(vectors)
                
                # Find similar files
                for i in range(len(files)):
                    for j in range(i + 1, len(files)):
                        similarity = similarity_matrix[i][j]
                        if similarity > SIMILARITY_THRESHOLD:
                            duplicates.append({
                                'file1': str(files[i].path),
                                'file2': str(files[j].path),
                                'similarity': float(similarity)
                            })
            
        except Exception as e:
            logger.error(f"Failed to find duplicates: {e}")
        
        return duplicates

    def _extract_dependencies(self, content: str, filepath: Path) -> Set[str]:
        """Extract dependencies from code file."""
        dependencies = set()
        
        try:
            # Python-specific dependency extraction
            if filepath.suffix == '.py':
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            dependencies.add(name.name)
                    elif isinstance(node, ast.ImportFrom):
                        dependencies.add(node.module or '')
            
            # JavaScript/TypeScript dependency extraction
            elif filepath.suffix in {'.js', '.ts', '.jsx', '.tsx'}:
                import_pattern = r'(?:import|require)\s*\(?[\'"]([^\'"]+)[\'"]'
                dependencies.update(re.findall(import_pattern, content))
            
        except Exception as e:
            logger.error(f"Failed to extract dependencies from {filepath}: {e}")
        
        return dependencies

    def _identify_code_issues(
        self, 
        raw_metrics, 
        complexity: float, 
        maintainability: float
    ) -> List[str]:
        """Identify potential code quality issues."""
        issues = []
        
        # Check cyclomatic complexity
        if complexity > CODE_QUALITY_METRICS['complexity']['max']:
            issues.append(f"High cyclomatic complexity: {complexity}")
        elif complexity > CODE_QUALITY_METRICS['complexity']['warning']:
            issues.append(f"Warning: Moderate cyclomatic complexity: {complexity}")
        
        # Check maintainability index
        if maintainability < CODE_QUALITY_METRICS['maintainability']['min']:
            issues.append(f"Low maintainability index: {maintainability}")
        elif maintainability < CODE_QUALITY_METRICS['maintainability']['warning']:
            issues.append(f"Warning: Moderate maintainability index: {maintainability}")
        
        # Check lines of code
        if raw_metrics.loc > CODE_QUALITY_METRICS['loc']['max']:
            issues.append(f"File too long: {raw_metrics.loc} lines")
        elif raw_metrics.loc > CODE_QUALITY_METRICS['loc']['warning']:
            issues.append(f"Warning: File approaching maximum length: {raw_metrics.loc} lines")
        
        # Check comment ratio
        if raw_metrics.loc > 0:
            comment_ratio = raw_metrics.comments / raw_metrics.loc
            if comment_ratio < CODE_QUALITY_METRICS['comment_ratio']['min']:
                issues.append(f"Low comment ratio: {comment_ratio:.2%}")
        
        return issues

    def _calculate_file_hash(self, filepath: Path) -> str:
        """Calculate SHA-256 hash of file contents."""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _categorize_file(self, filepath: Path) -> str:
        """Determine the category of a file."""
        ext = filepath.suffix.lower()
        name = filepath.name.lower()
        
        # Check code files
        for lang, extensions in SUPPORTED_CODE_EXTENSIONS.items():
            if ext in extensions:
                return f"code/{lang}"
        
        # Check documentation files
        doc_extensions = {'.md', '.rst', '.txt', '.pdf', '.doc', '.docx'}
        if ext in doc_extensions:
            return 'documentation'
        
        # Check configuration files
        config_patterns = {
            'requirements.txt', 'package.json', 'setup.py',
            '.gitignore', 'Dockerfile', 'docker-compose.yml'
        }
        if name in config_patterns or ext in {'.json', '.yaml', '.yml', '.toml', '.ini'}:
            return 'configuration'
        
        # Check test files
        if 'test' in name or 'spec' in name:
            return 'test'
        
        return 'other'

    def _categorize_files(self, files: List[FileMetadata]) -> Dict:
        """Group files by category with detailed information."""
        categories = {}
        
        for file in files:
            if not file:  # Skip failed analyses
                continue
                
            category = file.category
            if category not in categories:
                categories[category] = {
                    'count': 0,
                    'total_size': 0,
                    'files': []
                }
            
            categories[category]['count'] += 1
            categories[category]['total_size'] += file.size
            categories[category]['files'].append({
                'path': str(file.path),
                'size': file.size,
                'modified': file.modified.isoformat(),
                'mime_type': file.mime_type
            })
        
        return categories

    def _generate_project_summary(self, categorized_files: Dict, code_metrics: Dict) -> Dict:
        """Generate a comprehensive project summary."""
        total_files = sum(cat['count'] for cat in categorized_files.values())
        total_size = sum(cat['total_size'] for cat in categorized_files.values())
        
        # Calculate code statistics
        total_loc = 0
        avg_complexity = 0
        avg_maintainability = 0
        total_issues = 0
        languages = set()
        
        for lang, metrics in code_metrics.items():
            total_loc += metrics['total_loc']
            avg_complexity += metrics['avg_complexity']
            avg_maintainability += metrics['avg_maintainability']
            total_issues += len(metrics['issues'])
            languages.add(lang)
        
        if languages:
            avg_complexity /= len(languages)
            avg_maintainability /= len(languages)
        
        return {
            'total_files': total_files,
            'total_size': total_size,
            'languages': list(languages),
            'code_stats': {
                'total_loc': total_loc,
                'avg_complexity': avg_complexity,
                'avg_maintainability': avg_maintainability,
                'total_issues': total_issues
            },
            'categories': {
                category: info['count']
                for category, info in categorized_files.items()
            }
        }

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python analyzer.py <project_path>")
        sys.exit(1)
    
    project_path = Path(sys.argv[1])
    if not project_path.exists():
        print(f"Error: Path {project_path} does not exist")
        sys.exit(1)
    
    analyzer = ProjectAnalyzer(project_path)
    results = analyzer.analyze_project()
    
    # Print summary
    print("\nProject Analysis Summary:")
    print("-" * 50)
    print(f"Total Files: {results['summary']['total_files']}")
    print(f"Languages: {', '.join(results['summary']['languages'])}")
    print(f"Total Lines of Code: {results['summary']['code_stats']['total_loc']}")
    print(f"Average Complexity: {results['summary']['code_stats']['avg_complexity']:.2f}")
    print(f"Total Issues: {results['summary']['code_stats']['total_issues']}")
