# Integrasi upstream (ditinjau 26 November 2026)
Repo: https://github.com/JuneYaooo/rea-video
CLI: https://github.com/JuneYaooo/rea-video/blob/main/docs/en/cli.md
Workflow: https://github.com/JuneYaooo/rea-video/blob/main/docs/en/workflow.md
Skill: https://github.com/JuneYaooo/rea-video/blob/main/skills/rea-video/SKILL.md
OpenAI: https://help.openai.com/en/articles/20001066-skills-in-chatgpt

Untuk runtime Linux yang mendukung jaringan, review kode terlebih dahulu dan pin commit yang sudah diperiksa. Gunakan Python 3.12 (atau versi lain dengan wheel yang kompatibel) dan FFmpeg/FFprobe. Instal CLI melalui skrip upstream atau virtualenv dengan `pip install ".[ocr]"`; pada Python <=3.12 periksa konflik opencv-python/headless sebagaimana dijelaskan di workflow. ASR opsional, bahasa Indonesia tidak dijamin oleh ASR default. Download model pertama kali dapat memerlukan jaringan; jangan aktifkan VLM eksternal tanpa persetujuan dan kredensial yang sah.

Verifikasi `rea-video --help`; jalankan `rea-video decompose INPUT -o OUTPUT --lang en`; lihat `VIDEO.md`, `video/timeline.md`, frame shot dan `report.html`. `rea-video review OUTPUT` membuat tugas review, isi jawaban dengan bukti visual lalu `rea-video apply-review OUTPUT --by ChatGPT`. Untuk survei cut berbasis agen, gunakan `rea-video survey INPUT -o OUTPUT` sebelum decompose dan ikuti tahap review yang diminta. Terjemahkan laporan ke Indonesia tanpa mengubah timestamp atau schema. Jangan klaim format fallback sebagai format resmi.
