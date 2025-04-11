# 🎬 TransLateVid-DL-AI: SubGen

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/AI--Powered-Subtitles-orange.svg" alt="AI-Powered">
  <img src="https://img.shields.io/badge/AI--Powered-Translation-orange.svg" alt="AI-Powered">
</p>

> TransLateVid-DL-AI: SubGen is an advanced application for downloading, processing, and translating videos and their subtitles.

## ✨ Features

- 📥 **Video downloads** from various platforms
- 🔊 **Audio track extraction** and separation (voice and music) 
- 🗣️ **Automatic speech recognition** with state-of-the-art accuracy
- 🌐 **Subtitle translation** into numerous languages
- 🖥️ **Intuitive graphical interface** for easy operation

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/TheExtreMeLeGend/TransLateVid-DL-AI-SubGen.git
cd TransLateVid-DL-AI-SubGen

# Make sure you're using Python 3.10
# You can check your Python version with:
python --version

# Create and activate a virtual environment (recommended)
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# For GPU support (recommended for faster processing)
pip install torch==2.5.1+cu121 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Running the Application

```bash
python app.py
```

## 🔍 How It Works

TransLateVid-DL-AI: SubGen processes videos through several sophisticated stages:

### 1️⃣ Video Acquisition

- **From URL**: The software uses yt-dlp to download videos from YouTube and other platforms
- **From local file**: Directly processes video files from your computer
- Handles various formats and resolutions automatically

### 2️⃣ Audio Extraction

- FFmpeg extracts the audio track from the video
- Audio is converted to a suitable format for processing (WAV, 44.1kHz)
- High-quality conversion preserves audio details for better transcription

### 3️⃣ Audio Source Separation

- **Demucs** (Facebook's audio source separation model) splits the audio into:
  - 🎤 Vocals (human speech)
  - 🎵 Accompaniment (background music)
  - 🥁 Drums
  - 🎸 Bass
- This separation allows for cleaner transcription by isolating the speech

### 4️⃣ Speech Recognition & Transcription

- The isolated vocal track is processed by OpenAI's Whisper model
- Whisper performs automatic speech recognition (ASR)
- The model identifies spoken words and their timestamps
- Multiple languages are automatically detected and transcribed

### 5️⃣ Subtitle Generation

- Transcribed text with timestamps is formatted into SRT subtitle format
- Each subtitle entry includes a sequence number, timestamp, and text
- Line length and duration are optimized for readability

### 6️⃣ Translation (Optional)

- Original subtitles can be translated to numerous target languages
- Translation options include:
  - OpenAI models for context-aware, high-quality translation (currently the only fully functional option)
  - DeepL API for specialized translation (planned for future updates)
  - O3-mini for efficient, cost-effective translation
- Translation maintains proper subtitle formatting and timing

### 7️⃣ Output Files

- The software generates multiple output files:
  - Original extracted audio (.mp3)
  - Separated vocal and instrumental tracks (.wav)
  - Original language subtitles (.srt)
  - Translated subtitles (if requested) (.srt)
- All files are saved in an organized folder structure for easy access

## 💻 System Requirements

### Minimum Requirements (CPU Only)
- **CPU**: Intel i5/AMD Ryzen 5 or equivalent (4 cores recommended)
- **RAM**: 8GB minimum, 16GB recommended
- **Storage**: 10GB free space for application and temporary files
- Processing time will be significantly longer with CPU-only processing

### Recommended Requirements (With GPU)
- **GPU**: NVIDIA graphics card with CUDA support (GTX 1060 6GB or better)
- **CUDA Toolkit**: 11.6 or newer
- **cuDNN**: Compatible with your CUDA version
- **RAM**: 16GB or more
- **Storage**: 20GB+ free space for application, models, and processed files

> **Note**: GPU acceleration significantly improves performance for audio separation (Demucs) and speech recognition (Whisper), reducing processing time by up to 10x compared to CPU-only operation.

## 🔧 Prerequisites

- Python 3.10 (specifically recommended, other versions may not be fully compatible)
- FFmpeg (for video processing)
- Internet connection (for downloading and using APIs)
- API keys for translation services (OpenAI and/or DeepL)

## 📋 Detailed Installation Guide

### 1. Setting Up a Virtual Environment (Recommended)

Using a virtual environment is highly recommended to avoid conflicts with other Python packages. Make sure you're using Python 3.10 as this is the version the application is designed for.

#### Windows
```bash
# Check your Python version
python --version  # Should show Python 3.10.x

# Navigate to your project directory
cd path\to\project

# Create a virtual environment with Python 3.10
python -m venv venv

# Activate the virtual environment
venv\Scripts\activate
```

#### macOS/Linux
```bash
# Check your Python version
python3 --version  # Should show Python 3.10.x

# Navigate to your project directory
cd path/to/project

# Create a virtual environment with Python 3.10
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate
```

If you don't have Python 3.10 installed, you'll need to install it first. On Windows, you can download it from the [official Python website](https://www.python.org/downloads/). On macOS/Linux, you can use a version manager like pyenv to install specific Python versions.

### 2. Installing FFmpeg

FFmpeg is necessary for processing videos and audio files.

#### Windows
1. Download FFmpeg from [the official website](https://ffmpeg.org/download.html) or [GitHub](https://github.com/BtbN/FFmpeg-Builds/releases)
2. Extract the contents to a folder on your computer (e.g., C:\ffmpeg)
3. Add the bin folder path (e.g., C:\ffmpeg\bin) to your PATH environment variable
4. Verify the installation by opening a command prompt and typing `ffmpeg -version`

#### macOS
```bash
brew install ffmpeg
```

#### Linux
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# Fedora
sudo dnf install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```

### 2. Installing Python Dependencies

If you prefer to install dependencies manually, here are the main required libraries:

```bash
pip install torch                 # PyTorch for deep learning
pip install whisper_timestamped   # Enhanced version of OpenAI's Whisper with timestamp support
pip install openai                # OpenAI API client for GPT models
pip install yt-dlp                # YouTube video downloader, fork of youtube-dl
pip install pydub                 # Audio processing library
pip install soundfile             # Reading and writing sound files
pip install librosa               # Music and audio analysis
pip install emoji                 # Emoji support for text processing
pip install requests              # HTTP library for API requests
pip install transformers          # Hugging Face Transformers for NLP models
pip install demucs                # Audio source separation (vocals/instruments)
pip install numpy                 # Scientific computing
pip install pathlib               # Object-oriented filesystem paths
pip install unicodedata2          # Unicode character database
```

### 3. API Key Configuration

Create an `api_keys.json` file at the root of the project with the following structure:

```json
{
  "openai": "your-openai-api-key"
}
```

> **Note**: While the code includes support for DeepL API, this functionality is not yet fully implemented. Currently, only the OpenAI API is required for full functionality.

Alternatively, you can set the OpenAI API key as an environment variable:

```bash
# Windows
set OPENAI_API_KEY=your-openai-api-key

# Linux/macOS
export OPENAI_API_KEY=your-openai-api-key
```

## 📝 User Guide

### Downloading and Processing Videos

1. Launch the application with `python app.py`
2. In the main interface, you have two options:
   - **URL Video**: Enter the URL of a video to download and process
   - **Select Video File**: Select a local video file to process
3. Click "Process Video" to start processing
4. The application will display progress for each stage:
   - Downloading (progress bar shows download completion)
   - Audio extraction (processing the audio track)
   - Audio separation (splitting vocals from music - this step is CPU/GPU intensive)
   - Transcription (converting speech to text - also CPU/GPU intensive)
   - Subtitle generation (formatting the transcription with proper timestamps)
5. When complete, you'll be notified and can find the output files in the specified output directory

### Translating Subtitles

#### Using the Integrated Translation Tool

1. Once the video is processed, you can translate the generated subtitles
2. Click on "Translate Subtitles"
3. Select the SRT file to translate
4. Choose the target language from the dropdown menu
5. Select the translation service (currently only OpenAI/ChatGPT is fully functional)
6. Click "Start Translation"

> **Note**: While the application includes integration with DeepL API, this feature is not yet fully functional. Currently, only the OpenAI/ChatGPT translation option is working reliably. DeepL integration will be available in a future update.

#### Using the Dedicated SRT Translator Tool

You can also use the independent SRT Translator tool:

1. Launch `python srt_translator.py`
2. Select the target language from the dropdown menu
3. Click "Select SRT File" and choose the file to translate
4. Wait for the translation to complete
5. The translated file will be saved in the same folder as the original file

## ⚙️ Advanced Configuration

### GPU vs CPU Usage

You can control whether the application uses GPU or CPU for processing:

```python
# In config.json
{
  "audio": {
    "sample_rate": 44100,
    "channels": 2,
    "format": "wav"
  },
  "whisper": {
    "model": "medium",
    "language": "auto",
    "device": "cuda"  // Use "cuda" for GPU or "cpu" for CPU
  },
  "demucs": {
    "use_gpu": true  // Set to false to force CPU processing
  }
}
```

For systems without a compatible GPU, the application will automatically fall back to CPU processing. Note that processing times will be significantly longer without GPU acceleration.

### Memory Usage Optimization

If you're experiencing memory issues on systems with limited RAM:

1. Use smaller Whisper models ("tiny" or "base" instead of "medium")
2. Process shorter video segments (5-10 minutes) at a time
3. Close other memory-intensive applications while running processing
4. Add the following to your configuration:
   ```json
   "memory_optimization": {
     "enable": true,
     "max_segments_in_memory": 100
   }
   ```

### Audio Quality Parameters

You can adjust audio quality parameters by modifying the `config.json` file:

```json
{
  "audio": {
    "sample_rate": 44100,
    "channels": 2,
    "format": "wav"
  },
  "whisper": {
    "model": "medium",
    "language": "auto"
  }
}
```

### Transcription Models

The application lets you choose your preferred Whisper model directly from the user interface. Each model offers different trade-offs between speed, accuracy, and resource usage:

| Model | Size | Memory Required | Processing Speed | Accuracy | Use Case |
|-------|------|-----------------|------------------|----------|----------|
| tiny  | 75MB | ~1GB RAM       | Very Fast        | Limited  | Quick drafts, short content |
| base  | 142MB| ~1GB RAM       | Fast             | Moderate | General purpose, when speed matters |
| small | 466MB| ~2GB RAM       | Moderate         | Good     | Balanced option for most videos |
| medium| 1.5GB| ~5GB RAM       | Slower           | Very Good| Higher quality transcriptions (default) |
| large | 3GB  | ~10GB RAM      | Slowest          | Excellent| When maximum accuracy is required |

The model selection is saved between sessions, so you only need to change it when your requirements change. For systems with limited resources, using a smaller model can significantly improve performance.

## 🔍 Troubleshooting Common Issues

### Python Version Issues

This application is specifically designed for Python 3.10. If you encounter compatibility issues:
1. Verify your Python version with `python --version`
2. If you don't have Python 3.10, install it from the [official Python website](https://www.python.org/downloads/release/python-3100/)
3. Create a new virtual environment with Python 3.10:
   ```bash
   # Windows
   path\to\python310\python.exe -m venv venv
   # macOS/Linux
   /path/to/python3.10 -m venv venv
   ```
4. Some dependencies may have very specific version requirements that work best with Python 3.10

### Missing FFmpeg Error

If you encounter an error indicating that FFmpeg is not installed:
1. Verify that FFmpeg is correctly installed (`ffmpeg -version`)
2. Make sure FFmpeg is in your system PATH
3. Try to explicitly specify the path to FFmpeg in the application

### Errors Related to Special Characters

If you encounter problems with files containing special characters:
1. Use simple filenames without accented or non-Latin characters
2. If the problem persists, try processing files using the "Select Video File" option rather than the URL

### Download Errors

If the download fails:
1. Check your internet connection
2. Make sure the video is accessible in your region
3. Try with another URL or platform

### API Errors

If you encounter API-related errors:
1. Verify that your API keys are correctly configured
2. Make sure you have sufficient credits on your API account
3. Check the request limits of the API you are using

## 🙏 Acknowledgements and Third-Party Libraries

This project would not be possible without the incredible work of the open-source community. We'd like to thank the developers of the following libraries:

- **[FFmpeg](https://ffmpeg.org/)** - For powerful video and audio processing capabilities
- **[OpenAI Whisper](https://github.com/openai/whisper)** - For state-of-the-art speech recognition
- **[Whisper Timestamped](https://github.com/linto-ai/whisper-timestamped)** - For accurate subtitle timestamping
- **[Demucs](https://github.com/facebookresearch/demucs)** - For high-quality audio source separation (Meta Research)
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** - For robust video downloading from various platforms
- **[PyDub](https://github.com/jiaaro/pydub)** - For audio processing and manipulation
- **[SoundFile](https://github.com/bastibe/python-soundfile)** - For reading and writing audio files
- **[Librosa](https://librosa.org/)** - For audio analysis
- **[Transformers](https://github.com/huggingface/transformers)** - For accessing Hugging Face models
- **[Emoji](https://github.com/carpedm20/emoji/)** - For emoji processing in text
- **[NumPy](https://numpy.org/)** - For scientific computing
- **[OpenAI API](https://openai.com/blog/openai-api)** - For powerful AI-driven translation
- **[DeepL API](https://www.deepl.com/pro-api)** - For high-quality language translation

We're standing on the shoulders of giants, and we are immensely grateful for their contributions to the field.

## 🤝 Contribution

Contributions are welcome! Feel free to open an issue or submit a pull request.

## 📄 License

This project is distributed under the MIT license. See the LICENSE file for more details.

## 📬 Contact & Support

For any questions or support, please contact [nmlegendthb@outlook.fr]


### 🧵 Multithreaded Operations for Performance

This application uses **multithreading** to optimize some operations:

- 🔊 **Audio source separation** (Demucs): the process can be run in a separate thread to avoid blocking the main process.
- 🌍 **Subtitle translation**: segments may be translated in parallel using threads for better performance.

> ⚠️ Multithreading is **not used for the transcription process** to ensure controlled and stable execution.

You can disable threading globally from the configuration if needed for stricter sequential control.


### Support the Project

If you find this tool helpful, consider supporting its development:

<p align="center">
  <a href="https://www.paypal.com/donate/?hosted_button_id=YOUR_BUTTON_ID">
    <img src="https://www.paypalobjects.com/en_US/i/btn/btn_donate_LG.gif" alt="Donate with PayPal">
  </a>
</p>

You can make a donation via PayPal to: **nmlegendthb@outlook.fr**

Your support helps maintain this project and develop new features!
