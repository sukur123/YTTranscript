#!/usr/bin/env python3
"""
YTScript Local Summarizer

This module provides functionality to summarize transcripts using a local LLM.
"""

import os
import sys
import json
import subprocess
from pathlib import Path


class LocalSummarizer:
    """Class for summarizing transcripts using various local LLM options."""
    
    def __init__(self, model_path=None, model_type="llama.cpp", verbose=False):
        """
        Initialize the summarizer with a local LLM.
        
        Args:
            model_path: Path to the local LLM
            model_type: Type of model/backend to use: "llama.cpp", "ggml", or "exllama"
            verbose: Whether to print verbose output
        """
        self.model_path = Path(model_path) if model_path else None
        self.model_type = model_type
        self.verbose = verbose
        
        # Only verify if a model path is provided
        if self.model_path:
            self._verify_model()
    
    def _verify_model(self):
        """Verify that the model file exists."""
        if not self.model_path.exists():
            sys.exit(f"Error: LLM model not found at {self.model_path}")
        
        if self.verbose:
            print(f"Using {self.model_type} model at: {self.model_path}")
    
    def summarize_with_llama_cpp(self, transcript_text, max_length=500):
        """
        Summarize text using llama.cpp.
        
        Args:
            transcript_text: Text to summarize
            max_length: Maximum length of summary
            
        Returns:
            Summary text
        """
        if not self.model_path or not self.model_path.exists():
            return "Error: No valid LLM model provided for summarization."
        
        llama_path = self.model_path.parent / "main"
        if not llama_path.exists():
            return "Error: llama.cpp executable not found."
            
        # Create a prompt for summarization
        prompt = f"""<|system|>
You are an AI assistant that summarizes transcripts accurately and concisely.
</s>
<|user|>
Please summarize the following transcript in about 250 words:

{transcript_text}
</s>
<|assistant|>
"""
        
        # Use a temporary file for the prompt
        temp_prompt_file = Path("temp_prompt.txt")
        with open(temp_prompt_file, "w") as f:
            f.write(prompt)
        
        try:
            # Run llama.cpp
            command = [
                str(llama_path),
                "-m", str(self.model_path),
                "-f", str(temp_prompt_file),
                "--temp", "0.7",
                "--top-p", "0.9",
                "-n", str(max_length),
                "--color", "0"  # Disable color output
            ]
            
            if self.verbose:
                print(f"Running command: {' '.join(command)}")
            
            result = subprocess.run(
                command,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Extract just the assistant's response
            output = result.stdout.strip()
            response_part = output.split("<|assistant|>")[-1].strip()
            
            return response_part
            
        except subprocess.CalledProcessError as e:
            return f"Error during summarization: {e}"
        finally:
            # Clean up temporary file
            if temp_prompt_file.exists():
                os.remove(temp_prompt_file)
    
    def summarize_transcript(self, transcript_path):
        """
        Summarize a transcript file.
        
        Args:
            transcript_path: Path to the transcript file
            
        Returns:
            Summary text
        """
        if not Path(transcript_path).exists():
            return "Error: Transcript file does not exist."
        
        # Read the transcript file
        with open(transcript_path, "r") as f:
            transcript_text = f.read()
        
        # Truncate if too long (many LLMs have context limits)
        max_chars = 12000  # This assumes a 16K context window model
        if len(transcript_text) > max_chars:
            if self.verbose:
                print(f"Transcript is too long ({len(transcript_text)} chars), truncating to {max_chars} chars")
            transcript_text = transcript_text[:max_chars] + "...[truncated]"
        
        # Use the appropriate summarization method based on model_type
        if self.model_type == "llama.cpp":
            return self.summarize_with_llama_cpp(transcript_text)
        else:
            return "Unsupported model type. Currently only llama.cpp is supported."
    
    def save_summary(self, transcript_path, summary_text):
        """
        Save a summary to a file.
        
        Args:
            transcript_path: Path to the original transcript file
            summary_text: Summary text to save
            
        Returns:
            Path to the saved summary file
        """
        # Create summary file path
        transcript_path = Path(transcript_path)
        summary_path = transcript_path.parent / f"{transcript_path.stem}_summary.txt"
        
        # Write the summary
        with open(summary_path, "w") as f:
            f.write(summary_text)
        
        if self.verbose:
            print(f"Summary saved to: {summary_path}")
        
        return summary_path


def get_available_models():
    """
    Look for available local LLM models in common locations.
    
    Returns:
        List of model paths found
    """
    # Common locations to check for models
    locations = [
        Path.home() / ".local/share/llama.cpp/models",
        Path.home() / "llama.cpp/models",
        Path.home() / "models",
        Path.home() / ".local/share/models",
        Path.home() / "AI/models",
        Path("./models")
    ]
    
    found_models = []
    
    # Common extensions for LLM models
    extensions = [".gguf", ".bin", ".ggml"]
    
    for location in locations:
        if location.exists():
            for ext in extensions:
                models = list(location.glob(f"*{ext}"))
                found_models.extend(models)
    
    return found_models


# This allows the module to be imported or run directly
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="YTScript Local Summarizer - Summarize transcripts with local LLMs",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "transcript",
        help="Path to the transcript file to summarize"
    )
    
    parser.add_argument(
        "--model",
        help="Path to the LLM model file",
        default=None
    )
    
    parser.add_argument(
        "--model-type",
        help="Type of LLM model/backend to use",
        choices=["llama.cpp", "ggml", "exllama"],
        default="llama.cpp"
    )
    
    parser.add_argument(
        "--list-models",
        action="store_true",
        help="List available LLM models"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    args = parser.parse_args()
    
    # List available models if requested
    if args.list_models:
        models = get_available_models()
        if models:
            print("Found the following LLM models:")
            for i, model in enumerate(models, 1):
                print(f"{i}. {model}")
        else:
            print("No LLM models found in common locations.")
        sys.exit(0)
    
    # Create summarizer
    summarizer = LocalSummarizer(
        model_path=args.model,
        model_type=args.model_type,
        verbose=args.verbose
    )
    
    # Summarize the transcript
    summary = summarizer.summarize_transcript(args.transcript)
    
    # Save and display the summary
    if not summary.startswith("Error:"):
        summary_path = summarizer.save_summary(args.transcript, summary)
        print(f"\nSummary saved to: {summary_path}")
        print("\nSummary preview:")
        print("-" * 40)
        print(summary[:500] + ("..." if len(summary) > 500 else ""))
        print("-" * 40)
    else:
        print(f"\nError: {summary}")
