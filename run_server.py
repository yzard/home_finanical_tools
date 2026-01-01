#!/usr/bin/env python3
import os
import sys

# Add the current directory to PYTHONPATH to ensure home_financial_tools can be imported
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from home_financial_tools.server.main import main

if __name__ == "__main__":
    # Set default config path if not provided
    if "CONFIG_PATH" not in os.environ:
        os.environ["CONFIG_PATH"] = "sample/config.yaml"
    
    main()
