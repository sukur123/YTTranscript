#!/usr/bin/env python3
"""
YTScript GUI - Graphical User Interface for YTScript

This module provides a GUI for the YTScript tool, making it easier to:
1. Download audio from YouTube videos
2. Transcribe audio using OpenAI's Whisper model running locally
3. Generate summaries using local LLMs
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import threading
import queue
import subprocess
from pathlib import Path
import re
import time
import json
from datetime import datetime
import shutil
import webbrowser

# Import local modules
try:
    from config import load_config
    from yt_script import YTScript
    try:
        from summarizer import get_available_models, LocalSummarizer
        SUMMARIZER_AVAILABLE = True
    except ImportError:
        SUMMARIZER_AVAILABLE = False
except ImportError:
    messagebox.showerror("Error", "Could not import YTScript modules. Make sure you're running from the correct directory.")
    sys.exit(1)


class RedirectText:
    """Class to redirect stdout to a tkinter widget."""
    
    def __init__(self, text_widget):
        """Initialize with text widget to redirect to."""
        self.text_widget = text_widget
        self.queue = queue.Queue()
        self.update_timer = None
        
    def write(self, string):
        """Write text to the queue."""
        self.queue.put(string)
        
    def flush(self):
        """Flush the stream."""
        pass
    
    def update_widget(self):
        """Update the text widget with text from the queue."""
        while not self.queue.empty():
            text = self.queue.get_nowait()
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, text)
            self.text_widget.see(tk.END)
            self.text_widget.configure(state='disabled')
        
        # Schedule next update
        self.update_timer = self.text_widget.after(100, self.update_widget)
    
    def stop_updates(self):
        """Stop the periodic updates."""
        if self.update_timer:
            self.text_widget.after_cancel(self.update_timer)
            self.update_timer = None


class YTScriptGUI(tk.Tk):
    """Main GUI class for YTScript."""
    
    def __init__(self):
        """Initialize the GUI."""
        super().__init__()
        
        # Load config
        self.config = load_config()
        
        # Set up the window
        self.title("YTScript - YouTube Transcript Generator")
        self.geometry("950x650")
        self.minsize(800, 600)
        
        # Set application icon
        try:
            icon_path = Path(__file__).parent / "icon.svg"
            if icon_path.exists():
                self.iconphoto(True, tk.PhotoImage(file=str(icon_path)))
        except Exception:
            pass  # Ignore icon errors
        
        # Theme settings
        self.theme_mode = tk.StringVar(value=self._load_theme_preference())
        self.available_themes = ttk.Style().theme_names()
        
        # Apply theme
        self._apply_theme(self.theme_mode.get())
        
        # Create variables
        self.youtube_url = tk.StringVar()
        self.output_dir = tk.StringVar(value=self._load_last_output_dir())
        self.whisper_path = tk.StringVar(value=self.config["whisper_path"])
        self.model_path = tk.StringVar(value=self.config["model_path"])
        self.keep_audio = tk.BooleanVar(value=False)
        self.generate_srt = tk.BooleanVar(value=False)
        self.language = tk.StringVar()
        self.generate_summary = tk.BooleanVar(value=False)
        self.llm_path = tk.StringVar()
        
        # Load history
        self.history = self._load_history()
        
        # Create main frame with padding
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Setup drag and drop for URL (TkinterDnD is not available by default)
        try:
            self.drop_target_register(tk.DND_TEXT)
            self.dnd_bind('<<Drop>>', self._handle_drop)
        except (AttributeError, tk.TclError):
            print("Note: Drag and drop support not available. TkinterDnD not installed.")
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Create main tab
        main_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(main_tab, text="Transcribe")
        
        # Create history tab
        history_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(history_tab, text="History")
        
        # Create settings tab
        settings_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(settings_tab, text="Settings")
        
        # Create about tab
        about_tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(about_tab, text="About")
        
        # Design main tab
        self._setup_main_tab(main_tab)
        
        # Design history tab
        self._setup_history_tab(history_tab)
        
        # Design settings tab
        self._setup_settings_tab(settings_tab)
        
        # Design about tab
        self._setup_about_tab(about_tab)
        
        # Create status bar
        status_frame = ttk.Frame(self, relief=tk.SUNKEN, padding=(2, 2, 2, 2))
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.status_var = tk.StringVar(value="Ready")
        status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor=tk.W)
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Create progress bar
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            status_frame, 
            orient=tk.HORIZONTAL, 
            length=200, 
            mode='determinate',
            variable=self.progress_var
        )
        self.progress_bar.pack(side=tk.RIGHT, padx=10)
        self.progress_bar.pack_forget()  # Hide initially
        
        # Theme toggle button in status bar
        theme_btn = ttk.Button(
            status_frame, 
            text="🌓", 
            width=3,
            command=self._toggle_theme
        )
        theme_btn.pack(side=tk.RIGHT, padx=5)
        
        # Last setup steps
        self._check_settings()
        self._update_summary_ui()
        self._setup_keyboard_shortcuts()
    
    def _setup_main_tab(self, parent):
        """Set up the main tab UI elements."""
        # YouTube URL section with drag-drop hint
        url_frame = ttk.LabelFrame(parent, text="YouTube Video URL", padding="5")
        url_frame.pack(fill=tk.X, pady=5)
        
        url_entry = ttk.Entry(url_frame, textvariable=self.youtube_url, width=50)
        url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Hint label for drag and drop
        dnd_label = ttk.Label(url_frame, text="(drag & drop supported)", foreground="gray")
        dnd_label.pack(side=tk.LEFT, padx=5)
        
        paste_btn = ttk.Button(url_frame, text="Paste", command=self._paste_url)
        paste_btn.pack(side=tk.RIGHT, padx=5)
        
        # Output directory section
        output_frame = ttk.LabelFrame(parent, text="Output Directory", padding="5")
        output_frame.pack(fill=tk.X, pady=5)
        
        output_entry = ttk.Entry(output_frame, textvariable=self.output_dir, width=50)
        output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        browse_btn = ttk.Button(output_frame, text="Browse...", command=self._browse_output_dir)
        browse_btn.pack(side=tk.RIGHT, padx=5)
        
        # Options section
        options_frame = ttk.LabelFrame(parent, text="Options", padding="5")
        options_frame.pack(fill=tk.X, pady=5)
        
        ttk.Checkbutton(options_frame, text="Keep audio file", variable=self.keep_audio).grid(column=0, row=0, sticky=tk.W, padx=5, pady=2)
        ttk.Checkbutton(options_frame, text="Generate SRT subtitles", variable=self.generate_srt).grid(column=0, row=1, sticky=tk.W, padx=5, pady=2)
        
        ttk.Label(options_frame, text="Language (optional):").grid(column=1, row=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(options_frame, textvariable=self.language, width=5).grid(column=1, row=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(options_frame, text="Leave empty for auto-detection").grid(column=1, row=2, sticky=tk.W, padx=5, pady=0)
        
        # Summary section
        if SUMMARIZER_AVAILABLE:
            summary_frame = ttk.LabelFrame(parent, text="Summarization", padding="5")
            summary_frame.pack(fill=tk.X, pady=5)
            
            self.summary_check = ttk.Checkbutton(summary_frame, text="Generate summary", variable=self.generate_summary, command=self._update_summary_ui)
            self.summary_check.grid(column=0, row=0, sticky=tk.W, padx=5, pady=2)
            
            ttk.Label(summary_frame, text="LLM Model:").grid(column=0, row=1, sticky=tk.W, padx=5, pady=2)
            
            self.model_combo = ttk.Combobox(summary_frame, textvariable=self.llm_path, width=50, state="readonly")
            self.model_combo.grid(column=1, row=1, sticky=tk.W, padx=5, pady=2)
            
            # Populate the model list
            self._populate_model_list()
        
        # Action buttons with better styling
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=10)
        
        self.run_btn = ttk.Button(
            btn_frame, 
            text="Download and Transcribe", 
            command=self._run_transcription,
            style="Accent.TButton"
        )
        self.run_btn.pack(side=tk.LEFT, padx=5)
        
        self.cancel_btn = ttk.Button(
            btn_frame, 
            text="Cancel", 
            command=self._cancel_operation, 
            state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = ttk.Button(
            btn_frame, 
            text="Clear", 
            command=self._clear_form
        )
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        open_folder_btn = ttk.Button(
            btn_frame, 
            text="Open Output Folder", 
            command=self._open_output_folder
        )
        open_folder_btn.pack(side=tk.RIGHT, padx=5)
        
        # Console output with better styling
        console_frame = ttk.LabelFrame(parent, text="Console Output", padding="5")
        console_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Add a toolbar for console
        console_toolbar = ttk.Frame(console_frame)
        console_toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(
            console_toolbar, 
            text="Clear Console", 
            command=self._clear_console
        ).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(
            console_toolbar, 
            text="Copy to Clipboard", 
            command=self._copy_console
        ).pack(side=tk.LEFT, padx=2)
        
        # Console text widget
        self.console = scrolledtext.ScrolledText(
            console_frame, 
            wrap=tk.WORD, 
            height=10,
            background="#f5f5f5"  # Light gray background
        )
        self.console.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.console.configure(state='disabled')
        
        # Setup text redirection
        self.redirect = RedirectText(self.console)
        
        # Initialize process variable
        self.process = None
    
    def _setup_settings_tab(self, parent):
        """Set up the settings tab UI elements."""
        # Create a notebook for settings categories
        settings_notebook = ttk.Notebook(parent)
        settings_notebook.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create tabs for different settings categories
        paths_tab = ttk.Frame(settings_notebook, padding="10")
        appearance_tab = ttk.Frame(settings_notebook, padding="10")
        tools_tab = ttk.Frame(settings_notebook, padding="10")
        
        settings_notebook.add(paths_tab, text="Paths")
        settings_notebook.add(appearance_tab, text="Appearance")
        settings_notebook.add(tools_tab, text="Tools")
        
        # === Paths Tab ===
        self._setup_paths_settings(paths_tab)
        
        # === Appearance Tab ===
        self._setup_appearance_settings(appearance_tab)
        
        # === Tools Tab ===
        self._setup_tools_settings(tools_tab)
    
    def _setup_paths_settings(self, parent):
        """Set up the paths settings tab."""
        # Whisper.cpp path section
        whisper_frame = ttk.LabelFrame(parent, text="Whisper.cpp Path", padding="5")
        whisper_frame.pack(fill=tk.X, pady=5)
        
        whisper_entry = ttk.Entry(whisper_frame, textvariable=self.whisper_path, width=50)
        whisper_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        whisper_btn = ttk.Button(whisper_frame, text="Browse...", command=lambda: self._browse_path(self.whisper_path))
        whisper_btn.pack(side=tk.RIGHT, padx=5)
        
        # Whisper model path section
        model_frame = ttk.LabelFrame(parent, text="Whisper Model Path", padding="5")
        model_frame.pack(fill=tk.X, pady=5)
        
        model_entry = ttk.Entry(model_frame, textvariable=self.model_path, width=50)
        model_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        model_btn = ttk.Button(model_frame, text="Browse...", command=lambda: self._browse_path(self.model_path, filetypes=[("Model Files", "*.bin")]))
        model_btn.pack(side=tk.RIGHT, padx=5)
        
        # Default output directory
        output_frame = ttk.LabelFrame(parent, text="Default Output Directory", padding="5")
        output_frame.pack(fill=tk.X, pady=5)
        
        output_entry = ttk.Entry(output_frame, textvariable=self.output_dir, width=50)
        output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        output_btn = ttk.Button(output_frame, text="Browse...", command=self._browse_output_dir)
        output_btn.pack(side=tk.RIGHT, padx=5)
        
        # Setup and save buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, pady=10)
        
        setup_btn = ttk.Button(btn_frame, text="Run Setup Script", command=self._run_setup)
        setup_btn.pack(side=tk.LEFT, padx=5)
        
        save_btn = ttk.Button(btn_frame, text="Save Settings", command=self._save_settings)
        save_btn.pack(side=tk.RIGHT, padx=5)
    
    def _setup_appearance_settings(self, parent):
        """Set up the appearance settings tab."""
        # Theme selection
        theme_frame = ttk.LabelFrame(parent, text="UI Theme", padding="5")
        theme_frame.pack(fill=tk.X, pady=5)
        
        theme_label = ttk.Label(theme_frame, text="Select theme:")
        theme_label.pack(anchor=tk.W, padx=5, pady=5)
        
        # Radio buttons for themes
        theme_choices = ["light", "dark"]
        
        for i, theme in enumerate(theme_choices):
            rb = ttk.Radiobutton(
                theme_frame,
                text=theme.capitalize(),
                variable=self.theme_mode,
                value=theme,
                command=lambda: self._apply_theme(self.theme_mode.get())
            )
            rb.pack(anchor=tk.W, padx=20, pady=2)
        
        # Font size settings
        font_frame = ttk.LabelFrame(parent, text="Font Settings", padding="5")
        font_frame.pack(fill=tk.X, pady=5)
        
        # Font size for console
        font_label = ttk.Label(font_frame, text="Console font size:")
        font_label.pack(anchor=tk.W, padx=5, pady=5)
        
        font_sizes = ["9", "10", "11", "12", "14", "16"]
        self.font_size = tk.StringVar(value="11")
        
        font_combo = ttk.Combobox(
            font_frame,
            textvariable=self.font_size,
            values=font_sizes,
            width=5,
            state="readonly"
        )
        font_combo.pack(anchor=tk.W, padx=20, pady=2)
        font_combo.bind("<<ComboboxSelected>>", self._update_font_size)
        
        # Desktop integration
        desktop_frame = ttk.LabelFrame(parent, text="Desktop Integration", padding="5")
        desktop_frame.pack(fill=tk.X, pady=5)
        
        desktop_btn = ttk.Button(
            desktop_frame,
            text="Install Desktop Entry",
            command=self._install_desktop_entry
        )
        desktop_btn.pack(anchor=tk.W, padx=5, pady=5)
        
        desktop_info = ttk.Label(
            desktop_frame,
            text="This will add YTScript to your application menu.",
            font=("TkDefaultFont", 9),
            foreground="gray"
        )
        desktop_info.pack(anchor=tk.W, padx=5, pady=2)
    
    def _setup_tools_settings(self, parent):
        """Set up the tools settings tab."""
        # Environment info
        env_frame = ttk.LabelFrame(parent, text="Environment Information", padding="5")
        env_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        env_text = scrolledtext.ScrolledText(env_frame, wrap=tk.WORD, height=10)
        env_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Get environment info
        env_info = self._get_environment_info()
        env_text.insert(tk.END, env_info)
        env_text.configure(state='disabled')
        
        # Tools management
        tools_frame = ttk.LabelFrame(parent, text="External Tools", padding="5")
        tools_frame.pack(fill=tk.X, pady=5)
        
        update_tools_btn = ttk.Button(
            tools_frame,
            text="Check for Updates",
            command=self._check_tool_updates
        )
        update_tools_btn.pack(side=tk.LEFT, padx=5, pady=5)
        
        install_deps_btn = ttk.Button(
            tools_frame,
            text="Install Missing Dependencies",
            command=self._install_dependencies
        )
        install_deps_btn.pack(side=tk.LEFT, padx=5, pady=5)
    
    def _setup_about_tab(self, parent):
        """Set up the about tab UI elements."""
        about_frame = ttk.Frame(parent, padding="10")
        about_frame.pack(fill=tk.BOTH, expand=True)
        
        # App title
        title_label = ttk.Label(about_frame, text="YTScript", font=("TkDefaultFont", 18, "bold"))
        title_label.pack(pady=10)
        
        # App description
        desc_text = (
            "YTScript is a fully local YouTube transcript generator that works offline after installation. "
            "It downloads audio from YouTube videos and transcribes them using OpenAI's Whisper model "
            "running locally via whisper.cpp.\n\n"
            "Optionally, it can also generate summaries of the transcripts using local large language models."
        )
        desc_label = ttk.Label(about_frame, text=desc_text, wraplength=600, justify=tk.CENTER)
        desc_label.pack(pady=10)
        
        # Features list
        features_frame = ttk.LabelFrame(about_frame, text="Features", padding="10")
        features_frame.pack(fill=tk.X, padx=30, pady=10)
        
        features = [
            "🎬 Downloads audio from YouTube videos using yt-dlp",
            "🎙️ Transcribes audio using OpenAI's Whisper model running locally",
            "📝 Generates transcript in TXT and optionally SRT format", 
            "🔍 Optional summarization using local LLMs",
            "🖥️ Works entirely offline after installation",
            "🌗 Light and dark theme support",
            "📚 History tracking of transcribed videos"
        ]
        
        for feature in features:
            ttk.Label(features_frame, text=feature).pack(anchor=tk.W, pady=2)
        
        # Links section
        links_frame = ttk.LabelFrame(about_frame, text="Links", padding="10")
        links_frame.pack(fill=tk.X, padx=30, pady=10)
        
        # Style for links
        link_style = {"foreground": "blue", "cursor": "hand2"}
        
        # GitHub link
        github_link = ttk.Label(
            links_frame, 
            text="GitHub Repository", 
            **link_style
        )
        github_link.pack(anchor=tk.W, pady=2)
        github_link.bind(
            "<Button-1>", 
            lambda e: webbrowser.open_new("https://github.com/yourusername/YTScript")
        )
        
        # Whisper.cpp link
        whisper_link = ttk.Label(
            links_frame, 
            text="whisper.cpp", 
            **link_style
        )
        whisper_link.pack(anchor=tk.W, pady=2)
        whisper_link.bind(
            "<Button-1>", 
            lambda e: webbrowser.open_new("https://github.com/ggerganov/whisper.cpp")
        )
        
        # yt-dlp link
        ytdlp_link = ttk.Label(
            links_frame, 
            text="yt-dlp", 
            **link_style
        )
        ytdlp_link.pack(anchor=tk.W, pady=2)
        ytdlp_link.bind(
            "<Button-1>", 
            lambda e: webbrowser.open_new("https://github.com/yt-dlp/yt-dlp")
        )
        
        # Version and credits
        version_frame = ttk.Frame(about_frame)
        version_frame.pack(pady=15)
        
        version_label = ttk.Label(version_frame, text="Version 1.1")
        version_label.pack(side=tk.LEFT, padx=5)
        
        # Add a button to check for updates
        update_btn = ttk.Button(
            version_frame, 
            text="Check for Updates",
            command=lambda: webbrowser.open_new("https://github.com/yourusername/YTScript/releases")
        )
        update_btn.pack(side=tk.LEFT, padx=5)
        
        # Credits at the bottom
        credits_frame = ttk.Frame(about_frame)
        credits_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        credits_label = ttk.Label(
            credits_frame, 
            text="© 2025 YTScript Contributors",
            font=("TkDefaultFont", 9),
            foreground="gray"
        )
        credits_label.pack(side=tk.BOTTOM)
    
    def _browse_output_dir(self):
        """Open directory browser dialog and update output directory."""
        directory = filedialog.askdirectory(initialdir=self.output_dir.get())
        if directory:
            self.output_dir.set(directory)
            self._save_last_output_dir(directory)
    
    def _browse_path(self, string_var, filetypes=None):
        """Open file browser dialog and update path variable."""
        if filetypes:
            path = filedialog.askopenfilename(initialdir=os.path.dirname(string_var.get()), filetypes=filetypes)
        else:
            path = filedialog.askdirectory(initialdir=string_var.get())
        
        if path:
            string_var.set(path)
    
    def _paste_url(self):
        """Paste clipboard content to URL field."""
        try:
            clipboard_content = self.clipboard_get()
            if self._is_youtube_url(clipboard_content):
                self.youtube_url.set(clipboard_content)
            else:
                messagebox.showwarning("Not a YouTube URL", "The clipboard content doesn't appear to be a YouTube URL.")
        except tk.TclError:
            messagebox.showwarning("Clipboard Empty", "Clipboard is empty or contains non-text content.")
    
    def _is_youtube_url(self, text):
        """Check if text is a valid YouTube URL."""
        youtube_regex = r"(?:https?://)?(?:www\.)?youtu(?:\.be/|be\.com/(?:watch\?(?:.*&)?v=|embed/|v/|shorts/))([\w\-]+)(?:[?&]t=\d+)?(?:[?&]list=[\w\-]+)?"
        return re.match(youtube_regex, text) is not None
    
    def _save_settings(self):
        """Save settings to config file."""
        config_dir = Path(os.path.expanduser("~/.config/ytscript"))
        config_dir.mkdir(parents=True, exist_ok=True)
        
        config_path = config_dir / "config.json"
        
        config = {
            "whisper_path": self.whisper_path.get(),
            "model_path": self.model_path.get()
        }
        
        try:
            import json
            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)
            
            messagebox.showinfo("Settings Saved", f"Configuration saved to: {config_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {e}")
    
    def _populate_model_list(self):
        """Populate the LLM model combobox."""
        if not SUMMARIZER_AVAILABLE:
            return
        
        try:
            models = get_available_models()
            if models:
                self.model_combo['values'] = [str(model) for model in models]
                self.model_combo.current(0)  # Select first model
            else:
                self.model_combo['values'] = ["No models found"]
        except Exception as e:
            self.model_combo['values'] = [f"Error: {e}"]
    
    def _update_summary_ui(self):
        """Update the UI based on whether summary generation is enabled."""
        if not SUMMARIZER_AVAILABLE:
            return
        
        if self.generate_summary.get():
            self.model_combo.configure(state="readonly")
        else:
            self.model_combo.configure(state="disabled")
    
    def _run_transcription(self):
        """Run the transcription process in a separate thread."""
        if not self.youtube_url.get().strip():
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return
        
        if not self._check_settings():
            return
        
        # Clear console
        self.console.configure(state='normal')
        self.console.delete(1.0, tk.END)
        self.console.configure(state='disabled')
        
        # Start redirection
        self.old_stdout = sys.stdout
        sys.stdout = self.redirect
        self.redirect.update_widget()
        
        # Update UI state
        self.run_btn.configure(state=tk.DISABLED)
        self.cancel_btn.configure(state=tk.NORMAL)
        self.status_var.set("Transcribing...")
        
        # Show progress bar
        self.progress_var.set(0)
        self.progress_bar.pack(side=tk.RIGHT, padx=10)
        
        # Start thread
        self.thread = threading.Thread(target=self._transcription_thread)
        self.thread.daemon = True
        self.thread.start()
    
    def _transcription_thread(self):
        """Run transcription in a background thread."""
        try:
            # Update progress
            self.after(0, lambda: self.progress_var.set(10))
            
            # Create YTScript instance
            transcriber = YTScript(
                whisper_path=self.whisper_path.get(),
                model_path=self.model_path.get(),
                verbose=True
            )
            
            # Update progress
            self.after(0, lambda: self.progress_var.set(20))
            
            # Process video
            txt_path, srt_path = transcriber.process_video(
                youtube_url=self.youtube_url.get().strip(),
                output_dir=self.output_dir.get(),
                generate_srt=self.generate_srt.get(),
                language=self.language.get() if self.language.get() else None,
                keep_audio=self.keep_audio.get()
            )
            
            # Update progress
            self.after(0, lambda: self.progress_var.set(80))
            
            print("\nTranscription complete!")
            print(f"Text transcript saved to: {txt_path}")
            if srt_path:
                print(f"SRT subtitle file saved to: {srt_path}")
            
            # Print preview
            if txt_path and txt_path.exists():
                with open(txt_path, 'r') as f:
                    preview = "".join(f.readlines()[:5])
                    print("\nTranscript preview:")
                    print("-" * 40)
                    print(preview + "...")
                    print("-" * 40)
            
            # Generate summary if requested
            if SUMMARIZER_AVAILABLE and self.generate_summary.get() and self.llm_path.get():
                print("\nGenerating summary...")
                self.after(0, lambda: self.progress_var.set(85))
                
                try:
                    summarizer = LocalSummarizer(
                        model_path=self.llm_path.get(),
                        verbose=True
                    )
                    
                    summary = summarizer.summarize_transcript(txt_path)
                    self.after(0, lambda: self.progress_var.set(95))
                    
                    if not summary.startswith("Error:"):
                        summary_path = summarizer.save_summary(txt_path, summary)
                        print(f"\nSummary saved to: {summary_path}")
                        print("\nSummary preview:")
                        print("-" * 40)
                        print(summary[:500] + ("..." if len(summary) > 500 else ""))
                        print("-" * 40)
                    else:
                        print(f"\nError generating summary: {summary}")
                except Exception as e:
                    print(f"\nError during summarization: {e}")
            
            # Update progress to complete
            self.after(0, lambda: self.progress_var.set(100))
            
            # Update UI on the main thread
            self.after(0, lambda: self._update_ui_after_completion("Transcription completed"))
            
        except Exception as e:
            print(f"\nError: {str(e)}")
            self.after(0, lambda: self._update_ui_after_completion(f"Error: {str(e)}", error=True))
    
    def _update_ui_after_completion(self, status_message, error=False):
        """Update UI after transcription completes."""
        # Restore stdout
        sys.stdout = self.old_stdout
        self.redirect.stop_updates()
        
        # Update UI
        self.run_btn.configure(state=tk.NORMAL)
        self.cancel_btn.configure(state=tk.DISABLED)
        self.status_var.set(status_message)
        
        # Hide progress bar
        self.progress_bar.pack_forget()
        
        # Add to history if successful and not an error
        if not error and self.youtube_url.get().strip():
            self._add_to_history(
                self.youtube_url.get().strip(),
                self.output_dir.get()
            )
            
            # Update history view if it's visible
            if self.notebook.index(self.notebook.select()) == 1:  # History tab
                self._populate_history()
        
        if error:
            messagebox.showerror("Error", status_message)
    
    def _cancel_operation(self):
        """Cancel the current operation."""
        if messagebox.askyesno("Cancel Operation", "Are you sure you want to cancel the current operation?"):
            print("\nCancelling operation...")
            
            # Try to cancel the process if it's running
            if hasattr(self, 'thread') and self.thread.is_alive():
                # This is a hacky way to interrupt the thread
                # In a real app, you would need a proper cancellation mechanism
                self._update_ui_after_completion("Operation cancelled by user")
    
    def _open_output_folder(self):
        """Open the output directory in file explorer."""
        output_dir = self.output_dir.get()
        
        if not os.path.exists(output_dir):
            messagebox.showerror("Error", "Output directory does not exist")
            return
        
        if sys.platform == 'win32':
            os.startfile(output_dir)
        elif sys.platform == 'darwin':  # macOS
            subprocess.run(['open', output_dir])
        else:  # Linux
            subprocess.run(['xdg-open', output_dir])
    
    def _run_setup(self):
        """Run the setup script."""
        if messagebox.askyesno("Run Setup", "This will run the setup script to install dependencies. Continue?"):
            # Clear console
            self.console.configure(state='normal')
            self.console.delete(1.0, tk.END)
            self.console.configure(state='disabled')
            
            # Start redirection
            self.old_stdout = sys.stdout
            sys.stdout = self.redirect
            self.redirect.update_widget()
            
            # Update UI state
            self.run_btn.configure(state=tk.DISABLED)
            self.cancel_btn.configure(state=tk.NORMAL)
            self.status_var.set("Running setup...")
            
            # Start thread
            self.thread = threading.Thread(target=self._setup_thread)
            self.thread.daemon = True
            self.thread.start()
    
    def _setup_thread(self):
        """Run setup in a background thread."""
        try:
            # Get path to setup script
            setup_script = Path(__file__).parent / "setup.py"
            
            # Run setup script
            subprocess.run([sys.executable, str(setup_script)], check=True)
            
            # Reload config
            self.config = load_config()
            
            # Update UI
            self.after(0, lambda: self._after_setup())
            
        except Exception as e:
            print(f"\nError during setup: {e}")
            self.after(0, lambda: self._update_ui_after_completion(f"Setup failed: {str(e)}", error=True))
    
    def _after_setup(self):
        """Actions to perform after setup completes."""
        # Reload paths from config
        self.whisper_path.set(self.config["whisper_path"])
        self.model_path.set(self.config["model_path"])
        
        # Update UI
        self._update_ui_after_completion("Setup completed")
        
        # Repopulate models if available
        if SUMMARIZER_AVAILABLE:
            self._populate_model_list()
    
    def _check_settings(self):
        """Check if required settings are valid."""
        # Check whisper path
        whisper_path = Path(self.whisper_path.get()).expanduser().absolute()
        whisper_executable = whisper_path / "main"
        
        if not whisper_executable.exists():
            messagebox.showwarning(
                "Whisper.cpp Not Found", 
                "The whisper.cpp executable was not found at the specified path.\n\n"
                "Please run the setup script or set the correct path in Settings."
            )
            return False
        
        # Check model path
        model_path = Path(self.model_path.get()).expanduser().absolute()
        
        if not model_path.exists():
            messagebox.showwarning(
                "Whisper Model Not Found", 
                "The Whisper model file was not found at the specified path.\n\n"
                "Please run the setup script or set the correct path in Settings."
            )
            return False
        
        return True
    
    def _get_environment_info(self):
        """Get information about the environment."""
        info = []
        
        # Python version
        info.append(f"Python: {sys.version.split()[0]}")
        
        # OS info
        info.append(f"Platform: {sys.platform}")
        
        # Check for yt-dlp
        try:
            result = subprocess.run(
                ["yt-dlp", "--version"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                text=True
            )
            info.append(f"yt-dlp: {result.stdout.strip() if result.returncode == 0 else 'Not found'}")
        except (FileNotFoundError, subprocess.SubprocessError):
            info.append("yt-dlp: Not found")
        
        # Check for whisper.cpp
        whisper_path = Path(self.whisper_path.get()).expanduser().absolute()
        whisper_executable = whisper_path / "main"
        info.append(f"whisper.cpp: {'Found' if whisper_executable.exists() else 'Not found'}")
        
        # Check for model file
        model_path = Path(self.model_path.get()).expanduser().absolute()
        info.append(f"Whisper model: {'Found' if model_path.exists() else 'Not found'}")
        
        # Check for summarizer
        info.append(f"Summarizer module: {'Available' if SUMMARIZER_AVAILABLE else 'Not available'}")
        
        return "\n".join(info)
    
    def _setup_history_tab(self, parent):
        """Set up the history tab UI elements."""
        # Create frame for the history list
        history_frame = ttk.Frame(parent)
        history_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Add toolbar
        toolbar = ttk.Frame(history_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        refresh_btn = ttk.Button(
            toolbar,
            text="Refresh",
            command=self._refresh_history
        )
        refresh_btn.pack(side=tk.LEFT, padx=2)
        
        clear_history_btn = ttk.Button(
            toolbar,
            text="Clear History",
            command=self._clear_history
        )
        clear_history_btn.pack(side=tk.LEFT, padx=2)
        
        # Create a treeview for the history
        columns = ("date", "url", "output")
        self.history_tree = ttk.Treeview(history_frame, columns=columns, show="headings", selectmode="browse")
        
        # Define column headings
        self.history_tree.heading("date", text="Date")
        self.history_tree.heading("url", text="YouTube URL")
        self.history_tree.heading("output", text="Output Directory")
        
        # Define column widths
        self.history_tree.column("date", width=150)
        self.history_tree.column("url", width=350)
        self.history_tree.column("output", width=350)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(history_frame, orient=tk.VERTICAL, command=self.history_tree.yview)
        self.history_tree.configure(yscroll=scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add right-click menu
        self.history_menu = tk.Menu(self, tearoff=0)
        self.history_menu.add_command(label="Open Output Directory", command=self._open_history_dir)
        self.history_menu.add_command(label="Load URL", command=self._load_history_url)
        self.history_menu.add_command(label="Remove from History", command=self._remove_history_item)
        
        self.history_tree.bind("<Button-3>", self._show_history_menu)
        self.history_tree.bind("<Double-1>", self._load_history_url)
        
        # Action frame for selected history item
        action_frame = ttk.LabelFrame(parent, text="Selected Item Actions", padding="5")
        action_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(
            action_frame,
            text="Open Output Directory",
            command=self._open_history_dir
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            action_frame,
            text="Load URL to Transcribe Tab",
            command=self._load_history_url
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            action_frame,
            text="Remove from History",
            command=self._remove_history_item
        ).pack(side=tk.LEFT, padx=5)
        
        # Populate history
        self._populate_history()
    
    def _populate_history(self):
        """Populate the history treeview with items from the history."""
        # Clear existing items
        for item in self.history_tree.get_children():
            self.history_tree.delete(item)
        
        # Add history items
        for item in self.history:
            self.history_tree.insert(
                "",
                tk.END,
                values=(
                    item.get("date", "Unknown"),
                    item.get("url", "Unknown"),
                    item.get("output_dir", "Unknown")
                )
            )
    
    def _show_history_menu(self, event):
        """Show the context menu for history items."""
        # Get the item under cursor
        item = self.history_tree.identify_row(event.y)
        if item:
            # Select the item
            self.history_tree.selection_set(item)
            # Show the menu
            self.history_menu.post(event.x_root, event.y_root)
    
    def _open_history_dir(self, *args):
        """Open the output directory from the selected history item."""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a history item first.")
            return
        
        item_id = selection[0]
        item_index = self.history_tree.index(item_id)
        
        if 0 <= item_index < len(self.history):
            output_dir = self.history[item_index].get("output_dir")
            
            if output_dir and os.path.exists(output_dir):
                self._open_directory(output_dir)
            else:
                messagebox.showwarning("Directory Not Found", "The output directory no longer exists.")
    
    def _open_directory(self, path):
        """Open a directory in the file explorer."""
        if sys.platform == 'win32':
            os.startfile(path)
        elif sys.platform == 'darwin':  # macOS
            subprocess.run(['open', path])
        else:  # Linux
            subprocess.run(['xdg-open', path])
    
    def _load_history_url(self, *args):
        """Load the URL from the selected history item into the transcribe tab."""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a history item first.")
            return
        
        item_id = selection[0]
        item_index = self.history_tree.index(item_id)
        
        if 0 <= item_index < len(self.history):
            url = self.history[item_index].get("url")
            output_dir = self.history[item_index].get("output_dir")
            
            if url:
                self.youtube_url.set(url)
                
            if output_dir and os.path.exists(output_dir):
                self.output_dir.set(output_dir)
            
            # Switch to the transcribe tab
            self.notebook.select(0)
    
    def _remove_history_item(self, *args):
        """Remove the selected item from history."""
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a history item first.")
            return
        
        item_id = selection[0]
        item_index = self.history_tree.index(item_id)
        
        if 0 <= item_index < len(self.history):
            # Remove from list
            del self.history[item_index]
            
            # Update tree
            self.history_tree.delete(item_id)
            
            # Save updated history
            self._save_history()
    
    def _refresh_history(self):
        """Refresh the history list."""
        self.history = self._load_history()
        self._populate_history()
    
    def _clear_history(self):
        """Clear all history."""
        if messagebox.askyesno("Clear History", "Are you sure you want to clear all history?"):
            self.history = []
            self._save_history()
            self._populate_history()
    
    def _load_theme_preference(self):
        """Load theme preference from config file."""
        config_dir = Path(os.path.expanduser("~/.config/ytscript"))
        theme_file = config_dir / "theme.txt"
        
        if theme_file.exists():
            try:
                with open(theme_file, 'r') as f:
                    theme = f.read().strip()
                    return theme if theme in ["light", "dark"] else "light"
            except Exception:
                return "light"
        
        return "light"
    
    def _save_theme_preference(self, theme):
        """Save theme preference to config file."""
        config_dir = Path(os.path.expanduser("~/.config/ytscript"))
        config_dir.mkdir(parents=True, exist_ok=True)
        
        theme_file = config_dir / "theme.txt"
        
        try:
            with open(theme_file, 'w') as f:
                f.write(theme)
        except Exception:
            pass
    
    def _apply_theme(self, theme_mode):
        """Apply the selected theme."""
        style = ttk.Style()
        
        if theme_mode == "dark":
            # Dark theme
            self.configure(bg="#2d2d2d")
            style.theme_use("clam")
            
            # Configure colors
            style.configure(".", 
                background="#2d2d2d", 
                foreground="#ffffff",
                fieldbackground="#3d3d3d"
            )
            
            # Configure specific elements
            style.configure("TLabel", background="#2d2d2d", foreground="#ffffff")
            style.configure("TFrame", background="#2d2d2d")
            style.configure("TButton", background="#3d3d3d", foreground="#ffffff")
            style.configure("TNotebook", background="#2d2d2d", tabmargins=[2, 5, 2, 0])
            style.configure("TNotebook.Tab", background="#3d3d3d", foreground="#ffffff", padding=[10, 2])
            style.map("TNotebook.Tab", 
                background=[("selected", "#4d4d4d")],
                foreground=[("selected", "#ffffff")]
            )
            
            # Custom styles
            style.configure("Accent.TButton", background="#007bff", foreground="#ffffff")
            
            # Configure console
            self.console.configure(background="#3d3d3d", foreground="#ffffff")
        else:
            # Light theme
            self.configure(bg="#f0f0f0")
            style.theme_use("clam")
            
            # Configure colors
            style.configure(".", 
                background="#f0f0f0", 
                foreground="#000000",
                fieldbackground="#ffffff"
            )
            
            # Configure specific elements
            style.configure("TLabel", background="#f0f0f0", foreground="#000000")
            style.configure("TFrame", background="#f0f0f0")
            style.configure("TButton", background="#e1e1e1", foreground="#000000")
            style.configure("TNotebook", background="#f0f0f0", tabmargins=[2, 5, 2, 0])
            style.configure("TNotebook.Tab", background="#e1e1e1", foreground="#000000", padding=[10, 2])
            style.map("TNotebook.Tab", 
                background=[("selected", "#f8f8f8")],
                foreground=[("selected", "#000000")]
            )
            
            # Custom styles
            style.configure("Accent.TButton", background="#007bff", foreground="#ffffff")
            
            # Configure console
            self.console.configure(background="#f5f5f5", foreground="#000000")
        
        # Save theme preference
        self._save_theme_preference(theme_mode)
    
    def _toggle_theme(self):
        """Toggle between light and dark themes."""
        current_theme = self.theme_mode.get()
        new_theme = "light" if current_theme == "dark" else "dark"
        
        self.theme_mode.set(new_theme)
        self._apply_theme(new_theme)
    
    def _update_font_size(self, event=None):
        """Update the font size for the console."""
        size = self.font_size.get()
        self.console.configure(font=("TkFixedFont", int(size)))
    
    def _handle_drop(self, event):
        """Handle drag and drop of text (URL)."""
        data = event.data
        if self._is_youtube_url(data):
            self.youtube_url.set(data)
            self.notebook.select(0)  # Switch to transcribe tab
        else:
            messagebox.showwarning("Invalid URL", "The dropped text is not a valid YouTube URL.")
    
    def _clear_form(self):
        """Clear all form fields."""
        self.youtube_url.set("")
        self.keep_audio.set(False)
        self.generate_srt.set(False)
        self.language.set("")
        self.generate_summary.set(False)
    
    def _clear_console(self):
        """Clear the console output."""
        self.console.configure(state='normal')
        self.console.delete(1.0, tk.END)
        self.console.configure(state='disabled')
    
    def _copy_console(self):
        """Copy console content to clipboard."""
        text = self.console.get(1.0, tk.END)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_var.set("Console output copied to clipboard")
    
    def _install_desktop_entry(self):
        """Install the desktop entry for the application."""
        try:
            # Get install script path
            install_script = Path(__file__).parent / "install_desktop.py"
            
            if not install_script.exists():
                messagebox.showerror("Error", "Desktop integration script not found.")
                return
            
            # Run the installation script
            result = subprocess.run(
                [sys.executable, str(install_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0:
                messagebox.showinfo("Success", "Desktop entry installed successfully.")
            else:
                messagebox.showerror("Error", f"Failed to install desktop entry:\n{result.stderr}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred: {e}")
    
    def _check_tool_updates(self):
        """Check for updates to external tools."""
        messagebox.showinfo("Check for Updates", "This feature is not yet implemented.")
    
    def _install_dependencies(self):
        """Install missing dependencies."""
        if messagebox.askyesno("Install Dependencies", "This will run the setup script to install missing dependencies. Continue?"):
            self._run_setup()
    
    def _load_last_output_dir(self):
        """Load the last used output directory from config."""
        config_dir = Path(os.path.expanduser("~/.config/ytscript"))
        output_dir_file = config_dir / "last_output.txt"
        
        if output_dir_file.exists():
            try:
                with open(output_dir_file, 'r') as f:
                    dir_path = f.read().strip()
                    if os.path.isdir(dir_path):
                        return dir_path
            except Exception:
                pass
        
        return os.getcwd()
    
    def _save_last_output_dir(self, output_dir):
        """Save the last used output directory to config."""
        config_dir = Path(os.path.expanduser("~/.config/ytscript"))
        config_dir.mkdir(parents=True, exist_ok=True)
        
        output_dir_file = config_dir / "last_output.txt"
        
        try:
            with open(output_dir_file, 'w') as f:
                f.write(output_dir)
        except Exception as e:
            print(f"Error saving last output directory: {e}")
    
    def _setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts for the application."""
        # Main actions
        self.bind("<Control-r>", lambda e: self._run_transcription())
        self.bind("<Control-o>", lambda e: self._browse_output_dir())
        self.bind("<Control-q>", lambda e: self.quit())
        self.bind("<Escape>", lambda e: self._cancel_operation())
        
        # Tab switching
        self.bind("<Control-1>", lambda e: self.notebook.select(0))  # Transcribe tab
        self.bind("<Control-2>", lambda e: self.notebook.select(1))  # History tab
        self.bind("<Control-3>", lambda e: self.notebook.select(2))  # Settings tab
        self.bind("<Control-4>", lambda e: self.notebook.select(3))  # About tab
        
        # Console actions
        self.bind("<Control-l>", lambda e: self._clear_console())
        
        # Add help text to UI elements using tooltips
        self._create_tooltips()
