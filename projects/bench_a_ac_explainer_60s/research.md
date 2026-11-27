# Dossier Riset Universal v4.0 — Bagaimana AC Mendinginkan Ruangan?

- **Cakupan Topik (`Topic Scope`)**: Mekanisme termodinamika siklus kompresi uap pada AC split rumah tangga—meliputi evaporator, perubahan fase refrigeran, kompresor, kondensor, katup ekspansi, kalor laten pengembunan uap air, dan efisiensi pengaturan suhu termostat—dalam format explainer 3D berdurasi 60 detik.
- **Genre**: `explainer, edukasi` | **Mode Epistemik**: `factual_verified` (`VERIFIED_COMPLETE`)

## Pertanyaan Riset Utama
1. Bagaimana AC mendinginkan ruangan tertutup tanpa mengambil udara segar dari luar bangunan?
2. Mengapa perubahan fase cair-ke-uap refrigeran serta kerja kompresor dan katup ekspansi mampu memindahkan kalor melawan gradien suhu?
3. Mengapa menurunkan setelan remot ke 16 derajat Celsius tidak mempercepat laju pendinginan awal ruangan?

## Klaim Faktual Terverifikasi & Kutipan Bukti
- **`CLM_01` [verified_fact]**: Sistem AC mendinginkan ruangan dengan menarik udara hangat kamar melewati kumparan evaporator dingin berisi refrigeran yang menyerap kalor saat menguap dari cair menjadi gas.
  - Sumber: *U.S. Department of Energy — Energy Saver: Air Conditioning* (2024-06) — https://www.energy.gov/energysaver/air-conditioning
  - Ringkasan Bukti: Air conditioners transfer heat from the indoor air to the outdoors via an indoor evaporator coil filled with cold evaporating refrigerant.
- **`CLM_02` [verified_fact]**: Kompresor pada unit luar memampatkan gas refrigeran bertekanan rendah menjadi gas bersuhu dan bertekanan tinggi sehingga kalornya dapat dilepaskan ke udara luar melalui sirip kondensor.
  - Sumber: *Encyclopaedia Britannica — Air-conditioning: Principles of Operation* (2024-08) — https://www.britannica.com/technology/air-conditioning
  - Ringkasan Bukti: In vapor-compression air conditioning, the compressor raises refrigerant vapor pressure and temperature so the outdoor condenser coil rejects heat to ambient air.
- **`CLM_03` [verified_fact]**: Katup ekspansi menurunkan tekanan cairan refrigeran secara mendadak setelah keluar dari kondensor, menjatuhkan titik didih dan suhunya secara drastis sebelum masuk kembali ke evaporator.
  - Sumber: *National Institute of Standards and Technology (NIST) — Thermophysical Properties of Fluid Systems* (2023-11) — https://webbook.nist.gov/chemistry/fluid/
  - Ringkasan Bukti: Isenthalpic throttling across an expansion device drops refrigerant pressure and saturation temperature simultaneously, producing a cold two-phase mixture.
- **`CLM_04` [verified_fact]**: Selain menurunkan suhu udara (kalor sensibel), sirip evaporator dingin mengembunkan uap air dari udara kamar (kalor laten dehumidifikasi), dan termostat bekerja paling hemat pada suhu nyaman stabil tanpa perlu disetel ekstrem rendah di awal.
  - Sumber: *U.S. Department of Energy — Central Air Conditioning and Thermostat Operation* (2024-05) — https://www.energy.gov/energysaver/central-air-conditioning
  - Ringkasan Bukti: Indoor evaporator coils dehumidify room air by condensing moisture while cooling at a steady rate; setting the thermostat lower does not cool the house faster.

## Pemetaan Fakta ke Narasi (`Fact-to-Narration Mapping`)
- **`CLM_01`** → Beat `B01, B02`
- **`CLM_02`** → Beat `B03`
- **`CLM_03`** → Beat `B04`
- **`CLM_04`** → Beat `B04, B05`

## Miskonsepsi Umum & Koreksi
- **Miskonsepsi**: Unit AC menyedot udara luar lalu menyemprotkannya sebagai udara dingin baru ke dalam ruangan. → **Koreksi**: AC split mensirkulasikan ulang udara di dalam ruangan melewati sirip evaporator dingin; hanya kalor yang berpindah ke luar melalui aliran pipa refrigeran tertutup.
- **Miskonsepsi**: Menyetel remot ke suhu paling rendah seperti 16 derajat Celsius membuat AC menyemburkan hawa dingin lebih cepat sejak menit pertama. → **Koreksi**: Pada AC standar, laju penyerapan panas evaporator berlangsung konstan sampai suhu ruang menyentuh target termostat, sehingga setelan terlalu rendah hanya memaksa kompresor bekerja lebih lama.

## Batas Ketidakpastian (`Uncertainty`) & Pemisahan Fiksi
- *Ketidakpastian*: Kecepatan penurunan suhu kamar pada praktik sehari-hari bervariasi menurut beban kalor matahari, kerapatan insulasi dinding, jumlah penghuni, dan teknologi kompresor inverter maupun non-inverter.
- *Ketidakpastian*: Koefisien performa (COP) aktual berubah mengikuti selisih suhu udara luar di sekitar unit kondensor dan tingkat kebersihan kisi penukar kalor.
- *Elemen Fiksi Terdeklarasi*: Tokoh presenter Nadia dan penghuni kamar Bima beserta tata ruang kamar kos bergaya stylized 3D merupakan perangkat dramatisasi visual edukatif untuk memperjelas komponen nyata siklus AC.

