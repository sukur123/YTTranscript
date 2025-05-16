#!/usr/bin/env python3
"""
YTScript Launcher

This script provides a unified entry point for YTScript, launching either
the GUI or command-line version based on arguments.

Usage:
  python ytscript.py [options]  # Command-line mode
  python ytscript.py --gui      # GUI mode
"""

import sys
import os
import argparse
from pathlib import Path


def main():
    """Main entry point for the launcher."""
    parser = argparse.ArgumentParser(
        description="YTScript - A fully local YouTube transcript generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch in GUI mode"
    )
    
    # Parse only the GUI flag
    args, remaining_args = parser.parse_known_args()
    
    # Determine script directory
    script_dir = Path(__file__).parent
    
    if args.gui:
        # Launch GUI mode
        try:
            # Import the GUI module and run it
            sys.path.insert(0, str(script_dir))
            from gui import main as gui_main
            gui_main()
        except ImportError as e:
            print(f"Error: Failed to import GUI module: {e}")
            print("Make sure the GUI prerequisites are installed.")
            sys.exit(1)
    else:
        # Launch CLI mode by calling yt_script.py
        cli_script = script_dir / "yt_script.py"
        if not cli_script.exists():
            print(f"Error: CLI script not found at {cli_script}")
            sys.exit(1)
        
        # Replace current process with the CLI script
        os.execv(sys.executable, [sys.executable, str(cli_script)] + sys.argv[1:])


if __name__ == "__main__":
    main()
