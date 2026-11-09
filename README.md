# LocalDrop

Share files between your phone and your computer over Wi-Fi, in both directions.

You run one small program on your computer. Your phone opens a web page served by it. There is nothing to install on the phone, no cloud account, and your files never leave your home network.

## Features

- Phone to computer, and computer to phone, from the same page
- Multiple files at once, with progress bars
- Drag and drop on the computer, tap to pick files on the phone
- No file size limit, and large files are streamed to disk rather than held in memory
- Optional PIN so only people you tell can use it
- Works on iPhone, Android, Windows, macOS and Linux
- No dependencies: a single Python file using only the standard library

## Requirements

- Python 3.7 or newer on your computer (check with `python3 --version`)
- Your phone and computer on the **same Wi-Fi network**

## Quick start

1. Open a terminal in this folder.
2. Start the server:

   ```bash
   python3 share.py
   ```

   On Windows you may need `python share.py` or `py share.py`.

3. The terminal prints two addresses, for example:

   ```
   On this computer:   http://localhost:8000
   On your phone:      http://192.168.1.25:8000
   ```

4. Type the **phone address** into your phone's browser.
5. Upload files from either device. Every device on the page sees the same list and can download or delete files.

Press `Ctrl+C` in the terminal to stop sharing.

## Options

| Option | Description | Default |
| --- | --- | --- |
| `--port 9000` | Use a different port | `8000` |
| `--dir ~/Shared` | Folder where files are stored | `./shared` |
| `--pin 1234` | Require a PIN before anything can be seen or downloaded | none |

Example:

```bash
python3 share.py --port 9000 --dir ~/Desktop/Transfer --pin 4821
```

## Where files go

Uploads from your phone are saved in the `shared` folder next to `share.py` (or the folder you chose with `--dir`). To send a file from your computer to your phone, drop it into that folder or upload it through the web page on the computer, then download it on the phone.

If a file with the same name already exists, the new one is saved as `name (1).ext` so nothing is overwritten.

## Tips

- **Save to the phone's gallery:** on iPhone, after downloading a photo or video, open it from the Files app and use Share, then Save Image or Save Video. On Android, downloads land in the Downloads folder.
- **Bookmark it:** add the phone address to your home screen so it is one tap next time. The address can change if your router assigns a new IP, so check the terminal if it stops working.
- **Use the PIN** whenever you are on a network with other people, such as an office or cafe.

## Troubleshooting

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
- Anyone on the same network who knows the address (and PIN, if set) can upload, download and delete files in the shared folder.
- Do not expose the port to the internet, for example through port forwarding.
- Stop the program when you are finished.

## How it works

`share.py` runs a small HTTP server using Python's `http.server`. The web page is built into the script. Uploads send the raw file body with the filename in a header, which lets the server stream it straight to disk. Filenames are sanitized so uploads cannot write outside the shared folder.

## License

Free to use and modify however you like.
