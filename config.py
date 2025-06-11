import os
import platform
import logging
from pathlib import Path
from typing import Dict, List, Set

# System Configuration
BASE_DIR = Path(__file__).resolve().parent
LOG_DIR = BASE_DIR / "logs"
CACHE_DIR = BASE_DIR / "cache"
DB_PATH = BASE_DIR / "data" / "analysis.db"

# Create necessary directories
for directory in [LOG_DIR, CACHE_DIR, BASE_DIR / "data"]:
    directory.mkdir(parents=True, exist_ok=True)

# Logging Configuration
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = LOG_DIR / 'system.log'
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# System Detection
SYSTEM_INFO = {
    'os': platform.system(),
    'architecture': platform.machine(),
    'processor': platform.processor(),
    'python_version': platform.python_version(),
}

# File Analysis Configuration
SUPPORTED_CODE_EXTENSIONS = {
    'python': {'.py', '.pyw', '.pyx', '.pxd', '.pxi'},
    'javascript': {'.js', '.jsx', '.ts', '.tsx'},
    'web': {'.html', '.htm', '.css', '.scss', '.sass'},
    'java': {'.java', '.class', '.jar'},
    'c_cpp': {'.c', '.cpp', '.h', '.hpp'},
    'ruby': {'.rb', '.rake', '.gemspec'},
    'php': {'.php', '.phtml'},
    'go': {'.go'},
    'rust': {'.rs'},
}

SUPPORTED_DOC_EXTENSIONS = {
    'text': {'.txt', '.md', '.rst', '.adoc'},
    'office': {'.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'},
    'pdf': {'.pdf'},
}

SUPPORTED_CONFIG_EXTENSIONS = {
    'data': {'.json', '.yaml', '.yml', '.toml', '.ini', '.conf'},
    'lock': {'.lock'},
    'git': {'.gitignore', '.gitmodules', '.gitattributes'},
    'docker': {'Dockerfile', '.dockerignore', 'docker-compose.yml'},
    'package': {'package.json', 'requirements.txt', 'Pipfile', 'setup.py'},
}

# Project Markers (files/folders that indicate a project root)
PROJECT_MARKERS = {
    'python': {'setup.py', 'pyproject.toml', 'requirements.txt', 'Pipfile'},
    'node': {'package.json', 'package-lock.json', 'yarn.lock'},
    'ruby': {'Gemfile', 'Rakefile'},
    'php': {'composer.json'},
    'java': {'pom.xml', 'build.gradle'},
    'go': {'go.mod'},
    'rust': {'Cargo.toml'},
    'generic': {'.git', '.svn', '.hg'}
}

# Analysis Settings
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
CHUNK_SIZE = 1024 * 1024  # 1MB for reading large files
MAX_WORKERS = os.cpu_count() or 4
SIMILARITY_THRESHOLD = 0.8  # For code duplication detection

# ML Model Settings
MODEL_DIR = BASE_DIR / "models"
VECTORIZER_PATH = MODEL_DIR / "vectorizer.pkl"
CLASSIFIER_PATH = MODEL_DIR / "classifier.pkl"
WORD2VEC_PATH = MODEL_DIR / "word2vec.model"

# Database Configuration
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Cache Configuration
CACHE_TTL = 3600  # 1 hour
MAX_CACHE_SIZE = 1024 * 1024 * 1024  # 1GB

# Security Settings
IGNORED_DIRECTORIES = {
    '.git', '.svn', '.hg', '__pycache__', 
    'node_modules', 'venv', '.env', '.venv',
    'build', 'dist', '.idea', '.vscode'
}

IGNORED_FILES = {
    '.DS_Store', 'Thumbs.db', '.env', '*.pyc',
    '*.pyo', '*.pyd', '*.so', '*.dylib', '*.dll'
}

# Analysis Metrics
CODE_QUALITY_METRICS = {
    'complexity': {'max': 10, 'warning': 7},
    'maintainability': {'min': 20, 'warning': 25},
    'loc': {'max': 500, 'warning': 300},
    'comment_ratio': {'min': 0.1, 'warning': 0.15}
}

# Web Interface Configuration
WEB_HOST = "0.0.0.0"
WEB_PORT = 8000
SECRET_KEY = os.urandom(24)
SESSION_TYPE = 'filesystem'

def get_project_type(directory: Path) -> str:
    """Determine project type based on markers."""
    files = set(os.listdir(directory))
    for lang, markers in PROJECT_MARKERS.items():
        if markers & files:
            return lang
    return 'unknown'

def is_binary_file(filepath: Path) -> bool:
    """Check if a file is binary."""
    try:
        with open(filepath, 'tr') as check_file:
            check_file.read(1024)
            return False
    except UnicodeDecodeError:
        return True

def get_file_category(filepath: Path) -> str:
    """Categorize a file based on its extension."""
    ext = filepath.suffix.lower()
    name = filepath.name.lower()
    
    for lang, extensions in SUPPORTED_CODE_EXTENSIONS.items():
        if ext in extensions:
            return f"code/{lang}"
            
    for doc_type, extensions in SUPPORTED_DOC_EXTENSIONS.items():
        if ext in extensions:
            return f"doc/{doc_type}"
            
    for config_type, patterns in SUPPORTED_CONFIG_EXTENSIONS.items():
        if ext in patterns or name in patterns:
            return f"config/{config_type}"
            
    return "unknown"

# Initialize logging
logger = logging.getLogger(__name__)
logger.info(f"System initialized with: {SYSTEM_INFO}")
