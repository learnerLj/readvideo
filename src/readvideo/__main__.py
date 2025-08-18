"""Entry point for running readvideo as a module.

This allows the package to be executed with: python -m readvideo
"""

from .cli import cli

if __name__ == "__main__":
    cli()