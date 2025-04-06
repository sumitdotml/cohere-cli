from setuptools import setup, find_packages

setup(
    name="cohere-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "cohere>=4.37",
        "prompt_toolkit>=3.0.0",
        "rich>=13.0.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "cohere=cohere_cli.client:chat_loop",
        ],
    },
)
