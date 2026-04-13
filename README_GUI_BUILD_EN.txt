Photo & Video Sorter GUI
========================

This package contains an English GUI version of the photo/video renamer.

Features
--------
- Drag and drop a folder onto the app window
- Browse for a folder manually
- Preview mode
- Rename and organize mode
- Automatically moves renamed files into YYYY_MMDD folders

How to build the Windows EXE
----------------------------
1. Install Python for Windows
2. Extract this ZIP file(photo_sorter_gui_package.zip)
3. Double-click: build_windows_gui_exe.bat
4. After the build finishes, open:
   dist\PhotoVideoSorterGUI.exe

Notes
-----
- Drag-and-drop support requires tkinterdnd2
- HEIC support requires pillow-heif
- MOV/MP4 metadata support uses mutagen when available
