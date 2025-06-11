from datetime import datetime
from typing import Dict, List
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, 
    DateTime, ForeignKey, JSON, Text, Boolean
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

from config import SQLALCHEMY_DATABASE_URI

# Initialize SQLAlchemy
engine = create_engine(SQLALCHEMY_DATABASE_URI)
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Project(Base):
    """Represents a project that has been analyzed."""
    __tablename__ = 'projects'

    id = Column(Integer, primary_key=True)
    path = Column(String(512), unique=True, nullable=False)
    name = Column(String(256), nullable=False)
    created_at = Column(DateTime, default=func.now())
    last_analyzed = Column(DateTime, onupdate=func.now())
    
    # Project metadata
    total_files = Column(Integer, default=0)
    total_size = Column(Integer, default=0)  # in bytes
    languages = Column(JSON)  # List of programming languages used
    
    # Relationships
    analyses = relationship("Analysis", back_populates="project", cascade="all, delete-orphan")
    files = relationship("File", back_populates="project", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'path': self.path,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'last_analyzed': self.last_analyzed.isoformat() if self.last_analyzed else None,
            'total_files': self.total_files,
            'total_size': self.total_size,
            'languages': self.languages
        }

class Analysis(Base):
    """Represents a single analysis run of a project."""
    __tablename__ = 'analyses'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    timestamp = Column(DateTime, default=func.now())
    
    # Analysis results
    total_loc = Column(Integer)
    avg_complexity = Column(Float)
    avg_maintainability = Column(Float)
    total_issues = Column(Integer)
    
    # Detailed metrics stored as JSON
    code_metrics = Column(JSON)  # Detailed code quality metrics
    duplicates = Column(JSON)    # List of duplicate code sections
    issues = Column(JSON)        # List of identified issues
    
    # Relationships
    project = relationship("Project", back_populates="analyses")
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'timestamp': self.timestamp.isoformat(),
            'total_loc': self.total_loc,
            'avg_complexity': self.avg_complexity,
            'avg_maintainability': self.avg_maintainability,
            'total_issues': self.total_issues,
            'code_metrics': self.code_metrics,
            'duplicates': self.duplicates,
            'issues': self.issues
        }

class File(Base):
    """Represents a file within a project."""
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    path = Column(String(512), nullable=False)
    name = Column(String(256), nullable=False)
    size = Column(Integer)  # in bytes
    
    # File metadata
    mime_type = Column(String(128))
    encoding = Column(String(32))
    category = Column(String(64))  # e.g., 'code/python', 'documentation', etc.
    is_binary = Column(Boolean, default=False)
    hash = Column(String(64))  # SHA-256 hash of contents
    
    # File statistics
    loc = Column(Integer)          # Lines of code
    sloc = Column(Integer)         # Source lines of code
    comments = Column(Integer)     # Number of comments
    complexity = Column(Float)     # Cyclomatic complexity
    maintainability = Column(Float)# Maintainability index
    
    # Timestamps
    created_at = Column(DateTime)
    modified_at = Column(DateTime)
    analyzed_at = Column(DateTime, default=func.now())
    
    # Relationships
    project = relationship("Project", back_populates="files")
    dependencies = relationship("Dependency", back_populates="file", cascade="all, delete-orphan")
    issues = relationship("Issue", back_populates="file", cascade="all, delete-orphan")
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'project_id': self.project_id,
            'path': self.path,
            'name': self.name,
            'size': self.size,
            'mime_type': self.mime_type,
            'encoding': self.encoding,
            'category': self.category,
            'is_binary': self.is_binary,
            'hash': self.hash,
            'loc': self.loc,
            'sloc': self.sloc,
            'comments': self.comments,
            'complexity': self.complexity,
            'maintainability': self.maintainability,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'modified_at': self.modified_at.isoformat() if self.modified_at else None,
            'analyzed_at': self.analyzed_at.isoformat() if self.analyzed_at else None
        }

class Dependency(Base):
    """Represents a dependency relationship between files."""
    __tablename__ = 'dependencies'

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    name = Column(String(256), nullable=False)  # Name/path of the dependency
    type = Column(String(32))  # e.g., 'import', 'require', etc.
    is_internal = Column(Boolean, default=False)  # Whether it's internal to the project
    
    # Relationships
    file = relationship("File", back_populates="dependencies")
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'file_id': self.file_id,
            'name': self.name,
            'type': self.type,
            'is_internal': self.is_internal
        }

class Issue(Base):
    """Represents a code quality issue or warning."""
    __tablename__ = 'issues'

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey('files.id'), nullable=False)
    type = Column(String(64))  # e.g., 'complexity', 'maintainability', etc.
    severity = Column(String(16))  # 'low', 'medium', 'high'
    message = Column(Text)
    line_number = Column(Integer)
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    file = relationship("File", back_populates="issues")
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'file_id': self.file_id,
            'type': self.type,
            'severity': self.severity,
            'message': self.message,
            'line_number': self.line_number,
            'created_at': self.created_at.isoformat()
        }

class LearningEntry(Base):
    """Stores learning data from analysis results."""
    __tablename__ = 'learning_entries'

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=func.now())
    
    # Context
    file_pattern = Column(String(256))  # Pattern of files this entry applies to
    language = Column(String(64))
    category = Column(String(64))
    
    # Learning data
    observation = Column(Text)  # What was observed
    conclusion = Column(Text)   # What was learned
    confidence = Column(Float)  # Confidence in the conclusion (0-1)
    
    # Metadata for future reference
    frequency = Column(Integer, default=1)  # How often this pattern is seen
    last_seen = Column(DateTime, default=func.now())
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'file_pattern': self.file_pattern,
            'language': self.language,
            'category': self.category,
            'observation': self.observation,
            'conclusion': self.conclusion,
            'confidence': self.confidence,
            'frequency': self.frequency,
            'last_seen': self.last_seen.isoformat()
        }

def init_db():
    """Initialize the database by creating all tables."""
    Base.metadata.create_all(engine)

def get_session():
    """Get a new database session."""
    return Session()

if __name__ == "__main__":
    # Initialize the database
    init_db()
    print("Database initialized successfully.")
