#!/usr/bin/env python3
"""
YTScript Setup Script

This script helps set up the environment for YTScript by:
1. Installing yt-dlp
2. Installing system dependencies for whisper.cpp
3. Downloading and building whisper.cpp
4. Downloading Whisper models
"""

import os
import sys
import platform
import subprocess
import argparse
from pathlib import Path
import shutil
import urllib.request
import zipfile
import tarfile
import time


def run_command(command, description=None, exit_on_error=True):
    """Run a shell command and optionally exit on error."""
    if description:
        print(f"{description}...")
    
    result = subprocess.run(
        command, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        text=True,
        shell=True
    )
    
    if result.returncode != 0:
        print(f"Command failed: {command}")
        print(f"Error: {result.stderr}")
        if exit_on_error:
            sys.exit(1)
        return False
    
    return True


def is_command_available(command):
    """Check if a command is available in the system PATH."""
    try:
        # Use 'which' on Unix-like systems
        subprocess.run(
            ["which", command], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Try another method just to be sure (works on most systems)
        try:
            devnull = open(os.devnull, "w")
            subprocess.Popen([command], stdout=devnull, stderr=devnull).communicate()
            return True
        except (OSError, FileNotFoundError):
            return False


def install_yt_dlp():
    """Install yt-dlp using pip."""
    print("\n=== Installing yt-dlp ===")
    
    if is_command_available("yt-dlp"):
        print("yt-dlp is already installed.")
        return True
    
    try:
        # Try to install with pip
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--user", "yt-dlp"],
            check=True
        )
        print("yt-dlp installed successfully with pip.")
        return True
    except subprocess.CalledProcessError:
        print("Failed to install yt-dlp with pip.")
        return False


def install_system_dependencies():
    """Install system dependencies based on the platform."""
    print("\n=== Installing system dependencies ===")
    
    system = platform.system().lower()
    
    if system == "linux":
        # Try to detect Linux distribution
        try:
            # Try to read os-release file
            os_info = {}
            if os.path.exists('/etc/os-release'):
                with open('/etc/os-release', 'r') as f:
                    for line in f:
                        if '=' in line:
                            key, value = line.rstrip().split('=', 1)
                            os_info[key] = value.strip('"\'')
            
            distro = os_info.get('ID', '').lower()
            print(f"Detected Linux distribution: {distro}")
            
            # Also check ID_LIKE for derivatives
            distro_like = os_info.get('ID_LIKE', '').lower().split()
        except Exception:
            distro = ""
            distro_like = []
            print("Could not detect Linux distribution.")
        
        # Detect package manager and install appropriate packages
        if is_command_available("apt-get") or distro in ["ubuntu", "debian", "mint", "pop"] or "debian" in distro_like:
            # Debian/Ubuntu and derivatives
            run_command(
                "sudo apt-get update && sudo apt-get install -y build-essential cmake g++ git ffmpeg ccache",
                "Installing dependencies with apt-get"
            )
        elif is_command_available("dnf") or distro in ["fedora", "rhel", "centos", "rocky"] or any(d in distro_like for d in ["fedora", "rhel"]):
            # Fedora/RHEL/CentOS and derivatives
            run_command(
                "sudo dnf install -y cmake gcc-c++ git make ffmpeg ccache",
                "Installing dependencies with dnf"
            )
        elif is_command_available("pacman") or distro == "arch" or distro == "manjaro":
            # Arch Linux and derivatives
            run_command(
                "sudo pacman -Sy --needed cmake gcc git make ffmpeg",
                "Installing dependencies with pacman"
            )
        elif is_command_available("zypper") or distro == "opensuse":
            # openSUSE
            run_command(
                "sudo zypper install -y cmake gcc-c++ git make ffmpeg",
                "Installing dependencies with zypper"
            )
        elif is_command_available("apk") or distro == "alpine":
            # Alpine Linux
            run_command(
                "sudo apk add cmake g++ git make ffmpeg",
                "Installing dependencies with apk"
            )
        else:
            print("Unsupported Linux distribution. Please install these packages manually:")
            print("- cmake")
            print("- gcc/g++")
            print("- git")
            print("- make")
    elif system == "darwin":
        # macOS
        if is_command_available("brew"):
            run_command(
                "brew install cmake gcc git",
                "Installing dependencies with Homebrew"
            )
        else:
            print("Homebrew not found. Please install it from https://brew.sh and then install: cmake, gcc, git.")
    elif system == "windows":
        print("On Windows, please install these dependencies manually:")
        print("1. Visual Studio with C++ support")
        print("2. CMake: https://cmake.org/download/")
        print("3. Git: https://git-scm.com/download/win")
    else:
        print(f"Unsupported platform: {system}")
    print("System dependencies installed successfully.")
    return True


def download_whisper_cpp(install_dir):
    """
    Download and build whisper.cpp.
    
    Args:
        install_dir: Directory to install whisper.cpp
    
    Returns:
        Path to the whisper.cpp directory
    """
    print("\n=== Setting up whisper.cpp ===")
    
    # Create the install directory if it doesn't exist
    install_path = Path(install_dir).expanduser().absolute()
    models_path = install_path / "models"
    os.makedirs(models_path, exist_ok=True)
    
    whisper_path = install_path / "whisper.cpp"
    
    # Check if the directory exists but might be empty or corrupted
    if whisper_path.exists():
        if not (whisper_path / "Makefile").exists():
            print(f"Found whisper.cpp directory at {whisper_path} but it appears to be incomplete.")
            print("Removing existing directory and cloning again...")
            try:
                shutil.rmtree(whisper_path)
            except Exception as e:
                print(f"Error removing directory: {e}")
                print(f"Please manually remove {whisper_path} and try again.")
                return None
        else:
            # Reset any potential changes in the repository to avoid build issues
            run_command(
                f"cd {whisper_path} && git reset --hard && git clean -fd",
                "Resetting whisper.cpp repository to clean state",
                exit_on_error=False
            )
    
    # Clone whisper.cpp if it doesn't exist
    if not whisper_path.exists():
        print(f"Cloning whisper.cpp to {whisper_path}...")
        run_command(
            f"git clone https://github.com/ggerganov/whisper.cpp.git {whisper_path}",
            "Cloning whisper.cpp repository"
        )
    else:
        print(f"whisper.cpp already exists at {whisper_path}")
        # Pull the latest changes
        run_command(
            f"cd {whisper_path} && git pull",
            "Updating whisper.cpp repository"
        )
    
    # Check if Makefile exists before attempting to build
    if not (whisper_path / "Makefile").exists():
        print("Error: Makefile not found in whisper.cpp directory.")
        print("The repository may not have been cloned correctly.")
        return None
    
    # Build whisper.cpp
    print("Building whisper.cpp...")
    
    # Use the Makefile directly (no "clean" target which might not exist)
    build_cmd = f"cd {whisper_path} && make"
    result = run_command(
        build_cmd,
        "Building whisper.cpp",
        exit_on_error=False
    )
    
    # If that fails, try with cmake with special flags to bypass ccache if needed
    if not result:
        print("Standard build failed. Trying alternative build approach...")
        
        # Check if ccache is available
        if not is_command_available("ccache"):
            print("Note: ccache is not installed. Using alternative build configuration.")
            # Set environment variable to disable ccache
            cmake_build_cmd = (
                f"cd {whisper_path} && "
                f"mkdir -p build && cd build && "
                f"cmake -DGGML_NATIVE=OFF -DGGML_NO_CCACHE=ON .. && "
                f"cmake --build . --config Release"
            )
        else:
            cmake_build_cmd = (
                f"cd {whisper_path} && "
                f"mkdir -p build && cd build && "
                f"cmake .. && "
                f"cmake --build . --config Release"
            )
        
        result = run_command(
            cmake_build_cmd,
            "Building whisper.cpp with CMake",
            exit_on_error=False
        )
        
    # If that fails too, try one more approach with manual compilation flags
    if not result:
        print("CMake build failed. Trying basic build without optimization...")
        basic_build_cmd = (
            f"cd {whisper_path} && "
            f"make CFLAGS=\"-O2\" whisper"
        )
        result = run_command(
            basic_build_cmd,
            "Building whisper.cpp with basic options",
            exit_on_error=False
        )
    
    # Check if the main executable exists in potential locations
    main_executable_paths = [
        whisper_path / "main",                # Standard make build
        whisper_path / "build" / "main",      # CMake build
        whisper_path / "build" / "bin" / "main"  # Alternative CMake location
    ]
    
    main_executable = None
    for path in main_executable_paths:
        if path.exists():
            main_executable = path
            break
    
    if main_executable is None:
        print("whisper.cpp build failed. The executable was not found.")
        print("Please build whisper.cpp manually with the following commands:")
        print(f"cd {whisper_path}")
        print("make")
        return None
    
    print(f"whisper.cpp built successfully!")
    print(f"Main executable found at: {main_executable}")
    
    # Create a symlink to the main executable in the whisper.cpp root if it's not there
    if not (whisper_path / "main").exists() and main_executable != whisper_path / "main":
        try:
            os.symlink(main_executable, whisper_path / "main")
            print(f"Created symlink to main executable in {whisper_path}")
        except Exception as e:
            print(f"Note: Could not create symlink to main executable: {e}")
    
    return whisper_path


def download_whisper_model(models_dir, model_name="base.en"):
    """
    Download a Whisper model.
    
    Args:
        models_dir: Directory to save the model
        model_name: Model name/size to download (tiny.en, base.en, small.en, medium.en, large-v3)
    
    Returns:
        Path to the downloaded model
    """
    print(f"\n=== Downloading Whisper {model_name} model ===")
    
    # Create models directory if it doesn't exist
    models_path = Path(models_dir).expanduser().absolute()
    os.makedirs(models_path, exist_ok=True)
    
    model_filename = f"ggml-{model_name}.bin"
    model_path = models_path / model_filename
    
    # Check if model already exists
    if model_path.exists():
        print(f"Model already exists at {model_path}")
        return model_path
    
    # Model URLs from the whisper.cpp repository
    model_url = f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/{model_filename}"
    
    print(f"Downloading model from: {model_url}")
    print(f"This may take a while depending on your internet connection...")
    
    try:
        # Create a progress reporting callback
        def report_progress(block_num, block_size, total_size):
            if total_size > 0:
                percent = min(100, block_num * block_size * 100 / total_size)
                # Only update progress every 5%
                if int(percent) % 5 == 0:
                    sys.stdout.write(f"\rDownloading: {percent:.1f}%")
                    sys.stdout.flush()
        
        # Download the model with progress reporting
        urllib.request.urlretrieve(model_url, model_path, reporthook=report_progress)
        print(f"\nModel downloaded successfully to: {model_path}")
        return model_path
    except Exception as e:
        print(f"\nFailed to download model: {e}")
        
        # If the file was partially downloaded, remove it
        if model_path.exists():
            try:
                os.remove(model_path)
                print(f"Removed partial download file: {model_path}")
            except Exception:
                pass
        
        return None


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="YTScript Setup - Install dependencies for YTScript",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--install-dir",
        help="Directory to install whisper.cpp and models",
        default=os.path.expanduser("~/.ytscript")
    )
    
    parser.add_argument(
        "--model",
        help="Whisper model to download",
        choices=["tiny.en", "base.en", "small.en", "medium.en", "large-v3"],
        default="base.en"
    )
    
    parser.add_argument(
        "--no-system-deps",
        action="store_true",
        help="Skip installation of system dependencies"
    )
    
    parser.add_argument(
        "--no-yt-dlp",
        action="store_true",
        help="Skip installation of yt-dlp"
    )
    
    parser.add_argument(
        "--with-gui",
        action="store_true",
        help="Install GUI dependencies (tkinter)"
    )
    
    return parser.parse_args()


def create_config_file(config_path, whisper_path, model_path):
    """Create a configuration file with paths to whisper.cpp and the model."""
    config = {
        "whisper_path": str(whisper_path),
        "model_path": str(model_path)
    }
    
    with open(config_path, "w") as f:
        import json
        json.dump(config, f, indent=2)
    
    print(f"Configuration saved to: {config_path}")


def main():
    """Main entry point for the setup script."""
    print("YTScript Setup - Installing dependencies")
    
    args = parse_arguments()
    
    # Create install directory
    install_dir = Path(args.install_dir).expanduser().absolute()
    os.makedirs(install_dir, exist_ok=True)
    
    # Create config directory inside the user's home directory
    config_dir = Path(os.path.expanduser("~/.config/ytscript"))
    os.makedirs(config_dir, exist_ok=True)
    
    # Install yt-dlp if requested
    if not args.no_yt_dlp:
        install_yt_dlp()
    
    # Install system dependencies if requested
    if not args.no_system_deps:
        install_system_dependencies()
    
    # Download and build whisper.cpp
    whisper_path = download_whisper_cpp(install_dir)
    if not whisper_path:
        print("Failed to set up whisper.cpp. Please check the error messages above.")
        sys.exit(1)
    
    # Download Whisper model
    model_path = download_whisper_model(whisper_path / "models", args.model)
    if not model_path:
        print("Failed to download the Whisper model. Please check the error messages above.")
        sys.exit(1)
    
    # Create configuration file
    config_path = config_dir / "config.json"
    create_config_file(config_path, whisper_path, model_path)
    
    print("\n=== Setup completed successfully! ===")
    print(f"whisper.cpp installed at: {whisper_path}")
    print(f"Whisper model installed at: {model_path}")
    print("\nYou can now run YTScript with:")
    print(f"  python3 yt_script.py --whisper-path {whisper_path} --model-path {model_path} <youtube_url>")
    print("Or, to use the saved configuration:")
    print("  python3 yt_script.py <youtube_url>")


if __name__ == "__main__":
    main()
