# netguard/agent/setup.py
"""
NetGuard Agent — Setup para empacotamento e instalação.
Uso: pip install . ou python setup.py install
"""

from setuptools import setup, find_packages

setup(
    name="netguard-agent",
    version="1.6.0",
    description="NetGuard Host Vulnerability Scanner Agent",
    author="NetGuard Team",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "psutil>=5.9.8",
    ],
    entry_points={
        "console_scripts": [
            "netguard-agent=netguard_agent.agent:main",
        ],
    },
    python_requires=">=3.9",
)
