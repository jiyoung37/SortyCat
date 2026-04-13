import os
import re
import sys
import struct
from pathlib import Path
from datetime import datetime, timezone, timedelta

try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
except ImportError:
    print("Tkinter is required to run this application.")
    sys.exit(1)

try:
    from PIL import Image
except ImportError:
    print("Pillow is required. Install with: pip install pillow pillow-heif mutagen tkinterdnd2")
    sys.exit(1)

# HEIC support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# Optional drag & drop support
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False
    TkinterDnD = None
    DND_FILES = None

# Optional MP4/MOV metadata support
try:
    from mutagen.mp4 import MP4
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

SUPPORTED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.heic', '.heif', '.tiff', '.tif', '.webp',
    '.mov', '.mp4', '.m4v'
}
VIDEO_EXTENSIONS = {'.mov', '.mp4', '.m4v'}
DATE_PATTERN = re.compile(r'^(\d{8}_\d{6}|\d{4}-\d{2}-\d{2})')
FILENAME_DATE_EXTRACT = re.compile(r'^(\d{4})(\d{2})(\d{2})_')
QT_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)


def _qt_seconds_to_datetime(seconds: int) -> datetime:
    utc_dt = QT_EPOCH + timedelta(seconds=seconds)
    return utc_dt.astimezone().replace(tzinfo=None)


def _parse_mvhd_from_bytes(data: bytes):
    pos = 0
    while pos < len(data) - 8:
        try:
            box_size = struct.unpack_from('>I', data, pos)[0]
            box_type = data[pos + 4:pos + 8]
        except struct.error:
            break

        if box_size < 8:
            break

        if box_type == b'mvhd':
            version = data[pos + 8]
            if version == 0:
                creation_time = struct.unpack_from('>I', data, pos + 12)[0]
            else:
                creation_time = struct.unpack_from('>Q', data, pos + 12)[0]
            if creation_time > 0:
                return _qt_seconds_to_datetime(creation_time)
            return None

        if box_type in (b'moov', b'trak', b'mdia', b'minf', b'stbl', b'udta'):
            inner = _parse_mvhd_from_bytes(data[pos + 8:pos + box_size])
            if inner:
                return inner

        pos += box_size
    return None


def get_mov_datetime(filepath: Path):
    if MUTAGEN_AVAILABLE:
        try:
            tags = MP4(str(filepath))
            day_tag = tags.get('©day')
            if day_tag:
                raw = str(day_tag[0]).strip()
                for fmt in (
                    '%Y-%m-%dT%H:%M:%S%z',
                    '%Y-%m-%dT%H:%M:%S',
                    '%Y-%m-%d %H:%M:%S',
                    '%Y-%m-%d',
                    '%Y/%m/%d',
                ):
                    try:
                        dt = datetime.strptime(raw[:19] if 'T' in raw or ' ' in raw else raw, fmt)
                        return dt.replace(tzinfo=None)
                    except ValueError:
                        continue
        except Exception:
            pass

    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024 * 1024)
        dt = _parse_mvhd_from_bytes(chunk)
        if dt:
            return dt

        with open(filepath, 'rb') as f:
            full_data = f.read()
        return _parse_mvhd_from_bytes(full_data)
    except Exception:
        return None


def get_exif_datetime(filepath: Path):
    try:
        with Image.open(filepath) as img:
            exif_data = None
            if hasattr(img, 'getexif'):
                exif_data = img.getexif()
            if not exif_data and hasattr(img, '_getexif'):
                exif_data = img._getexif()
            if not exif_data:
                return None

            try:
                exif_ifd = exif_data.get_ifd(34665)
                if exif_ifd:
                    value = exif_ifd.get(36867) or exif_ifd.get(36868)
                    if value:
                        return datetime.strptime(str(value).strip(), "%Y:%m:%d %H:%M:%S")
            except Exception:
                pass

            for tag_id in (36867, 36868, 306):
                value = exif_data.get(tag_id)
                if value:
                    try:
                        return datetime.strptime(str(value).strip(), "%Y:%m:%d %H:%M:%S")
                    except ValueError:
                        continue
    except Exception:
        return None
    return None


def get_file_mtime(filepath: Path) -> datetime:
    return datetime.fromtimestamp(os.path.getmtime(filepath))


def already_has_date_prefix(filename: str) -> bool:
    return bool(DATE_PATTERN.match(filename))


def make_unique_path(target_path: Path) -> Path:
    if not target_path.exists():
        return target_path
    stem = target_path.stem
    suffix = target_path.suffix
    parent = target_path.parent
    counter = 1
    while True:
        new_path = parent / f"{stem}_{counter}{suffix}"
        if not new_path.exists():
            return new_path
        counter += 1


class Logger:
    def __init__(self):
        self.lines = []

    def write(self, text=""):
        self.lines.append(text)

    def dump(self):
        return "\n".join(self.lines)


class SorterEngine:
    def __init__(self, logger: Logger):
        self.logger = logger

    def sort_into_date_folders(self, folder_path: str, dry_run: bool = False):
        folder = Path(folder_path)
        if not folder.exists():
            self.logger.write(f"Folder not found: {folder_path}")
            return False

        files = [
            f for f in folder.iterdir()
            if f.is_file()
            and f.suffix.lower() in SUPPORTED_EXTENSIONS
            and FILENAME_DATE_EXTRACT.match(f.name)
        ]

        if not files:
            self.logger.write("No files with a date prefix were found, so folder sorting was skipped.")
            return True

        self.logger.write("")
        self.logger.write("Organizing files into date folders")
        self.logger.write("-" * 60)

        moved = 0
        errors = 0
        groups = {}
        for f in sorted(files):
            m = FILENAME_DATE_EXTRACT.match(f.name)
            year, month, day = m.group(1), m.group(2), m.group(3)
            folder_name = f"{year}_{month}{day}"
            groups.setdefault(folder_name, []).append(f)

        for folder_name in sorted(groups):
            target_dir = folder / folder_name
            file_list = groups[folder_name]
            self.logger.write(f"[{folder_name}] {len(file_list)} file(s)")

            if not dry_run:
                target_dir.mkdir(exist_ok=True)

            for filepath in file_list:
                dest = make_unique_path(target_dir / filepath.name)
                self.logger.write(f"  -> {filepath.name}")
                if not dry_run:
                    try:
                        filepath.rename(dest)
                        moved += 1
                    except Exception as e:
                        self.logger.write(f"     ERROR: {e}")
                        errors += 1
                else:
                    moved += 1

        self.logger.write("-" * 60)
        self.logger.write(f"Folder organization complete: moved {moved} file(s), created {len(groups)} folder(s)")
        if errors:
            self.logger.write(f"Errors: {errors}")
        return errors == 0

    def rename_photos(self, folder_path: str, dry_run: bool = False, sort_after: bool = False):
        folder = Path(folder_path)
        if not folder.exists():
            self.logger.write(f"Folder not found: {folder_path}")
            return False

        files = [f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS]
        if not files:
            self.logger.write("No supported photo or video files were found.")
            return False

        self.logger.write(f"Folder: {folder}")
        self.logger.write(f"Supported files found: {len(files)}")
        self.logger.write("-" * 60)

        renamed = 0
        skipped = 0
        fallback = 0
        errors = 0

        for filepath in sorted(files):
            filename = filepath.name
            stem = filepath.stem
            suffix = filepath.suffix.lower()

            if already_has_date_prefix(filename):
                self.logger.write(f"SKIP   already dated: {filename}")
                skipped += 1
                continue

            if suffix in VIDEO_EXTENSIONS:
                dt = get_mov_datetime(filepath)
                source = "QuickTime"
            else:
                dt = get_exif_datetime(filepath)
                source = "EXIF"

            if dt is None:
                dt = get_file_mtime(filepath)
                source = "File modified time"
                fallback += 1

            date_prefix = dt.strftime("%Y%m%d_%H%M%S")
            new_name = f"{date_prefix}_{stem}{suffix}"
            new_path = make_unique_path(folder / new_name)

            self.logger.write(f"OK     [{source}] {filename}")
            self.logger.write(f"       -> {new_path.name}")

            if not dry_run:
                try:
                    filepath.rename(new_path)
                    renamed += 1
                except Exception as e:
                    self.logger.write(f"       ERROR: {e}")
                    errors += 1
            else:
                renamed += 1

        self.logger.write("-" * 60)
        self.logger.write(f"Rename complete: {renamed} renamed, {skipped} skipped, {fallback} used file modified time")
        if errors:
            self.logger.write(f"Errors: {errors}")

        if sort_after:
            self.sort_into_date_folders(folder_path, dry_run=dry_run)

        return errors == 0


class PhotoSorterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Photo & Video Sorter")
        self.root.geometry("920x680")
        self.root.minsize(820, 600)

        self.folder_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Select or drop a folder to begin.")

        self._setup_style()
        self._build_ui()

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        bg = "#f4f7fb"
        card = "#ffffff"
        accent = "#2563eb"
        border = "#dbe4f0"
        text = "#1f2937"
        muted = "#6b7280"

        self.colors = {
            "bg": bg,
            "card": card,
            "accent": accent,
            "border": border,
            "text": text,
            "muted": muted,
        }

        self.root.configure(bg=bg)
        style.configure("App.TFrame", background=bg)
        style.configure("Card.TFrame", background=card, relief="flat")
        style.configure("TLabel", background=bg, foreground=text, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=bg, foreground=text, font=("Segoe UI", 20, "bold"))
        style.configure("Sub.TLabel", background=bg, foreground=muted, font=("Segoe UI", 10))
        style.configure("CardTitle.TLabel", background=card, foreground=text, font=("Segoe UI", 11, "bold"))
        style.configure("CardText.TLabel", background=card, foreground=muted, font=("Segoe UI", 10))
        style.configure("Primary.TButton", font=("Segoe UI", 11, "bold"), padding=(18, 10))
        style.configure("Secondary.TButton", font=("Segoe UI", 11), padding=(18, 10))
        style.map("Primary.TButton", background=[("active", accent)])

    def _build_ui(self):
        outer = ttk.Frame(self.root, style="App.TFrame", padding=24)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="Photo & Video Sorter", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            outer,
            text="Rename media files by capture date and organize them into date folders.",
            style="Sub.TLabel"
        ).pack(anchor="w", pady=(4, 18))

        card = tk.Frame(outer, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1, bd=0)
        card.pack(fill="x", pady=(0, 16))

        top = tk.Frame(card, bg=self.colors["card"])
        top.pack(fill="x", padx=18, pady=(18, 8))
        tk.Label(top, text="Folder", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 11, "bold")).pack(anchor="w")
        tk.Label(
            top,
            text="Drag and drop a folder here, or click Browse.",
            bg=self.colors["card"], fg=self.colors["muted"], font=("Segoe UI", 10)
        ).pack(anchor="w", pady=(2, 0))

        self.drop_area = tk.Frame(card, bg="#f8fbff", highlightbackground=self.colors["border"], highlightthickness=2, bd=0, height=130)
        self.drop_area.pack(fill="x", padx=18, pady=(6, 12))
        self.drop_area.pack_propagate(False)

        self.drop_label = tk.Label(
            self.drop_area,
            text="Drop a folder here\n\nor use Browse",
            bg="#f8fbff",
            fg=self.colors["muted"],
            font=("Segoe UI", 13),
            justify="center"
        )
        self.drop_label.pack(expand=True)

        path_row = tk.Frame(card, bg=self.colors["card"])
        path_row.pack(fill="x", padx=18, pady=(0, 18))

        self.path_entry = ttk.Entry(path_row, textvariable=self.folder_var, font=("Segoe UI", 10))
        self.path_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(path_row, text="Browse", command=self.browse_folder, style="Secondary.TButton").pack(side="left", padx=(10, 0))

        actions = tk.Frame(outer, bg=self.colors["bg"])
        actions.pack(fill="x", pady=(0, 16))
        ttk.Button(actions, text="Preview", command=self.preview_action, style="Secondary.TButton").pack(side="left")
        ttk.Button(actions, text="Rename and Organize", command=self.run_action, style="Primary.TButton").pack(side="left", padx=(10, 0))

        status = tk.Label(
            outer,
            textvariable=self.status_var,
            bg=self.colors["bg"], fg=self.colors["muted"],
            font=("Segoe UI", 10)
        )
        status.pack(anchor="w", pady=(0, 10))

        log_card = tk.Frame(outer, bg=self.colors["card"], highlightbackground=self.colors["border"], highlightthickness=1, bd=0)
        log_card.pack(fill="both", expand=True)
        tk.Label(log_card, text="Activity", bg=self.colors["card"], fg=self.colors["text"], font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=18, pady=(16, 8))

        text_wrap = tk.Frame(log_card, bg=self.colors["card"])
        text_wrap.pack(fill="both", expand=True, padx=18, pady=(0, 18))

        self.log_text = tk.Text(
            text_wrap,
            wrap="word",
            font=("Consolas", 10),
            bg="#fbfdff",
            fg="#1f2937",
            relief="flat",
            padx=12,
            pady=12,
            undo=False,
        )
        scrollbar = ttk.Scrollbar(text_wrap, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._bind_drop_target()
        self._append_log("Welcome. Choose a folder, then click Preview or Rename and Organize.")
        if not DND_AVAILABLE:
            self._append_log("Note: drag-and-drop is disabled because tkinterdnd2 is not installed. Browse still works.")

    def _bind_drop_target(self):
        if not DND_AVAILABLE:
            return
        try:
            self.drop_area.drop_target_register(DND_FILES)
            self.drop_area.dnd_bind('<<Drop>>', self.on_drop)
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind('<<Drop>>', self.on_drop)
        except Exception:
            self._append_log("Drag-and-drop could not be initialized. Browse will still work.")

    def on_drop(self, event):
        raw = event.data.strip()
        path = raw[1:-1] if raw.startswith('{') and raw.endswith('}') else raw
        if path and os.path.isdir(path):
            self.folder_var.set(path)
            self.status_var.set("Folder selected.")
            self._append_log(f"Selected folder: {path}")
        else:
            messagebox.showwarning("Invalid drop", "Please drop a folder, not a file.")

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select a folder")
        if folder:
            self.folder_var.set(folder)
            self.status_var.set("Folder selected.")
            self._append_log(f"Selected folder: {folder}")

    def _append_log(self, text: str):
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.root.update_idletasks()

    def _validate_folder(self):
        folder = self.folder_var.get().strip().strip('"').strip("'")
        if not folder:
            messagebox.showwarning("No folder selected", "Please choose or drop a folder first.")
            return None
        if not os.path.isdir(folder):
            messagebox.showerror("Folder not found", "The selected folder does not exist.")
            return None
        return folder

    def _run_engine(self, dry_run: bool, sort_after: bool):
        folder = self._validate_folder()
        if not folder:
            return

        self.log_text.delete("1.0", "end")
        logger = Logger()
        engine = SorterEngine(logger)

        ok = engine.rename_photos(folder, dry_run=dry_run, sort_after=sort_after)
        self._append_log(logger.dump())

        if dry_run:
            self.status_var.set("Preview complete.")
        else:
            self.status_var.set("Rename and organization complete." if ok else "Completed with some errors.")

        if not dry_run and ok:
            messagebox.showinfo("Done", "Files were renamed and organized into date folders.")

    def preview_action(self):
        self._run_engine(dry_run=True, sort_after=False)

    def run_action(self):
        folder = self._validate_folder()
        if not folder:
            return
        answer = messagebox.askyesno(
            "Confirm",
            "This will rename files and move them into date folders. Do you want to continue?"
        )
        if answer:
            self._run_engine(dry_run=False, sort_after=True)


def main():
    root_cls = TkinterDnD.Tk if DND_AVAILABLE else tk.Tk
    root = root_cls()
    app = PhotoSorterApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
