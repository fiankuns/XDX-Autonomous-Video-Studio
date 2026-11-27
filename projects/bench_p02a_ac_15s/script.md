# Naskah Produksi Siap Baca (VO, Dialog & Aksi Konkret) — Bagaimana AC Mendinginkan Ruangan? (Uji 4-Shot 15 Detik)

## B01 · `SEQ_01/SCN_01` · `0.0s – 3.5s` (hook_overheated_character)
- **Narasi VO (Bahasa Indonesia)**: AC tidak menciptakan dingin melainkan memindahkan panas kamarmu.
- **Catatan Humor Situasional**: Bima mengipasi wajah di kamar tertutup 32 derajat sambil melirik unit AC.
- **Rangkaian Aksi Visual Per-Shot**:
  1. `[THREEJS · establishing]` **Hook karakter Bima kepanasan di kamar tertutup 32 derajat di bawah unit AC indoor** — Bima mengipasi wajah di kamar pengap 32 derajat Celsius dengan jendela tertutup rapat di bawah prop_ac_indoor_evaporator_cutaway.

## B02 · `SEQ_01/SCN_01` · `3.5s – 7.0s` (remote_interaction)
- **Narasi VO (Bahasa Indonesia)**: Saat tombol remot ditekan, kisi AC terbuka.
- **Catatan Humor Situasional**: Ibu jari Bima menekan tombol remot dengan mantap dan kisi AC membuka mulus.
- **Rangkaian Aksi Visual Per-Shot**:
  1. `[THREEJS · medium]` **Interaksi tangan Bima menekan tombol 24 derajat pada remot AC menuju unit indoor** — Ibu jari kanan Bima menekan tombol daya dan setelan 24 derajat pada prop_ac_remote_control hingga sinyal inframerah membuka kisi prop_ac_indoor_evaporator_cutaway.

## B03 · `SEQ_02/SCN_02` · `7.0s – 11.0s` (technical_cutaway_evaporator)
- **Narasi VO (Bahasa Indonesia)**: Di evaporator, refrigeran cair menyerap panas kamar.
- **Rangkaian Aksi Visual Per-Shot**:
  1. `[THREEJS · cutaway]` **Penampang teknis kumparan evaporator tembaga AC indoor** — Casing depan prop_ac_indoor_evaporator_cutaway terbelah memperlihatkan kumparan pipa tembaga dingin menyerap panah kalor merah dari udara kamar hingga refrigeran cair menguap.

## B04 · `SEQ_02/SCN_03` · `11.0s – 15.0s` (heat_transfer_visualization)
- **Narasi VO (Bahasa Indonesia)**: Kompresor memompa uap panas ke kondensor luar.
- **Rangkaian Aksi Visual Per-Shot**:
  1. `[THREEJS · wide]` **Visualisasi perpindahan panas dari pipa evaporator indoor ke kompresor dan kondensor outdoor** — Aliran refrigeran oranye panas mengalir menembus dinding dari evaporator menuju prop_outdoor_compressor_condenser_unit sementara kipas kondensor melepas gelombang kalor ke udara luar.

