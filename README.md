# Nanovor DebugLog Viewer

A Python replacement for the Flash-based DebugLog viewer that displays real-time debug logs from the Nanovor client.

## Overview

The Nanovor DebugLog Viewer is a standalone tool that listens on a TCP port for log messages forwarded by the Flash bridge (`DebugLogBridge.swf`). It provides both a GUI and console interface for viewing debug output with filtering and exclusion capabilities.

## Features

- **Real-time log display** - Receive and display debug logs as they arrive
- **GUI interface** - Interactive Tkinter-based interface with filtering controls
- **Console fallback** - Simple console output when Tkinter is not available
- **Text filtering** - Search logs by entering keywords
- **Sender filtering** - Exclude logs from specific senders or keywords
- **Log clearing** - Clear the display or entire log buffer
- **Refiltering** - Dynamically reapply filters to the log history
- **Customizable exclusions** - Set which senders to exclude by default

## Installation

### Requirements

- Python 3.7+
- `tkinter` (optional, for GUI mode)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/thekuhaku/NanovorDebugLog.git
cd NanovorDebugLog
```

2. Ensure Python is installed and the script is executable.

## Usage

### Basic Usage

Start the viewer with default settings:

```bash
python debug_log_viewer.py
```

The tool will listen on `127.0.0.1:8765` by default.

### GUI Mode (Default)

If Tkinter is available, the tool launches with a graphical interface:

- **Filter (text)** - Enter keywords to filter logs
- **Exclude senders** - Comma-separated list of sender substrings to exclude
- **Clear log** - Clear the current display
- **Refilter** - Reapply filters to log history

### Console Mode

If Tkinter is unavailable, logs display in the console:

```bash
python debug_log_viewer.py --port 9000
```

### Command-line Options

```
--port PORT                    TCP listen port (default: 8765)
--no-exclude-download          Do not exclude Downloadovor/Download manager logs by default
--exclude SENDER              Additional sender substring to exclude (can repeat)
```

### Examples

Listen on port 9000 with no default exclusions:

```bash
python debug_log_viewer.py --port 9000 --no-exclude-download
```

Exclude multiple senders:

```bash
python debug_log_viewer.py --exclude "Error" --exclude "Warning"
```

## Workflow

1. **Start the viewer**: `python debug_log_viewer.py [options]`
2. **Run the Flash bridge**: Execute `DebugLogBridge.swf` in your Flash player
3. **Run the game**: Start the Nanovor game with debug logging enabled
4. **View logs**: Watch real-time debug output in the viewer interface

## Configuration

### Default Excluded Senders

By default, the following sender substrings are excluded:
- `download`
- `downloadovor`
- `downloadmanager`

Disable this with `--no-exclude-download`.

### UI Settings (GUI Mode)

- **Max display characters**: 500,000 characters (oldest logs are removed when exceeded)
- **Log buffer**: Stores up to 100,000 lines for refiltering
- **Font**: Consolas, size 10 (in GUI mode)

## Log Message Format

Log messages are formatted as:

```
HH:MM:SS|[TYPE] Message text
```

Where `[TYPE]` can be:
- ` ERROR ` - Error message
- ` COMMENT ` - Comment message
- (empty) - Regular log message

Example:

```
14:23:45| Nanovor 1 started attack
14:23:46| ERROR Combat system error occurred
14:23:47| COMMENT Debug checkpoint reached
```

## Troubleshooting

### "tkinter not available"

The GUI requires Tkinter, which may not be installed on all Python distributions. Install it:

- **Windows**: `python -m pip install tk`
- **Linux (Ubuntu/Debian)**: `sudo apt-get install python3-tk`
- **macOS**: Tkinter is included with the Python installer

If unavailable, the tool automatically falls back to console mode.

### Connection refused

Ensure the Flash bridge (`DebugLogBridge.swf`) is running and attempting to connect to the correct host/port.

### No logs appearing

- Check that the game is actually generating debug output
- Verify the bridge is connecting (check console output)
- Try `--no-exclude-download` to check if logs are being filtered

## Development

The viewer is designed to be easily extensible. Key components:

- `LogServer` - Handles TCP connections and message parsing
- `run_gui()` - GUI implementation with Tkinter
- `run_console()` - Console-only implementation
- Filter functions - `extract_sender()`, `should_exclude()`, `apply_filter_to_line()`

## License

See LICENSE file for details.

## Support

For issues or questions, please open an issue on GitHub.
