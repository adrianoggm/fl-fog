# Contributing to FL-Fog

Thank you for your interest in contributing to FL-Fog! This document provides guidelines and information for contributors.

## 🤝 Code of Conduct

By participating in this project, you agree to abide by our Code of Conduct. Please be respectful and constructive in all interactions.

## 🚀 Getting Started

### Prerequisites

- Python 3.8+ 
- Git
- Docker (optional, for containerized development)

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/TFM-Federated-learning-on-edge-nodes.git
   cd TFM-Federated-learning-on-edge-nodes/fl-fog
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .[dev]
   ```

4. **Install Pre-commit Hooks**
   ```bash
   pre-commit install
   ```

5. **Run Tests**
   ```bash
   pytest tests/
   ```

## 🛠️ Development Workflow

### Branch Naming Convention

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `hotfix/description` - Critical fixes
- `docs/description` - Documentation updates
- `refactor/description` - Code refactoring

### Code Style

We use automated tools to maintain code quality:

- **Black** - Code formatting
- **isort** - Import sorting
- **flake8** - Linting
- **mypy** - Type checking

Run all checks locally:
```bash
# Auto-format code
black .
isort .

# Check code quality
flake8 fog_node communication tests
mypy fog_node communication

# Or run the full CI pipeline locally
./test_ci_local.sh  # Linux/Mac
.\test_ci_local.ps1  # Windows
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `style` - Code style changes
- `refactor` - Code refactoring
- `test` - Adding tests
- `chore` - Maintenance tasks

**Examples:**
```
feat(aggregator): add FedProx aggregation strategy
fix(cache): resolve memory leak in model storage
docs(api): update fog node API documentation
test(integration): add MQTT communication tests
```

## 📝 Pull Request Process

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write code following our style guidelines
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Locally**
   ```bash
   pytest tests/
   ./test_ci_local.sh
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat(component): description of changes"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a Pull Request on GitHub.

### PR Checklist

- [ ] Code follows style guidelines
- [ ] Tests pass locally
- [ ] New functionality has tests
- [ ] Documentation updated
- [ ] No merge conflicts
- [ ] PR description explains changes
- [ ] Related issues linked

## 🧪 Testing

### Test Structure

```
tests/
├── unit/           # Unit tests
├── integration/    # Integration tests
├── performance/    # Performance tests
└── conftest.py     # Test configuration
```

### Writing Tests

- Use `pytest` for testing framework
- Follow AAA pattern (Arrange, Act, Assert)
- Use descriptive test names
- Mock external dependencies
- Test both success and failure cases

**Example:**
```python
import pytest
from fog_node.aggregator import RegionalAggregator

class TestRegionalAggregator:
    def test_fedavg_aggregation_success(self):
        # Arrange
        aggregator = RegionalAggregator("fedavg")
        models = [mock_model_1, mock_model_2]
        
        # Act
        result = aggregator.aggregate(models)
        
        # Assert
        assert result is not None
        assert result.weights == expected_weights
```

### Running Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# With coverage
pytest --cov=fog_node --cov=communication

# Specific test file
pytest tests/unit/test_aggregator.py

# Specific test
pytest tests/unit/test_aggregator.py::TestRegionalAggregator::test_fedavg
```

## 📚 Documentation

### Code Documentation

- Use docstrings for all public functions/classes
- Follow Google docstring format
- Include type hints
- Document complex algorithms

**Example:**
```python
async def aggregate_models(
    self, 
    models: List[ModelUpdate], 
    strategy: str = "fedavg"
) -> AggregatedModel:
    """
    Aggregate multiple model updates using specified strategy.
    
    Args:
        models: List of model updates from edge devices
        strategy: Aggregation strategy ("fedavg", "fedprox", etc.)
        
    Returns:
        Aggregated model ready for distribution
        
    Raises:
        ValueError: If strategy is not supported
        AggregationError: If aggregation fails
        
    Example:
        >>> aggregator = RegionalAggregator()
        >>> result = await aggregator.aggregate_models(models, "fedavg")
        >>> print(result.accuracy)
        0.95
    """
```

### API Documentation

- Use Sphinx for API documentation
- Include examples in docstrings
- Document configuration options
- Provide usage scenarios

### Building Documentation

```bash
cd docs
make html
# Open docs/_build/html/index.html
```

## 🏗️ Architecture Guidelines

### Code Organization

```
fog_node/
├── __init__.py         # Main fog node class
├── aggregator.py       # FL aggregation logic
├── edge_coordinator.py # Edge device management
├── model_cache.py      # Model caching system
└── resource_monitor.py # Resource monitoring

communication/
├── __init__.py
├── edge_interface.py   # Edge device communication
├── cloud_interface.py  # Cloud server communication
└── peer_interface.py   # Peer fog communication
```

### Design Principles

1. **Modularity** - Keep components loosely coupled
2. **Async/Await** - Use async patterns for I/O operations
3. **Type Safety** - Use type hints throughout
4. **Configuration** - Make behavior configurable
5. **Error Handling** - Implement proper error handling
6. **Logging** - Add comprehensive logging
7. **Testing** - Write testable code

### Performance Considerations

- Use async/await for concurrent operations
- Implement connection pooling
- Cache frequently accessed data
- Monitor resource usage
- Profile critical paths

## 🔧 Adding New Features

### Feature Development Process

1. **Design Discussion**
   - Open an issue to discuss the feature
   - Gather feedback from maintainers
   - Define requirements and scope

2. **Implementation**
   - Create feature branch
   - Implement core functionality
   - Add comprehensive tests
   - Update documentation

3. **Integration**
   - Ensure compatibility with existing code
   - Add configuration options
   - Update examples and tutorials

4. **Review**
   - Submit pull request
   - Address review feedback
   - Ensure CI passes

### Common Feature Areas

- **Aggregation Algorithms** - New FL aggregation strategies
- **Communication Protocols** - Additional communication methods
- **Security Features** - Enhanced privacy/security mechanisms
- **Monitoring Tools** - Improved observability features
- **Optimization Algorithms** - Resource optimization strategies

## 🐛 Bug Reports

### Reporting Bugs

Use the GitHub issue template and include:

- **Environment** - OS, Python version, dependencies
- **Reproduction** - Steps to reproduce the bug
- **Expected Behavior** - What should happen
- **Actual Behavior** - What actually happens
- **Logs** - Relevant error messages or logs
- **Screenshots** - If applicable

### Bug Fix Process

1. Create issue or claim existing bug
2. Create bugfix branch
3. Implement fix with test
4. Verify fix works
5. Submit pull request

## 🚀 Release Process

### Version Numbering

We follow [Semantic Versioning](https://semver.org/):
- MAJOR.MINOR.PATCH (e.g., 1.2.3)
- MAJOR - Breaking changes
- MINOR - New features (backward compatible)
- PATCH - Bug fixes

### Release Checklist

- [ ] Update version in `__init__.py`
- [ ] Update CHANGELOG.md
- [ ] Run full test suite
- [ ] Update documentation
- [ ] Create release PR
- [ ] Tag release
- [ ] Deploy to PyPI

## 📞 Getting Help

### Communication Channels

- **GitHub Issues** - Bug reports and feature requests
- **GitHub Discussions** - General questions and discussions
- **Email** - fl-fog@project.com for private matters

### Mentorship

New contributors are welcome! We provide:
- Good first issues labeled `good-first-issue`
- Mentorship for complex features
- Code review feedback
- Documentation guidance

## 🎯 Areas for Contribution

### High Priority
- Additional FL aggregation algorithms
- Performance optimizations
- Security enhancements
- Documentation improvements

### Medium Priority
- Monitoring and alerting features
- Configuration management tools
- Integration with other FL frameworks
- Mobile device support

### Learning Opportunities
- Writing tests for existing code
- Improving error messages
- Adding type hints
- Documentation updates
- Example applications

---

Thank you for contributing to FL-Fog! Every contribution, no matter how small, helps make federated learning more accessible and efficient. 🌟
