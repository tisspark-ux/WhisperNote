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

## Language rule

Always respond to the user in Korean only. Do not use English in user-facing responses.

Python console print messages (startup progress, status output) must be written in Korean.
Exception: .bat files must remain ASCII-only (English), per the absolute rule above.

Plan files (plan mode) must also be written in Korean.

## 수정 전 계획 공유 규칙

**간단한 수정을 제외하고, 소스 코드를 수정하기 전에 반드시 계획을 사용자에게 먼저 보여줄 것.**

- 어떤 파일을 왜 수정하는지 명확히 설명
- 예상 영향도 및 변경 범위 포함
- 사용자 승인 후에만 실제 코드 수정 진행
- 간단한 수정(오타, 주석, 1줄 이내 명백한 수정 등)은 계획 생략 가능

## 수정 후 영향도 체크 및 커밋 규칙

모든 수정 작업은 아래 순서를 반드시 따를 것:

1. **영향도 체크**: 수정한 파일과 연관된 전체 파일을 확인하여 사이드 이펙트 여부 점검.
   - 함수 시그니처 변경 → 호출하는 모든 곳 수정
   - 클래스/모듈 변경 → 임포트하는 모든 파일 확인
   - UI 컴포넌트 추가/변경 → 이벤트 연결(inputs/outputs) 일치 여부 확인

2. **코드 점검**: 커밋 전 수정된 파일을 다시 읽어 논리 오류, 누락된 연결, 타입 불일치 등 검토.

3. **커밋**: 점검 후 문제가 없을 때만 커밋할 것. 발견된 문제는 먼저 수정 후 커밋.

## Versioning rules

Use semantic versioning: MAJOR.MINOR.PATCH

- PATCH (0.x.y → 0.x.y+1): bug fix, patch tweak, no new user-visible feature
- MINOR (0.x.0 → 0.x+1.0): new feature, new UI element, new dependency
- MAJOR (x.0.0): architectural overhaul or breaking change

On every change, BOTH of these must be updated together:
1. `version.py` — set `__version__ = "X.Y.Z"`
2. `version.py` — add entry to `CHANGELOG` at the top (newest first)

Version is displayed in:
- UI header badge: `gr.HTML(f"...<span>v{__version__}</span>...")` in app.py
- Console on startup: `print(f"WhisperNote v{__version__}")` in app.py

Commit message convention:
- `feat: <description>` — new feature (MINOR bump)
- `fix: <description>` — bug fix (PATCH bump)
- `chore: <description>` — tooling, docs, no functional change (PATCH bump)
