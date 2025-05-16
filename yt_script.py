#!/usr/bin/env python3
"""
YTScript - A fully local YouTube transcript generator

This tool downloads audio from YouTube videos and transcribes them
using OpenAI's Whisper model running locally via whisper.cpp.

No internet connection is required after initial setup.
"""

import argparse
import os
import subprocess
import sys
import json
import tempfile
import shutil
from pathlib import Path
from datetime import timedelta

# Import local modules
try:
    from config import load_config
except ImportError:
    # If config.py is not found, define a simple load_config function
    def load_config():
        return {
            "whisper_path": os.environ.get("WHISPER_CPP_PATH", "./whisper.cpp"),
            "model_path": os.environ.get("WHISPER_MODEL_PATH", "./models/ggml-base.en.bin"),
        }


class YTScript:
    """Main class for handling YouTube transcription workflow."""

    def __init__(self, whisper_path, model_path, verbose=False):
        """
        Initialize the YTScript with paths to required components.

        Args:
            whisper_path: Path to whisper.cpp main folder
            model_path: Path to the Whisper model file
            verbose: Whether to print verbose output
        """
        self.whisper_path = Path(whisper_path).expanduser().absolute()
        self.model_path = Path(model_path).expanduser().absolute()
        self.verbose = verbose
        
        # Verify required components exist
        self._verify_dependencies()

    def _verify_dependencies(self):
        """Verify that all required dependencies are installed and accessible."""
        # Check if yt-dlp is installed
        try:
            result = subprocess.run(
                ["yt-dlp", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            if self.verbose:
                print(f"Found yt-dlp: {result.stdout.strip()}")
        except FileNotFoundError:
            sys.exit("Error: yt-dlp not found. Please install it using the setup script.")

        # Check if whisper.cpp exists at the specified path
        whisper_executable = self.whisper_path / "main"
        if not whisper_executable.exists():
            sys.exit(f"Error: whisper.cpp executable not found at {whisper_executable}")

        # Check if the model file exists
        if not self.model_path.exists():
            sys.exit(f"Error: Whisper model not found at {self.model_path}")

    def download_audio(self, youtube_url, output_dir=None):
        """
        Download audio from a YouTube video.

        Args:
            youtube_url: URL of the YouTube video
            output_dir: Directory to save the audio (temp directory if None)

        Returns:
            Path to the downloaded audio file
        """
        if self.verbose:
            print(f"Downloading audio from: {youtube_url}")
        
        # Create temp directory if output_dir is not specified
        temp_dir = None
        if output_dir is None:
            temp_dir = tempfile.TemporaryDirectory()
            output_dir = temp_dir.name
        else:
            output_dir = Path(output_dir).expanduser().absolute()
            os.makedirs(output_dir, exist_ok=True)

        # Create a unique filename based on the video ID
        output_template = str(Path(output_dir) / "%(id)s.%(ext)s")
        
        # Download the audio using yt-dlp
        command = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "wav",  # wav format works well with whisper
            "--audio-quality", "0",   # highest quality
            "--output", output_template,
            "--quiet" if not self.verbose else "--progress",
            youtube_url
        ]
        
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as e:
            if temp_dir:
                temp_dir.cleanup()
            sys.exit(f"Error downloading video: {e}")
        
        # Find the downloaded file
        audio_files = list(Path(output_dir).glob("*.wav"))
        if not audio_files:
            if temp_dir:
                temp_dir.cleanup()
            sys.exit("Failed to download audio")
        
        audio_path = audio_files[0]
        if self.verbose:
            print(f"Audio downloaded to: {audio_path}")
        
        # Return the path to the audio file and the temp directory (if created)
        return audio_path, temp_dir

    def transcribe(self, audio_path, output_dir=None, generate_srt=False, language=None):
        """
        Transcribe audio using whisper.cpp.

        Args:
            audio_path: Path to the audio file
            output_dir: Directory to save the transcript
            generate_srt: Whether to generate SRT subtitle file
            language: Language code for transcription (auto-detect if None)

        Returns:
            Path to the transcript file
        """
        if self.verbose:
            print(f"Transcribing audio file: {audio_path}")
        
        # Determine output directory
        if output_dir is None:
            output_dir = Path(audio_path).parent
        else:
            output_dir = Path(output_dir).expanduser().absolute()
            os.makedirs(output_dir, exist_ok=True)
        
        # Base output filename (without extension)
        base_output = output_dir / Path(audio_path).stem
        
        # Prepare whisper.cpp command
        whisper_cmd = [
            str(self.whisper_path / "main"),
            "-m", str(self.model_path),
            "-f", str(audio_path),
            "-otxt",  # Output plain text
        ]
        
        # Add SRT output if requested
        if generate_srt:
            whisper_cmd.append("-osrt")
        
        # Add language if specified
        if language:
            whisper_cmd.extend(["-l", language])
        
        if self.verbose:
            print(f"Running whisper.cpp command: {' '.join(whisper_cmd)}")
        
        try:
            result = subprocess.run(
                whisper_cmd,
                check=True,
                stdout=subprocess.PIPE if not self.verbose else None,
                stderr=subprocess.PIPE if not self.verbose else None,
                cwd=str(output_dir)
            )
        except subprocess.CalledProcessError as e:
            sys.exit(f"Error during transcription: {e}")
        
        # Whisper.cpp saves output files in the current working directory
        txt_output = output_dir / f"{Path(audio_path).stem}.txt"
        srt_output = output_dir / f"{Path(audio_path).stem}.srt" if generate_srt else None
        
        if self.verbose:
            print(f"Transcription complete.")
            print(f"Text transcript: {txt_output}")
            if generate_srt:
                print(f"SRT subtitle file: {srt_output}")
        
        return txt_output, srt_output

    def process_video(self, youtube_url, output_dir=None, generate_srt=False, language=None, keep_audio=False):
        """
        Process a YouTube video: download and transcribe.

        Args:
            youtube_url: URL of the YouTube video
            output_dir: Directory to save the outputs
            generate_srt: Whether to generate SRT subtitle file
            language: Language code for transcription
            keep_audio: Whether to keep the downloaded audio file

        Returns:
            Tuple of paths to the output files (txt, srt if generated)
        """
        if self.verbose:
            print(f"Processing video: {youtube_url}")
        
        # Create output directory if specified
        if output_dir:
            output_dir = Path(output_dir).expanduser().absolute()
            os.makedirs(output_dir, exist_ok=True)
        
        # Download audio
        audio_path, temp_dir = self.download_audio(youtube_url, output_dir)
        
        try:
            # Transcribe audio
            txt_path, srt_path = self.transcribe(
                audio_path, 
                output_dir, 
                generate_srt=generate_srt,
                language=language
            )
            
            # If user doesn't want to keep the audio and we're not using a temp dir, delete it
            if not keep_audio and not temp_dir and audio_path.exists():
                if self.verbose:
                    print(f"Removing audio file: {audio_path}")
                os.remove(audio_path)
                
            # If we're using a temp directory but want to keep the outputs,
            # move them to the output directory
            if temp_dir and output_dir:
                if txt_path.exists():
                    shutil.copy(txt_path, output_dir)
                    txt_path = output_dir / txt_path.name
                if srt_path and srt_path.exists():
                    shutil.copy(srt_path, output_dir)
                    srt_path = output_dir / srt_path.name
            
            return txt_path, srt_path
            
        finally:
            # Clean up temp directory if created
            if temp_dir:
                temp_dir.cleanup()


def parse_arguments():
    """Parse command line arguments."""
    # Load configuration
    config = load_config()
    
    parser = argparse.ArgumentParser(
        description="YTScript - A fully local YouTube transcript generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "url",
        help="YouTube video URL to transcribe"
    )
    
    parser.add_argument(
        "-o", "--output-dir",
        help="Directory to save the transcript (default: current directory)",
        default=os.getcwd()
    )
    
    parser.add_argument(
        "--whisper-path",
        help="Path to whisper.cpp directory",
        default=config["whisper_path"]
    )
    
    parser.add_argument(
        "--model-path",
        help="Path to Whisper model file",
        default=config["model_path"]
    )
    
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Keep the downloaded audio file"
    )
    
    parser.add_argument(
        "--srt",
        action="store_true",
        help="Generate SRT subtitle file in addition to text transcript"
    )
    
    parser.add_argument(
        "--language",
        help="Language code for transcription (auto-detect if not specified)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run the setup script to install dependencies"
    )
    
    # Summarization options
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="Generate a summary of the transcript using a local LLM"
    )
    
    parser.add_argument(
        "--llm-path",
        help="Path to the local LLM model for summarization"
    )
    
    parser.add_argument(
        "--list-llms",
        action="store_true",
        help="List available local LLM models"
    )

    return parser.parse_args()


def main():
    """Main entry point for the script."""
    args = parse_arguments()
    
    # If setup flag is provided, run the setup script
    if args.setup:
        setup_script = Path(__file__).parent / "setup.py"
        if setup_script.exists():
            subprocess.run([sys.executable, str(setup_script)])
        else:
            sys.exit(f"Setup script not found at: {setup_script}")
        return
    
    # If list-llms flag is provided, list available LLMs and exit
    if args.list_llms:
        try:
            from summarizer import get_available_models
            models = get_available_models()
            if models:
                print("Found the following LLM models:")
                for i, model in enumerate(models, 1):
                    print(f"{i}. {model}")
            else:
                print("No LLM models found in common locations.")
        except ImportError:
            print("Error: summarizer module not found. Ensure summarizer.py is in the same directory.")
        return
    
    # Initialize YTScript
    transcriber = YTScript(
        whisper_path=args.whisper_path,
        model_path=args.model_path,
        verbose=args.verbose
    )
    
    # Process the video
    txt_path, srt_path = transcriber.process_video(
        youtube_url=args.url,
        output_dir=args.output_dir,
        generate_srt=args.srt,
        language=args.language,
        keep_audio=args.keep_audio
    )
    
    print("\nTranscription complete!")
    print(f"Text transcript saved to: {txt_path}")
    if srt_path:
        print(f"SRT subtitle file saved to: {srt_path}")
    
    # Print first few lines of the transcript
    if txt_path.exists():
        with open(txt_path, 'r') as f:
            preview = "".join(f.readlines()[:5])
            print("\nTranscript preview:")
            print("-" * 40)
            print(preview + "...")
            print("-" * 40)
    
    # Generate summary if requested
    if args.summarize:
        try:
            from summarizer import LocalSummarizer
            
            print("\nGenerating summary...")
            summarizer = LocalSummarizer(
                model_path=args.llm_path,
                verbose=args.verbose
            )
            
            summary = summarizer.summarize_transcript(txt_path)
            
            if not summary.startswith("Error:"):
                summary_path = summarizer.save_summary(txt_path, summary)
                print(f"\nSummary saved to: {summary_path}")
                print("\nSummary preview:")
                print("-" * 40)
                print(summary[:500] + ("..." if len(summary) > 500 else ""))
                print("-" * 40)
            else:
                print(f"\nError generating summary: {summary}")
                if not args.llm_path:
                    print("\nTip: Use --llm-path to specify a local LLM model for summarization.")
                    print("     Use --list-llms to see available models.")
        except ImportError:
            print("\nError: summarizer module not found. Ensure summarizer.py is in the same directory.")
            print("Continuing without summarization.")


if __name__ == "__main__":
    main()
