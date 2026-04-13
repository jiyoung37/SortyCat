# 🐱 SortyCat – Photo & Video Organizer

SortyCat is a simple and cute desktop tool that helps you clean up messy photo and video folders in seconds.

Just drag & drop your folder, and SortyCat will:

* 📸 Rename files using capture date (EXIF / video metadata)
* 🗂️ Organize them into date-based folders (YYYY_MMDD)
* ⚡ Work instantly with a clean and simple interface

---

## ✨ Features

* Drag & drop folder support
* Preview before applying changes
* Automatic renaming: `YYYYMMDD_HHMMSS_filename.ext`
* Smart fallback to file timestamp if metadata is missing
* Supports images and videos

---

## 🖼️ Example

Before:

```
IMG_1234.jpg
VID_5678.mov
random.png
```

After:

```
20240315_143022_IMG_1234.jpg
20240315_143045_VID_5678.mov
```

Organized into:

```
2024_0315/
```

---

## 🚀 How to Use

1. Launch the app
2. Drag & drop your folder
3. Click:

   * `Preview` → see what will change
   * `Rename and Organize` → apply changes

---

## 📦 Download

👉 Download the latest version from the Releases section.

---

## 🛠️ Built With

* Python
* Pillow (EXIF handling)
* Mutagen (video metadata)
* Tkinter (GUI)

---

## 🌍 Why SortyCat?

Because your photos deserve a clean home 🐾

---

## 📄 License

MIT License
