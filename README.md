# LocalDrop

Share files between your phone and your computer over Wi-Fi, in both directions.

You run one small program on your computer. Your phone opens a web page served by it. There is nothing to install on the phone, no cloud account, and your files never leave your home network.

## Features

- **Desktop window** (`gui.py`): start and stop sharing with a button, see the QR code, pick the folder, set a PIN and manage files, no terminal needed
- **Scan a QR code to connect**: no typing addresses on your phone
- Phone to computer, and computer to phone, from the same page
- Multiple files at once, with progress bars
- Drag and drop on the computer, tap to pick files on the phone
- No file size limit, and large files are streamed to disk rather than held in memory
- Optional PIN so only people you tell can use it
- Works on iPhone, Android, Windows, macOS and Linux
- No packages to install: only Python's standard library is used

## Requirements

- Python 3.7 or newer on your computer (check with `python3 --version`)
- For the desktop window only: **tkinter**, which comes with Python on Windows and macOS. On Linux install it with `sudo apt install python3-tk` (Ubuntu/Debian) or `sudo dnf install python3-tkinter` (Fedora). The command-line version does not need it.
- Your phone and computer on the **same Wi-Fi network**

Keep `gui.py` and `share.py` in the same folder.

## Quick start (desktop window)

1. Run:

   ```bash
   python3 gui.py
   ```

   On Windows you can usually double-click `gui.py`, or run `python gui.py` / `py gui.py`.

2. Click **Start sharing**. A QR code appears in the window.
3. Scan it with your phone's camera and tap the link. The share opens in your phone's browser, already unlocked if a PIN is set.
4. Send files from your phone with the page's upload box. They show up in the window's file list.
5. To send files to your phone, click **Add files…** in the window, then download them on the phone page.

In the window you can:

| Control | What it does |
| --- | --- |
| Start / Stop sharing | Turns the share on or off (settings are locked while it runs) |
| QR code and address | Scan it, or click **Copy** and send the address another way |
| Folder / Browse… | Where shared files are stored (default `~/LocalDrop`) |
| Port | Change it if the default 8000 is taken |
| Require PIN | On by default with a random 4-digit PIN each time you open the app; you can type your own |
| Add files… | Copy files into the share so your phone can download them |
| Open folder | Show the shared folder in your file manager |
| Delete selected | Remove files from the share (also press the Delete key) |
| Activity | Live log of what your phone is doing |

The folder and port are remembered between runs. The PIN is not saved.

## Quick start (command line)

1. Open a terminal in this folder.
2. Start the server:

   ```bash
   python3 share.py
   ```

   On Windows you may need `python share.py` or `py share.py`.

3. The terminal prints a **QR code** (and the addresses in text), for example:

   ```
   On this computer:   http://localhost:8000
   On your phone:      http://192.168.1.25:8000

   Scan with your phone's camera:
   (QR code appears here)
   ```

4. Point your phone's **camera app** at the QR code and tap the link that pops up. The share opens in your phone's browser. If you set a PIN, the QR code logs you in automatically.
5. Upload files from either device. Every device on the page sees the same list and can download or delete files.

You can also open `http://localhost:8000` on the computer. The page shows the same QR code at the top (under "Connect your phone"), which is handy if the terminal is hard to read.

No QR scanner? Type the "On your phone" address into your phone's browser instead.

Press `Ctrl+C` in the terminal to stop sharing.

## Options

| Option | Description | Default |
| --- | --- | --- |
| `--port 9000` | Use a different port | `8000` |
| `--dir ~/Shared` | Folder where files are stored | `./shared` |
| `--pin 1234` | Require a PIN before anything can be seen or downloaded | none |
| `--no-qr` | Don't print the QR code in the terminal | off |

Example:

```bash
python3 share.py --port 9000 --dir ~/Desktop/Transfer --pin 4821
```

## Where files go

With the desktop window, files live in the folder shown in the window (default `~/LocalDrop`). With the command line, uploads from your phone are saved in the `shared` folder next to `share.py` (or the folder you chose with `--dir`). To send a file from your computer to your phone, drop it into that folder or upload it through the web page on the computer, then download it on the phone.

If a file with the same name already exists, the new one is saved as `name (1).ext` so nothing is overwritten.

## Tips

- **Save to the phone's gallery:** on iPhone, after downloading a photo or video, open it from the Files app and use Share, then Save Image or Save Video. On Android, downloads land in the Downloads folder.
- **Bookmark it:** add the phone address to your home screen so it is one tap next time. The address can change if your router assigns a new IP, so check the terminal if it stops working.
- **Use the PIN** whenever you are on a network with other people, such as an office or cafe.

## Troubleshooting

**"tkinter is not installed" when running `gui.py`**
Install it as described under Requirements. Until then, `python3 share.py` works without it.

**The QR code looks garbled or won't scan**
- Make the terminal window larger, or zoom out so the whole code fits without wrapping.
- Use a terminal that supports colors and Unicode (Windows Terminal, macOS Terminal, iTerm2, most Linux terminals). The old Windows `cmd.exe` window may not draw it correctly.
- Easiest fix: open `http://localhost:8000` on the computer and scan the QR code shown on that page.

**The phone cannot open the page**
- Confirm both devices are on the same Wi-Fi. Guest networks and some public Wi-Fi isolate devices from each other.
- Turn off any VPN on either device.
- Your computer's firewall may be blocking incoming connections. Allow Python through the firewall when prompted (Windows Defender Firewall or macOS System Settings > Network > Firewall).
- Try a different port with `--port 9000`.

**"Could not start on port 8000"**
Another program is using that port. Pick another with `--port`.

**The printed address is wrong (for example `127.0.0.1`)**
Detection failed, usually because you are not connected to a network. Find your computer's IP address in its network settings and use `http://<that-ip>:8000` on your phone.

## Security notes

LocalDrop is designed for a trusted home or private network.

- Traffic is plain HTTP, not encrypted. The PIN is a basic barrier, not strong security.
- With `--pin`, the PIN is built into the QR code so scanning logs you in. Anyone who can see your screen can scan it, so don't show the QR code to people you don't want to share with.
- Anyone on the same network who knows the address (and PIN, if set) can upload, download and delete files in the shared folder.
- Do not expose the port to the internet, for example through port forwarding.
- Stop the program when you are finished.

## How it works

`gui.py` is a tkinter window that starts and stops the server from `share.py` on a background thread and draws the QR code itself. `share.py` runs a small HTTP server using Python's `http.server`. The web page is built into the script, and so is a small QR code generator, which is why no packages are needed. Uploads send the raw file body with the filename in a header, which lets the server stream it straight to disk. Filenames are sanitized so uploads cannot write outside the shared folder.

## License

Free to use and modify however you like.
