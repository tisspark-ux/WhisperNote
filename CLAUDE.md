# WhisperNote — Development Rules

## ABSOLUTE RULE: .bat files must be ASCII-only

**NEVER put any non-ASCII character in .bat or .cmd files.**
This includes:
- Korean/CJK characters
- Em dash (—), en dash (–), curly quotes (" " ' ')
- Any character outside the 0x00–0x7F range

Korean Windows reads batch files as CP949. UTF-8 multi-byte sequences
are misinterpreted as CP949, causing the file to crash immediately or
produce garbage commands.

Allowed in .bat files: a-z A-Z 0-9 and standard ASCII punctuation only.
Use English `rem` for all comments. Never use `::` with special characters.

Violations that already burned us:
- Korean comments in run.bat  → 't' 'l' 've' 'radio' 'ium' command errors
- <-loopback> in run.bat      → < > treated as redirect operators
- Em dash (—) in install.bat  → immediate crash on startup

## Rule: All logic goes in Python, not bat files

Batch files are runners only. Any conditional logic, registry edits,
proxy config, version detection, etc. must go in Python (app.py or helpers).

## Key files

| File | Purpose |
|---|---|
| app.py | Main entry: all proxy/SSL/Gradio patches at top, then UI |
| version.py | __version__ + CHANGELOG — bump on every change |
| transcriber.py | WhisperX transcription + load_audio patch (PyAV) |
| diarizer.py | resemblyzer + SpectralClustering speaker diarization |
| summarizer.py | Ollama HTTP summarization |
| recorder.py | sounddevice microphone/loopback recording |
| config.py | All user-configurable settings |

## Known patches in app.py (do not remove)

1. no_proxy env vars — corporate proxy bypass for Python process
2. winreg ProxyOverride — corporate proxy bypass for browser (Windows)
3. requests SSL verify=False + proxies=None for localhost
4. gradio.networking.url_ok patch — corporate proxy blocks localhost
5. gradio_client.utils patches — Gradio 4.x boolean schema TypeError
   - _json_schema_to_python_type, get_type, get_desc all patched

## Dependency pins (do not loosen without testing)

- pyannote.audio==3.4.0 (4.x breaks whisperx)
- starlette>=0.37.2,<0.40.0 (0.40+ TemplateResponse API change breaks Gradio 4.x)
- gradio>=4.44.1,<5.0.0
