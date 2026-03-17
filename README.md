# 🌅 Morning Momentum Bot  v2.0

> **One-time setup, daily delight.** A lightweight Windows bot that monitors a public GitHub repo for motivational images and displays them as picture-in-picture popups the instant they're pushed. **No Python required** — ships as a standalone `.exe`.

---

## 🎯 Problem Statement

| Pain Point | Solution |
|---|---|
| Daily email is **24 MB** per image | Images served from GitHub CDN (no email, no bloat) |
| Easy to **miss the email** | Auto-popup appears on screen + Windows toast notification |
| Manual effort every day | **Set-and-forget** — runs silently in the system tray |
| Needs technical setup | **Just double-click** `setup.bat` — no Python, no installs |

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    SENDER (Colleague: sureshgce)                  │
│                                                                  │
│   GitHub Repo: github.com/sureshgce/morning-motivation           │
│   └── images/                                                    │
│       ├── 10-03-2026.png                                         │
│       ├── 11-03-2026.png                                         │
│       └── 17-03-2026.png   ← pushes new image daily             │
│                                                                  │
│   (drag-and-drop onto sender/push_image.bat)                     │
└──────────────────┬───────────────────────────────────────────────┘
                   │
                   │  GitHub REST API (public, no auth needed)
                   │  GET /repos/sureshgce/morning-motivation/contents/images
                   │  Conditional requests (ETag) → saves rate limits
                   │  Fallback: auto-tries repo root if images/ not found
                   │
┌──────────────────▼───────────────────────────────────────────────┐
│               RECEIVER (Your Windows PC — no Python needed)       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐     │
│  │         Morning Momentum Bot (standalone .exe)           │     │
│  │                                                         │     │
│  │  ┌───────────┐   ┌──────────────┐   ┌──────────────┐   │     │
│  │  │  GitHub    │──▶│  State Mgr   │──▶│  Image       │   │     │
│  │  │  Monitor   │   │ (.bot_state) │   │  Downloader  │   │     │
│  │  │  (poll     │   │  SHA-based   │   │  + local     │   │     │
│  │  │   3 min)   │   │  dedup       │   │    cache     │   │     │
│  │  └───────────┘   └──────────────┘   └──────┬───────┘   │     │
│  │                                            │            │     │
│  │                    ┌───────────────┐ ┌──────▼────────┐  │     │
│  │                    │  Windows      │ │  PiP Popup    │  │     │
│  │                    │  Toast        │ │  (tkinter)    │  │     │
│  │                    │  Notification │ │  • borderless │  │     │
│  │                    └───────────────┘ │  • always-on- │  │     │
│  │                                      │    top        │  │     │
│  │                                      │  • auto-close │  │     │
│  │  ┌───────────┐                       │  • fade anim  │  │     │
│  │  │  System   │  Tray icon:           │  • draggable  │  │     │
│  │  │  Tray ☀   │  Check Now            │  • progress   │  │     │
│  │  │           │  Show Last             │    countdown  │  │     │
│  │  │           │  Quit                 └───────────────┘  │     │
│  │  └───────────┘                                          │     │
│  └─────────────────────────────────────────────────────────┘     │
│                                                                  │
│  Auto-starts via Windows Task Scheduler (registered by setup.bat)│
└──────────────────────────────────────────────────────────────────┘
```

---

## 📂 Project Structure

```
Morning_momentum/
├── README.md                          # This file
├── repo_organize.bat                  # ONE-TIME: reorganize GitHub repo (move images → images/)
│
├── setup/                             # ═══ ALL CODE & BUILD FILES ═══
│   ├── morning_bot.py                 # Source code (v2.0 — exe-aware)
│   ├── morning_bot.spec               # PyInstaller build configuration
│   ├── config.json                    # Bot configuration (pre-filled for sureshgce repo)
│   ├── requirements.txt               # Python deps (build-time only)
│   ├── build_exe.bat                  # Build the standalone .exe (needs Python)
│   ├── setup.bat                      # END USER: one-time setup (NO Python needed)
│   ├── start_bot.bat                  # END USER: manual start
│   ├── stop_bot.bat                   # END USER: manual stop
│   ├── dist/                          # ← Built exe output
│   │   └── morning_bot/
│   │       ├── morning_bot.exe        # ★ Standalone exe (no Python required)
│   │       ├── config.json            # Configuration (edit this)
│   │       ├── images/                # Local image cache (auto-created)
│   │       ├── _internal/             # Bundled Python runtime & libs
│   │       ├── .bot_state.json        # Seen images tracker (auto-created)
│   │       └── morning_bot.log        # Log file (auto-created)
│   ├── build/                         # Build temp (auto-created)
│   └── venv/                          # Build venv (auto-created)
│
├── sender/                            # ═══ FOR YOUR COLLEAGUE ═══
│   └── push_image.bat                 # Drag-and-drop image to push to GitHub
│
├── images/                            # Shared image folder reference
└── email.pdf                          # Original email reference
```

---

## ⚡ Quick Start

### For the End User (NO Python required!)

**Step 1** — Double-click **`setup\setup.bat`**

That's it! The bot:
- Registers itself to auto-start at every Windows logon
- Starts running immediately in the system tray (☀ icon)
- Polls `github.com/sureshgce/morning-motivation` every 3 minutes
- Shows a PiP popup when a new image is pushed

### For Building the EXE (one-time, needs Python)

Only needed if you want to rebuild the exe from source:

```
setup\build_exe.bat
```

This creates `setup\dist\morning_bot\morning_bot.exe` — a fully standalone Windows application.

### For Reorganizing the GitHub Repo

If your colleague's images are at the repo root (not in `images/` folder):

```
repo_organize.bat
```

This clones the repo, moves all images into `images/`, commits and pushes. Run once from a machine with Git installed.

---

## ⚙️ Configuration Reference

Edit **`setup\dist\morning_bot\config.json`** (next to the exe):

| Key | Default | Description |
|---|---|---|
| `github.owner` | `sureshgce` | GitHub username of the repo owner |
| `github.repo` | `morning-motivation` | Repository name |
| `github.branch` | `main` | Branch to monitor |
| `github.image_path` | `images` | Folder inside repo (auto-fallback to root) |
| `github.token` | `""` | Optional GitHub PAT (raises rate limit 60→5000/hr) |
| `polling.interval_seconds` | `180` | Check interval in seconds |
| `polling.active_hours.start` | `06:00` | Don't poll before this time |
| `polling.active_hours.end` | `22:00` | Don't poll after this time |
| `popup.max_width` | `600` | Maximum popup width in pixels |
| `popup.max_height` | `500` | Maximum popup height in pixels |
| `popup.display_seconds` | `30` | Auto-dismiss after N seconds |
| `popup.opacity` | `0.95` | Window opacity (0.0 – 1.0) |
| `popup.position` | `bottom-right` | `bottom-right`, `bottom-left`, `top-right`, `top-left`, `center` |
| `storage.image_cache_dir` | `images` | Local cache directory |
| `storage.max_cache_days` | `30` | Auto-purge images older than N days |

---

## 🖥️ For the Sender (Your Colleague)

The repo at [github.com/sureshgce/morning-motivation](https://github.com/sureshgce/morning-motivation) should have images in the `images/` folder:

```
morning-motivation/          ← GitHub repo
└── images/
    ├── 10-03-2026.png
    ├── 11-03-2026.png
    ├── 12-03-2026.png
    └── 17-03-2026.png       ← push new image daily
```

A helper **`sender/push_image.bat`** is provided — drag-and-drop an image onto it to auto-commit and push.

### Supported Image Formats
`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.tif`, `.tiff`, `.svg`, `.ico`, `.heic`, `.heif`, `.avif`, `.jfif`

---

## 🔧 Manual Controls

| Action | How |
|---|---|
| Start bot | Double-click `setup\start_bot.bat` |
| Stop bot | Double-click `setup\stop_bot.bat` |
| Check now | Right-click tray ☀ icon → **Check Now** |
| Show last image | Right-click tray ☀ icon → **Show Last Image** |
| View logs | Open `setup\dist\morning_bot\morning_bot.log` |

---

## 🛡️ Production Qualities

- **No Python required** — standalone exe with bundled runtime
- **Smart fallback** — if `images/` folder not found, auto-checks repo root
- **Date-aware titles** — parses `DD-MM-YYYY` filenames for popup title bar
- **Single-instance lock** — PID file prevents duplicate bots
- **ETag caching** — conditional HTTP requests save GitHub rate limits
- **Graceful shutdown** — signal handlers clean up on exit
- **Active hours** — no polling during sleep hours (configurable)
- **Auto-cleanup** — old cached images purged automatically
- **Retry with backoff** — network failures handled gracefully (3 retries)
- **Dual logging** — rolling file log + console (dev mode)
- **Windows toast** — bonus native notification alongside PiP popup
- **Zero-config auto-start** — Windows Task Scheduler integration
- **Error popups** — friendly dialogs for config issues (not silent crashes)

---

## 📋 Dependencies (build-time only)

| Package | Purpose |
|---|---|
| `requests` | GitHub API communication |
| `Pillow` | Image loading, resizing, tray icon generation |
| `pystray` | Windows system tray icon |
| `pyinstaller` | Build standalone exe |

**End users need ZERO dependencies** — everything is bundled in the exe.
