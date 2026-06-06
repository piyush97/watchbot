from setuptools import setup, find_packages

setup(
    name="watchbot",
    version="0.1.0",
    description="Unified homelab + social media monitoring plugin for Hermes Agent",
    author="Piyush Mehta",
    author_email="me@piyushmehta.com",
    license="MIT",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.11",
    install_requires=[
        "hermes-agent>=0.15.0",
        "httpx>=0.27.0",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "watchbot=watchbot.__main__:main",
        ],
    },
    extras_require={
        "dev": ["pytest>=8.0", "pytest-asyncio>=0.24.0", "ruff>=0.4.0"],
        "dashboard": ["flask>=3.0", "plotly>=5.20"],
        "twitter": ["tweepy>=4.14"],
        "all": ["watchbot[dashboard,twitter]"],
    },
)
