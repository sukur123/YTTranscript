# YTScript - Local YouTube Transcript Generator

A fully local YouTube transcript generator that works offline after initial setup.

## Features

- 🎬 Downloads audio from YouTube videos using yt-dlp
- 🎙️ Transcribes audio using OpenAI's Whisper model running locally via whisper.cpp
- 📝 Generates transcript in TXT and optionally SRT format
- 🔍 Optional summarization using local LLMs
- 🖥️ Works entirely offline after installation
- 💻 Command-line interface with flexible options
- 🪟 User-friendly graphical interface

## Requirements

- Python 3.6+
- Build tools (cmake, gcc/g++)
- Git (for installing whisper.cpp)

## Installation

### Quick setup

```bash
# Clone this repository
git clone https://github.com/yourusername/YTScript.git
cd YTScript

# Install dependencies
python3 setup.py
```

The setup script will:
1. Install yt-dlp
2. Install necessary system dependencies
3. Clone and build whisper.cpp
4. Download the Whisper model

### Manual installation

If you prefer manual installation:

1. Install yt-dlp:
   ```bash
   pip install --user yt-dlp
   ```

2. Install whisper.cpp:
   ```bash
   git clone https://github.com/ggerganov/whisper.cpp.git
   cd whisper.cpp
   make
   ```

3. Download a Whisper model:
   ```bash
   cd models
   wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
   ```

## Usage

### Graphical User Interface

Launch the GUI for an easy-to-use interface:

```bash
python3 ytscript.py --gui
```

Or directly:

```bash
python3 gui.py
```

### Command Line Interface

#### Basic usage

```bash
python3 ytscript.py https://www.youtube.com/watch?v=VIDEO_ID
```

or

```bash
python3 yt_script.py https://www.youtube.com/watch?v=VIDEO_ID
```

#### With options

```bash
python3 ytscript.py https://www.youtube.com/watch?v=VIDEO_ID \
  -o /path/to/output/dir \
  --srt \
  --language en \
  --keep-audio \
  -v
```

#### Using a specific whisper.cpp path and model

```bash
python3 ytscript.py https://www.youtube.com/watch?v=VIDEO_ID \
  --whisper-path /path/to/whisper.cpp \
  --model-path /path/to/whisper.cpp/models/ggml-base.en.bin
```

#### Summarization

To enable summarization using a local LLM:

```bash
python3 ytscript.py https://www.youtube.com/watch?v=VIDEO_ID \
  --summarize \
  --llm-path /path/to/llm/model.gguf
```

To list available LLM models:

```bash
python3 ytscript.py --list-llms
```

## Command Line Options

| Option | Description |
|--------|-------------|
| `url` | YouTube video URL to transcribe |
| `-o, --output-dir` | Directory to save the transcript (default: current directory) |
| `--whisper-path` | Path to whisper.cpp directory |
| `--model-path` | Path to Whisper model file |
| `--keep-audio` | Keep the downloaded audio file |
| `--srt` | Generate SRT subtitle file in addition to text transcript |
| `--language` | Language code for transcription (auto-detect if not specified) |
| `-v, --verbose` | Enable verbose output |
| `--setup` | Run the setup script to install dependencies |
| `--summarize` | Generate a summary of the transcript using a local LLM |
| `--llm-path` | Path to the local LLM model for summarization |
| `--list-llms` | List available local LLM models |

## Project Structure

```
YTScript/
├── ytscript.py     # Unified launcher script
├── yt_script.py    # Command-line interface script
├── gui.py          # Graphical user interface script
├── setup.py        # Setup script for installing dependencies
├── config.py       # Configuration loading utilities
├── summarizer.py   # Optional transcript summarization module
└── README.md       # Documentation
```

## Models

### Whisper Models

YTScript supports all Whisper models available in whisper.cpp:

- `tiny.en`: Smallest model, fastest but less accurate
- `base.en`: Good balance of speed and accuracy (default)
- `small.en`: Better accuracy, slower
- `medium.en`: High accuracy, much slower
- `large-v3`: Highest accuracy, very slow

For non-English languages, use the models without the `.en` suffix.

### LLM Models for Summarization

The summarization feature currently supports:
- llama.cpp compatible models (.gguf format)
- Models with at least 7B parameters recommended for good results

## Extending

### Adding Different ASR Engines

You can modify the `YTScript` class to support different ASR engines by implementing a new transcription method.

### Improving Summarization

The summarization module can be extended to support different LLM backends like:
- ExLlama
- CTransformers
- Local API-based models (Ollama, LM Studio, etc.)

## License

MIT License
