# Folder Launcher

Website kecil (berjalan secara lokal) untuk menyimpan senarai path folder Windows anda — klik sahaja kad folder untuk membukanya dalam Windows Explorer.

## Cara mula

1. Double-click fail **`start.bat`**
2. Browser akan terbuka sendiri di http://127.0.0.1:8765
3. Tambah folder: tampal path (cth `C:\Users\yusuf\Documents`) atau klik **📂 Pilih folder…** untuk guna dialog Windows
4. Klik mana-mana kad folder untuk membukanya

## Fail-fail

| Fail | Fungsi |
|---|---|
| `start.bat` | Double-click fail ini untuk mula |
| `server.py` | Server web kecil (Python, tiada perlu install apa-apa) |
| `index.html` | Antara muka website |
| `paths.json` | Senarai folder anda (backup fail ini) |

## Nota

- **Kenapa perlu server?** Browser tidak membenarkan website biasa membuka folder lokal atas sebab keselamatan. Server kecil ini (berjalan di PC anda sendiri) yang arahkan Windows Explorer membuka folder tersebut.
- Data disimpan dalam `paths.json` — mudah untuk backup atau pindah ke PC lain. Fail ini **dikecualikan daripada repo** (lihat `.gitignore`) supaya senarai folder anda tidak dimuat naik; formatnya boleh dirujuk di `paths.example.json`.
- Server hanya boleh diakses dari komputer anda sendiri (127.0.0.1), bukan dari luar.
- Anda boleh pindahkan folder ini ke mana-mana (cth `C:\Tools\FolderLauncher`) — asalkan keempat-empat fail kekal bersama.
- Tip: kalau nak auto-mula bila hidupkan PC, tekan `Win+R`, taip `shell:startup`, lalu letak shortcut ke `start.bat` dalam folder itu.

## GitHub Pages

Laman penerangan & muat turun projek: https://whwgywgr.github.io/folder-launcher/ (dibina dari folder `docs/`). Ciri "klik untuk buka folder" hanya berfungsi bila dijalankan secara lokal melalui `start.bat` — GitHub Pages tidak boleh menjalankan server Python.
