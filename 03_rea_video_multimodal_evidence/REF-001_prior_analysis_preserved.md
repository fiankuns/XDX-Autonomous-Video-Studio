# REA-Video ID — Pengujian video aktual

Input: 1001952045.mp4. Durasi video 154,5 s; kontainer 154,619 s; 720×1280, 30 fps, 4635 frame; H.264 + HE-AAC stereo.

## Hasil
Adapter asli fallback berhasil berjalan dengan threshold 0,30: 2 segmen kandidat, 6 frame. Hasil ini tidak memadai karena pemeriksaan 31 frame interval 5 detik menunjukkan banyak pergantian adegan. Uji sensitivitas 0,06 menghasilkan 36 frame kandidat, dikelompokkan dengan jarak maksimum 0,6 detik menjadi 29 puncak. Pasangan frame ±0,5 detik ditinjau secara visual. Ini bukan jumlah shot final.

## Observasi
Animasi 3D stylized/diorama, karakter kepala bulat dan anggota tubuh tipis, ekspresi kartun, properti tematik, latar interior dan eksterior, subtitle putih dengan outline gelap. Cerita satir tentang tata kelola, pelayanan publik, korupsi, dan pemilu. Pembuka dan penutup kembali ke kamar. Variasi framing, visual transisi lembut, pencahayaan hangat interior dan daylight eksterior. Engine pembuat dan prompt asli tidak teridentifikasi.

## QC
Metadata, ekstraksi frame dan pemeriksaan visual lulus. Deteksi hard cut default gagal mencakup struktur. Deteksi sensitif perlu validasi lebih lanjut; belum mendeteksi seluruh dissolve atau menentukan timestamp shot akurat. Tidak ada ASR, pemisahan audio, OCR otomatis atau engine upstream. Contact sheet menggunakan posisi seek yang diminta.

## Rekomendasi
Deteksi multiskala, threshold adaptif, perbandingan histogram dan fitur visual, pengelompokan transisi gradual, deteksi perubahan subtitle terpisah, validasi manual tiap kandidat, uji dengan anotasi ground truth.
