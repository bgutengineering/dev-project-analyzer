# Developer Project Analysis System

A powerful system for analyzing, organizing, and optimizing developer projects. This tool helps developers understand their codebases, identify issues, and maintain high-quality code standards.

## Features

### 1. Project Analysis
- **File Structure Analysis**: Scans and categorizes project files
- **Code Quality Metrics**: 
  - Cyclomatic complexity
  - Maintainability index
  - Lines of code (LOC)
  - Comment ratio
- **Issue Detection**:
  - Code complexity warnings
  - Potential bugs
  - Style violations
  - Duplicate code sections

### 2. Project Organization
- **Smart Categorization**: Automatically categorizes files based on type and purpose
- **Dependency Analysis**: Maps project dependencies and their relationships
- **Similar Project Detection**: Finds projects with similar structure or functionality

### 3. Learning Capabilities
- **Pattern Recognition**: Learns from code patterns and common issues
- **Suggestions**: Provides improvement recommendations based on analysis
- **Historical Tracking**: Maintains history of analyses for tracking improvements

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/dev-project-analyzer.git
cd dev-project-analyzer
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Initialize the database:
```bash
python models.py
```

## Usage

### CLI Mode

Analyze a project directory:
```bash
python main.py --mode cli --path /path/to/your/project
```

### Web Interface

Start the web server:
```bash
python main.py --mode web
```

Then open your browser and navigate to `http://localhost:8000`

## System Requirements

- Python 3.8 or higher
- Ubuntu/ARM64 compatible (optimized for Orange Pi 5 Max)
- Sufficient disk space for analysis data
- Internet connection for web interface features

## Configuration

The system can be configured through the following files:
- `config.py`: System-wide configuration
- `requirements.txt`: Python dependencies

Key configuration options:
- Analysis thresholds
- File size limits
- Threading settings
- Database configuration
- Web server settings

## Architecture

### Core Components

1. **Analyzer Module** (`analyzer.py`)
   - File analysis
   - Code quality metrics
   - Pattern detection
   - Duplicate code identification

2. **Database Models** (`models.py`)
   - Project metadata
   - Analysis results
   - Historical data
   - Learning entries

3. **Main Application** (`main.py`)
   - CLI interface
   - Web server
   - Core logic coordination

4. **Web Interface** (`ui/templates/`)
   - Modern, responsive design
   - Real-time analysis results
   - Historical data visualization

### Data Flow

1. User initiates analysis (CLI or Web)
2. System scans project directory
3. Files are analyzed for:
   - Structure
   - Quality metrics
   - Potential issues
4. Results are stored in database
5. Analysis is presented to user
6. System learns from results

## API Endpoints

### Analysis

- `POST /api/analyze`
  - Analyzes a project directory
  - Body: `{"path": "/path/to/project"}`

### History

- `GET /api/history/<project_path>`
  - Retrieves analysis history for a project

### Similar Projects

- `GET /api/similar/<project_path>`
  - Finds projects similar to the specified one

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with Flask and SQLAlchemy
- UI powered by TailwindCSS
- Code analysis powered by various Python libraries

## Future Enhancements

1. **Advanced Analysis**
   - Deep learning-based code analysis
   - More sophisticated duplicate detection
   - Performance optimization suggestions

2. **Integration**
   - IDE plugins
   - CI/CD pipeline integration
   - Cloud storage support

3. **Collaboration**
   - Team collaboration features
   - Project sharing
   - Comment and annotation system

4. **Reporting**
   - Detailed PDF reports
   - Trend analysis
   - Custom metrics tracking

## Troubleshooting

### Common Issues

1. **Database Initialization**
   ```bash
   python models.py
   ```
   Reinitializes the database if you encounter database issues.

2. **Port Conflicts**
   ```bash
   python main.py --mode web --port 8001
   ```
   Use a different port if 8000 is occupied.

3. **Large Projects**
   - Adjust `MAX_FILE_SIZE` in config.py
   - Increase worker count for better performance

### Getting Help

- Check the issues section on GitHub
- Join our community Discord
- Contact support@projectanalyzer.com

## Best Practices

1. **Regular Analysis**
   - Run analysis weekly
   - Track metrics over time
   - Address issues promptly

2. **Configuration**
   - Customize thresholds for your needs
   - Set appropriate file size limits
   - Configure ignore patterns

3. **Data Management**
   - Regular database backups
   - Clean old analysis data
   - Monitor disk usage

## Security

- All file operations are read-only
- No execution of analyzed code
- Secure database connections
- Input validation and sanitization

## Support

For support:
1. Check documentation
2. Search existing issues
3. Create a new issue
4. Contact support

## Roadmap

- [ ] Machine learning enhancements
- [ ] Real-time analysis
- [ ] Multi-language support
- [ ] Cloud deployment options
- [ ] Advanced visualization
- [ ] Team collaboration features
