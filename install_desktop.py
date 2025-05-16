#!/usr/bin/env python3
"""
YTScript Desktop Integration Script

This script installs the desktop entry and icon for YTScript
to make it easily accessible from desktop environments.
"""

import os
import sys
import shutil
from pathlib import Path
import subprocess


def install_desktop_entry():
    """Install the YTScript desktop entry."""
    print("Installing YTScript desktop integration...")
    
    # Get script directory
    script_dir = Path(__file__).parent.absolute()
    
    # Source files
    desktop_file = script_dir / "ytscript.desktop"
    icon_file = script_dir / "icon.svg"
    
    if not desktop_file.exists():
        print(f"Error: Desktop entry file not found: {desktop_file}")
        return False
        
    if not icon_file.exists():
        print(f"Error: Icon file not found: {icon_file}")
        return False
    
    # Target directories
    home_dir = Path.home()
    apps_dir = home_dir / ".local/share/applications"
    icons_dir = home_dir / ".local/share/icons/hicolor/scalable/apps"
    
    # Create directories if they don't exist
    apps_dir.mkdir(parents=True, exist_ok=True)
    icons_dir.mkdir(parents=True, exist_ok=True)
    
    # Target files
    target_desktop = apps_dir / "ytscript.desktop"
    target_icon = icons_dir / "ytscript.svg"
    
    # Copy icon file
    try:
        shutil.copy2(icon_file, target_icon)
        print(f"Icon installed to: {target_icon}")
    except Exception as e:
        print(f"Failed to install icon: {e}")
        return False
    
    # Create desktop entry with correct path
    try:
        with open(desktop_file, 'r') as f:
            desktop_content = f.read()
        
        desktop_content = desktop_content.replace('%INSTALL_PATH%', str(script_dir))
        
        with open(target_desktop, 'w') as f:
            f.write(desktop_content)
        
        # Make it executable
        os.chmod(target_desktop, 0o755)
        
        print(f"Desktop entry installed to: {target_desktop}")
    except Exception as e:
        print(f"Failed to install desktop entry: {e}")
        return False
    
    # Update desktop database
    try:
        subprocess.run(
            ["update-desktop-database", str(apps_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False
        )
    except Exception:
        # Not critical if this fails
        pass
    
    print("YTScript desktop integration installed successfully!")
    print("You should now be able to find and run YTScript from your desktop environment's application menu.")
    
    return True


if __name__ == "__main__":
    # Check if running as root
    if os.geteuid() == 0:
        print("Warning: This script should not be run as root. Running for the current user...")
    
    install_desktop_entry()
