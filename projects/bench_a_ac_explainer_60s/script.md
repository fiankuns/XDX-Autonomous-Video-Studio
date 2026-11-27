# Naskah Produksi Siap Baca (VO, Dialog & Aksi Konkret) — Bagaimana AC Mendinginkan Ruangan?

## B01 · `SEQ_01/SCN_01` · `0.0s – 10.0s` (hook_anomaly_and_misconception)
- **Narasi VO (Bahasa Indonesia)**: Pernah heran bagaimana AC mendinginkan ruangan pengap tanpa memasukkan udara dari luar? Rahasianya: AC bukan pembuat dingin, melainkan pemindah panas kamar.
- **Dialog `char_bima_penghuni`** *(terkejut polos sambil menunjuk kusen jendela)*: "Pantas lubang anginnya rapat semua!"
- **Catatan Humor Situasional**: Bima menempelkan pipinya ke kaca jendela yang terkunci rapat mencari celah angin, padahal hembusan sejuk datang dari kotak tertutup di atas kepalanya.
- **Rangkaian Aksi Visual Per-Shot**:
  1. `[BLENDER · establishing]` **Bima kepanasan di kamar tertutup di bawah unit AC split** — Kamera mendorong masuk ke kamar kos yang jendelanya tertutup rapat sementara Bima mengipasi wajah dan termometer meja menyala di angka 32 derajat Celsius.
  2. `[BLENDER · medium]` **Nadia menggeser penutup depan AC di samping Bima** — Bima menoleh ke kusen jendela yang terkunci sambil berujar heran, lalu Nadia mengangkat cangkang depan unit AC indoor hingga tampak deretan pipa tembaga evaporator berkilau dingin.

## B02 · `SEQ_01/SCN_02` · `10.0s – 23.0s` (evaporator_phase_change_mechanism)
- **Narasi VO (Bahasa Indonesia)**: Udara hangat ruangan ditarik kipas melewati kisi evaporator yang sangat dingin. Di dalam pipanya, cairan refrigeran menyerap kalor udara lalu mendidih menjadi uap bertekanan rendah.
- **Rangkaian Aksi Visual Per-Shot**:
  1. `[BLENDER · cutaway]` **Penampang kipas blower dan kisi evaporator dalam ruang** — Pita udara oranye hangat dari kamar tersedot ke kisi aluminium evaporator lalu meluncur keluar kembali ke kamar sebagai aliran udara biru sejuk.
  2. `[THREEJS · close_up]` **Gelembung refrigeran mendidih di dalam pipa tembaga transparan** — Kamera makro menembus dinding pipa evaporator memperlihatkan cairan refrigeran biru pirus menyerap partikel kalor keemasan hingga bergejolak mendidih menjadi uap.

## B03 · `SEQ_02/SCN_03` · `23.0s – 37.0s` (compressor_and_condenser_heat_rejection)
- **Narasi VO (Bahasa Indonesia)**: Uap pembawa panas itu mengalir ke unit luar menuju kompresor. Kompresor memampatkannya hingga bersuhu tinggi, supaya sirip kondensor mudah membuang panasnya ke udara luar.
- **Dialog `char_nadia_presenter`** *(tersenyum sambil menunjuk kipas kondensor luar)*: "Makanya angin unit luar selalu terasa gerah."
- **Catatan Humor Situasional**: Daun tanaman pot di depan kipas unit outdoor bergoyang terkena hembusan hangat persis saat Nadia menjelaskan ke mana perginya panas kamar Bima.
- **Rangkaian Aksi Visual Per-Shot**:
  1. `[BLENDER · wide]` **Unit outdoor terurai memperlihatkan kompresor dan sirip kondensor** — Casing logam unit outdoor bergeser terbuka secara exploded view; tabung kompresor memompa uap refrigeran hingga berpijar merah-oranye bertekanan tinggi menuju jaringan pipa kondensor.
  2. `[BLENDER · medium]` **Nadia berdiri di balkon samping kipas unit outdoor yang membuang kalor** — Kipas besar unit outdoor menghembuskan gelombang kalor hangat ke udara terbuka sementara Nadia menunjuk aliran panas keluar dari sirip kondensor.

## B04 · `SEQ_02/SCN_04` · `37.0s – 50.0s` (expansion_valve_drop_and_dehumidification)
- **Narasi VO (Bahasa Indonesia)**: Setelah mengembun kembali jadi cairan, refrigeran dipaksa melewati celah sempit katup ekspansi. Tekanannya anjlok, suhunya langsung membeku lagi, sambil mengembunkan uap air lembap ruangan.
- **Rangkaian Aksi Visual Per-Shot**:
  1. `[THREEJS · insert]` **Penyempitan celah katup ekspansi yang mendinginkan cairan refrigeran** — Cairan refrigeran hangat melesat melewati leher sempit katup ekspansi; begitu melewati celah, warnanya langsung berubah biru es disertai kabut dingin bertekanan rendah.
  2. `[BLENDER · close_up]` **Butiran embun uap air menetes ke talang pembuangan evaporator** — Tetesan uap air dari udara kamar mengembun di permukaan sirip evaporator dingin lalu mengalir rapi melalui talang dan selang pembuangan air AC.

## B05 · `SEQ_03/SCN_05` · `50.0s – 60.0s` (payoff_thermostat_efficiency_callback)
- **Narasi VO (Bahasa Indonesia)**: Jadi tak perlu menekan remot ke enam belas derajat agar cepat sejuk. Setel dua puluh empat derajat saja, biarkan siklus pemindah panas bekerja hemat!
- **Dialog `char_bima_penghuni`** *(lega jenaka sambil mengacungkan jempol)*: "Dompet aman, kamar tetap adem!"
- **Catatan Humor Situasional**: Bima yang tadinya siap menekan tombol turun berkali-kali tersipu malu lalu menaikkan angka remot ke 24 derajat Celsius.
- **Rangkaian Aksi Visual Per-Shot**:
  1. `[BLENDER · insert]` **Layar remot AC naik dari 16°C ke 24°C di depan termometer kamar** — Ibu jari Bima menekan tombol naik pada remot AC dari 16°C menuju 24°C sementara layar termometer digital meja di latar belakang turun mantap ke 24°C.
  2. `[BLENDER · reaction]` **Bima bersandar nyaman bersama Nadia di kamar yang sejuk** — Penutup unit AC indoor kembali tertutup rapi menghembuskan angin lembut, Nadia mengangguk puas, dan Bima bersandar santai meletakkan kipas kertasnya.

