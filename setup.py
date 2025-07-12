#!/usr/bin/env python3
"""
Setup script for FL-Fog package.

Fog computing layer for federated learning in continuum environments.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the contents of README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding='utf-8')

# Read requirements
requirements = []
requirements_path = this_directory / "requirements.txt"
if requirements_path.exists():
    requirements = requirements_path.read_text().strip().split('\n')
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith('#')]

# Read version from __init__.py
version = "0.1.0"
init_file = this_directory / "fog_node" / "__init__.py"
if init_file.exists():
    for line in init_file.read_text().split('\n'):
        if line.startswith('__version__'):
            version = line.split('=')[1].strip().strip('"').strip("'")
            break

setup(
    name="fl-fog",
    version=version,
    author="TFM Federated Learning Team",
    author_email="fl-fog@project.com",
    description="Fog computing layer for federated learning in continuum environments",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/TFM-Federated-learning-on-edge-nodes",
    project_urls={
        "Bug Tracker": "https://github.com/your-org/TFM-Federated-learning-on-edge-nodes/issues",
        "Documentation": "https://fl-fog.readthedocs.io/",
        "Source Code": "https://github.com/your-org/TFM-Federated-learning-on-edge-nodes/tree/main/fl-fog",
    },
    packages=find_packages(exclude=["tests", "tests.*", "docs", "docs.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: System :: Distributed Computing",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=6.2.0",
            "pytest-asyncio>=0.18.0",
            "pytest-cov>=2.12.0",
            "coverage>=5.5.0",
            "black>=21.0.0",
            "flake8>=3.9.0",
            "mypy>=0.910",
            "isort>=5.9.0",
            "pre-commit>=2.15.0",
        ],
        "docs": [
            "sphinx>=4.0.0",
            "sphinx-rtd-theme>=0.5.0",
            "sphinx-autodoc-typehints>=1.12.0",
            "myst-parser>=0.15.0",
        ],
        "monitoring": [
            "prometheus-client>=0.12.0",
            "grafana-api>=1.0.3",
        ],
    },
    entry_points={
        "console_scripts": [
            "fl-fog=fog_node.main:main",
            "fog-node=fog_node.main:main",
            "fl-fog-monitor=fog_node.monitoring:main",
        ],
    },
    include_package_data=True,
    package_data={
        "fog_node": ["config/*.yaml", "config/*.yml"],
        "": ["*.md", "*.txt", "*.yaml", "*.yml"],
    },
    zip_safe=False,
    keywords=[
        "federated-learning",
        "fog-computing", 
        "continuum-computing",
        "edge-computing",
        "distributed-ai",
        "machine-learning",
        "privacy-preserving",
    ],
)
