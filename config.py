#!/usr/bin/env python3
"""
YTScript Config Loader

This module loads configuration from the config file or environment variables.
"""

import os
import json
from pathlib import Path


def load_config():
    """
    Load configuration from the config file or environment variables.
    
    Returns:
        dict: Configuration dictionary with whisper_path and model_path
    """
    # Default configuration
    config = {
        "whisper_path": os.environ.get("WHISPER_CPP_PATH", "./whisper.cpp"),
        "model_path": os.environ.get("WHISPER_MODEL_PATH", "./models/ggml-base.en.bin"),
    }
    
    # Config file locations to check (in order of preference)
    config_paths = [
        Path("./config.json"),  # Current directory
        Path(os.path.expanduser("~/.config/ytscript/config.json")),  # User config directory
    ]
    
    # Try to load configuration from file
    for config_path in config_paths:
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    file_config = json.load(f)
                    # Update config with values from file
                    config.update(file_config)
                break
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load config from {config_path}: {e}")
    
    return config
