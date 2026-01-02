# 🎮 Game Integrity Dashboard

A high-performance, dark-themed utility for PC gamers and modders to backup and verify game file integrity. 

Stop redownloading 100GB games just because one file is corrupted. With this tool, you can create a "Master Hash" of your clean game files and verify them in seconds whenever a crash occurs.

---

## ✨ Features

* **🗂️ Library Auto-Detection:** Select your main Games folder once, and all your games appear in a convenient sidebar.
* **⚡ High-Speed Verification:** Optimized 64KB chunked hashing to handle massive titles (RDR2, GTA V, etc.) without crashing your RAM.
* **✅ Standardized Format:** Saves hashes in the universal `.md5` format (`hash *filename`).
* **🧵 Multi-Threaded:** The UI stays responsive and smooth while the background thread does the heavy lifting.
* **📁 Clean Organization:** All checksum files are automatically stored in a `/Checksums` folder for you.

---

## 🚀 How to Use

### For Users (Executable)
1.  Download `GameIntegrityTool.exe` from the [Releases](../../releases) tab.
2.  Launch the app and click **Set Game Library Directory**.
3.  Select a game from the list on the left.
4.  Click **Create Master Hash** to "fingerprint" your game.
5.  If the game ever breaks, select it and click **Verify Integrity**.
6.  Broken and/or missing files will be shown on logs

### For Developers (Python)
If you want to run the source code:
1.  Install dependencies:
    ```bash
    pip install PyQt6
    ```
2.  Run the script:
    ```bash
    python GameIntegrity.py
    ```

---

## 🛠️ Built With

* **Python 3.10+**
* **PyQt6** - Modern GUI Framework
* **Hashlib** - Secure MD5 Hashing
* **PyInstaller** - Executable Bundling

---
🤝 Join the Project!

This tool is Public Domain. That means it belongs to you just as much as it belongs to me. If you have an idea to make it faster, sleeker, or more powerful, jump in!

---

## 📜 License

This is free and unencumbered software released into the public domain.

Anyone is free to copy, modify, publish, use, compile, sell, or distribute this software, either in source code form or as a compiled binary, for any purpose, commercial or non-commercial, and by any means.

For more information, please refer to <http://unlicense.org/>

---

**Developed with ❤️ for the gaming community.**
