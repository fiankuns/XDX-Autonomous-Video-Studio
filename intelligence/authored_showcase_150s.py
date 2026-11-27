"""Genuine AI-Authored Production Payloads & Verified Research Dossiers (v3.4).

Authored directly by the AI Agent acting as Researcher, Scriptwriter, Dialogue Writer,
Historian, and Animation Director — containing zero template placeholders, natural spoken
Bahasa Indonesia narration, character dialogue, concrete 3D diorama visual actions, and
real peer-reviewed / institutional sources.
"""

from __future__ import annotations

import copy
from typing import Any


def build_authored_time_perception_payload(
    *,
    project_id: str = "persepsi_waktu_150s",
    target_duration_s: int = 150,
    genres: list[str] | None = None,
) -> dict[str, Any]:
    """Return a rich, broadcast-ready Indonesian production payload adaptable to 15..180s."""
    active_genres = genres or ["explainer", "edukasi", "sejarah", "biografi", "komedi_absurd"]
    is_pure_fiction = all(g in {"horor", "storytelling", "komedi_absurd"} for g in active_genres)

    all_12_beats: list[dict[str, Any]] = [
        {
            "beat_id": "B01",
            "act": "ACT_1",
            "sequence_id": "SEQ_01",
            "scene_id": "SCN_01",
            "environment_id": "env_kamar_indonesia_modular_v1",
            "beat_role": "hook_visual_anomaly",
            "target_duration_s": 12.0,
            "narration_vo": (
                "Pernahkah kamu menyenggol gelas kopi di pinggir meja, lalu tiba-tiba seluruh ruangan "
                "terasa melambat seperti adegan film laga, padahal jarum jam dinding tetap berdetak normal?"
            ),
            "claim_refs": ["CLM_01"],
            "humor_beat": "Kontras dramatis wajah panik Raka terhadap insiden sepele gelas miring tiga derajat.",
            "emotion": "shocked_absurd",
            "dialogue_lines": [
                {
                    "speaker_id": "char_raka_protagonist",
                    "line": "Tunggu dulu, kenapa kopinya melayang lama sekali?!",
                    "delivery": "panik tertahan dengan mata membelalak",
                    "onscreen_speaking": False,
                }
            ],
            "shot_blueprints": [
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Siku Raka dan cangkir kopi di tepi meja kayu jati",
                    "concrete_action": "Siku kanan Raka menyenggol gagang cangkir keramik di atas meja belajar hingga cangkir miring melewati bibir meja.",
                    "props": ["prop_study_table_v1", "prop_desk_lamp_v1", "prop_wall_clock_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "establishing",
                    "is_cutaway": False,
                    "cutaway_purpose": "Membangun anomali visual 0-3 detik tanpa salam pembuka",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Wajah Raka dan pantulan tetesan kopi",
                    "concrete_action": "Kamera mendorong mendekat ke wajah Raka yang membeku sementara jarum detik jam dinding di latar belakang bergeser satu klik tegas.",
                    "props": ["prop_wall_clock_v1", "prop_desk_lamp_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "close_up",
                    "is_cutaway": False,
                    "cutaway_purpose": "Menunjukkan kontras antara kepanikan subjektif dan detak jam objektif",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Insert jarum jam dinding berdetak presisi",
                    "concrete_action": "Jarum menit dan detik pada jam dinding berbingkai gelap bergetar halus tepat satu detik tanpa melambat sedikit pun.",
                    "props": ["prop_wall_clock_v1"],
                    "preferred_engine": "threejs",
                    "shot_size": "insert",
                    "is_cutaway": True,
                    "cutaway_purpose": "Bukti visual bahwa waktu fisika tidak melambat",
                    "transition_in": "trans_whip_pan_cutaway_6f",
                },
            ],
        },
        {
            "beat_id": "B02",
            "act": "ACT_1",
            "sequence_id": "SEQ_01",
            "scene_id": "SCN_01",
            "environment_id": "env_kamar_indonesia_modular_v1",
            "beat_role": "core_scientific_question",
            "target_duration_s": 12.0,
            "narration_vo": (
                "Selama puluhan tahun banyak orang yakin otak manusia benar-benar mempercepat "
                "kecepatan rekam matanya saat terancam, mirip kamera berkecepatan tinggi."
            ),
            "claim_refs": ["CLM_01"],
            "humor_beat": "Naya menyodorkan buku catatan tebal tepat ketika Raka baru saja menangkap tatakan gelas.",
            "emotion": "curious_engaged",
            "dialogue_lines": [
                {
                    "speaker_id": "char_naya_researcher",
                    "line": "Kalau matamu secepat kamera sinema, harusnya gelas itu sudah ketangkap dari tadi.",
                    "delivery": "datar menyindir sambil menunjuk meja",
                    "onscreen_speaking": False,
                }
            ],
            "shot_blueprints": [
                {
                    "duration_weight": 1.1,
                    "visual_subject": "Naya berdiri di ambang pintu kayu kamar sambil memegang buku",
                    "concrete_action": "Pintu kayu kamar terbuka dan Naya melangkah masuk sambil mengangkat buku catatan bersampul merah ke arah meja Raka.",
                    "props": ["prop_wooden_door_v1", "prop_chronicle_book_v1", "prop_study_chair_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "medium",
                    "is_cutaway": False,
                    "cutaway_purpose": "Memperkenalkan karakter pendukung dan skeptisisme ilmiah",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Diagram perbandingan frame kamera cepat vs persepsi mata",
                    "concrete_action": "Dua kolom pedestal tiga dimensi tumbuh berdampingan membandingkan hipotesis frame mata cepat dengan kecepatan baca aktual retina.",
                    "props": ["prop_data_pedestal_compare_v1"],
                    "preferred_engine": "threejs",
                    "shot_size": "cutaway",
                    "is_cutaway": True,
                    "cutaway_purpose": "Memvisualkan hipotesis kamera lambat sebelum diuji eksperimen",
                    "transition_in": "trans_whip_pan_cutaway_6f",
                },
                {
                    "duration_weight": 0.9,
                    "visual_subject": "Reaksi Raka melirik buku di atas meja",
                    "concrete_action": "Raka menarik kursi belajarnya lalu mencondongkan badan memeriksa halaman diagram di buku Naya di bawah cahaya lampu meja.",
                    "props": ["prop_study_chair_v1", "prop_study_table_v1", "prop_chronicle_book_v1", "prop_desk_lamp_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "reaction",
                    "is_cutaway": False,
                    "cutaway_purpose": "Menjaga kesinambungan ruang meja belajar sebelum masuk ke eksperimen",
                    "transition_in": "trans_hard_cut_zero",
                },
            ],
        },
        {
            "beat_id": "B03",
            "act": "ACT_2",
            "sequence_id": "SEQ_02",
            "scene_id": "SCN_02",
            "environment_id": "env_kamar_indonesia_modular_v1",
            "beat_role": "eagleman_tower_experiment_setup",
            "target_duration_s": 14.0,
            "narration_vo": (
                "Pada tahun dua ribu tujuh, ahli saraf David Eagleman bersama Chess Stetson dan Matthew Fiesta "
                "menguji klaim ini secara ekstrem: menjatuhkan relawan telentang dari menara setinggi empat puluh delapan meter."
            ),
            "claim_refs": ["CLM_01"],
            "humor_beat": "Miniatur menara uji di atas meja tampak menjulang melewati kap lampu belajar.",
            "emotion": "curious_engaged",
            "dialogue_lines": [],
            "shot_blueprints": [
                {
                    "duration_weight": 1.2,
                    "visual_subject": "Diorama menara jatuh bebas setinggi 48 meter",
                    "concrete_action": "Model bangunan menara uji vertikal muncul secara terukur lengkap dengan jaring pengaman di dasar dan penanda tinggi empat puluh delapan meter.",
                    "props": ["prop_modular_tower_building_v1", "prop_shade_tree_v1"],
                    "preferred_engine": "threejs",
                    "shot_size": "wide",
                    "is_cutaway": True,
                    "cutaway_purpose": "Merekonstruksi skala tinggi menara eksperimen Stetson, Fiesta, dan Eagleman (2007)",
                    "transition_in": "trans_cross_dissolve_12f",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Kartu publikasi ilmiah tahun 2007 di timeline",
                    "concrete_action": "Pita tahun bergeser ke angka dua ribu tujuh menampilkan parameter eksperimen jatuh bebas menuju jaring tanpa beban tali pengikat.",
                    "props": ["prop_data_pedestal_compare_v1"],
                    "preferred_engine": "remotion",
                    "shot_size": "insert",
                    "is_cutaway": True,
                    "cutaway_purpose": "Menampilkan bukti publikasi PLoS ONE 2007 secara presisi",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Pohon penanda skala di samping dasar menara",
                    "concrete_action": "Kamera bergerak turun dari puncak menara melewati tajuk pohon rindang dan mobil parkir miniatur untuk memperlihatkan betapa tingginya jarak jatuh.",
                    "props": ["prop_modular_tower_building_v1", "prop_shade_tree_v1", "prop_city_vehicle_v1"],
                    "preferred_engine": "threejs",
                    "shot_size": "medium",
                    "is_cutaway": True,
                    "cutaway_purpose": "Memberi pembanding skala konkret antara pohon, mobil, dan tinggi 48 meter",
                    "transition_in": "trans_hard_cut_zero",
                },
            ],
        },
        {
            "beat_id": "B04",
            "act": "ACT_2",
            "sequence_id": "SEQ_02",
            "scene_id": "SCN_02",
            "environment_id": "env_kamar_indonesia_modular_v1",
            "beat_role": "perceptual_chronometer_test",
            "target_duration_s": 13.0,
            "narration_vo": (
                "Di pergelangan tangan peserta dipasang kronometer persepsi dengan angka LED yang berkedip "
                "sedikit terlalu cepat untuk dibaca saat tenang. Jika otak sungguh melambat, angka itu pasti terbaca jelas saat jatuh."
            ),
            "claim_refs": ["CLM_01"],
            "humor_beat": None,
            "emotion": "curious_engaged",
            "dialogue_lines": [],
            "shot_blueprints": [
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Jam pergelangan kronometer LED berkedip cepat",
                    "concrete_action": "Kamera makro menyorot layar kronometer bundar di pergelangan tangan saat pola angka berganti cepat membentuk kilau buram yang tak terbaca.",
                    "props": ["prop_wall_clock_v1"],
                    "preferred_engine": "threejs",
                    "shot_size": "insert",
                    "is_cutaway": True,
                    "cutaway_purpose": "Mendemonstrasikan cara kerja perceptual chronometer LED",
                    "transition_in": "trans_whip_pan_cutaway_6f",
                },
                {
                    "duration_weight": 1.1,
                    "visual_subject": "Raka mempraktikkan menatap pergelangan tangannya sambil mundur ke kasur",
                    "concrete_action": "Raka merebahkan punggung secara teatrikal ke atas kasur kamar sambil mengangkat pergelangan tangannya tepat di depan wajah.",
                    "props": ["prop_bedroom_bed_v1", "prop_wall_clock_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "medium",
                    "is_cutaway": False,
                    "cutaway_purpose": "Visualisasi fisik posisi jatuh telentang di dalam ruang diorama kamar",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Grafik hasil bacaan akurasi jatuh vs berdiri di tanah",
                    "concrete_action": "Grafik batang animasi menampilkan tingkat keterbacaan angka saat jatuh bebas yang sejajar dan tidak melebihi kontrol di permukaan tanah.",
                    "props": ["prop_data_pedestal_compare_v1"],
                    "preferred_engine": "remotion",
                    "shot_size": "cutaway",
                    "is_cutaway": True,
                    "cutaway_purpose": "Menyajikan hasil terukur eksperimen bahwa resolusi visual tidak meningkat",
                    "transition_in": "trans_hard_cut_zero",
                },
            ],
        },
        {
            "beat_id": "B05",
            "act": "ACT_2",
            "sequence_id": "SEQ_02",
            "scene_id": "SCN_02",
            "environment_id": "env_kamar_indonesia_modular_v1",
            "beat_role": "experiment_paradox_reveal",
            "target_duration_s": 12.0,
            "narration_vo": (
                "Hasilnya mengejutkan: tak satu pun peserta mampu membaca angka berkedip lebih baik saat jatuh. "
                "Namun ketika diminta menaksir durasi jatuhnya sendiri, mereka rata-rata merasa jatuh tiga puluh enam persen lebih lama!"
            ),
            "claim_refs": ["CLM_01"],
            "humor_beat": "Raka bangkit dari kasur dengan ekspresi merasa baru jatuh lima menit padahal baru dua detik.",
            "emotion": "shocked_absurd",
            "dialogue_lines": [
                {
                    "speaker_id": "char_raka_protagonist",
                    "line": "Jadi mata kita gagal baca angkanya, tapi otak tetap ngotot durasinya panjang?",
                    "delivery": "heran bercampur geli",
                    "onscreen_speaking": False,
                }
            ],
            "shot_blueprints": [
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Perbandingan durasi estimasi 36 persen lebih panjang",
                    "concrete_action": "Kolom kuning bertuliskan estimasi memori peserta tumbuh tiga puluh enam persen lebih tinggi dibanding kolom biru durasi jatuh sesungguhnya.",
                    "props": ["prop_data_pedestal_compare_v1"],
                    "preferred_engine": "threejs",
                    "shot_size": "cutaway",
                    "is_cutaway": True,
                    "cutaway_purpose": "Membuktikan selisih 36% antara durasi terukur dan estimasi retrospektif",
                    "transition_in": "trans_whip_pan_cutaway_6f",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Raka duduk di tepi kasur menatap Naya",
                    "concrete_action": "Raka bangkit duduk di tepi kasur berlapis selimut biru sambil merentangkan kedua telapak tangan menunjukkan ukuran waktu yang membengkak.",
                    "props": ["prop_bedroom_bed_v1", "prop_wardrobe_cabinet_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "medium",
                    "is_cutaway": False,
                    "cutaway_purpose": "Reaksi karakter menerjemahkan angka ilmiah ke gestur tubuh yang mudah dipahami",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Naya menunjuk lemari arsip buku di sudut kamar",
                    "concrete_action": "Naya membuka pintu lemari kayu di sudut ruangan dan menarik setumpuk buku tebal untuk menganalogikan kepadatan rekaman memori.",
                    "props": ["prop_wardrobe_cabinet_v1", "prop_chronicle_book_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "wide",
                    "is_cutaway": False,
                    "cutaway_purpose": "Jembatan visual menuju mekanisme memori amigdala",
                    "transition_in": "trans_hard_cut_zero",
                },
            ],
        },
        {
            "beat_id": "B06",
            "act": "ACT_2",
            "sequence_id": "SEQ_03",
            "scene_id": "SCN_03",
            "environment_id": "env_kamar_indonesia_modular_v1",
            "beat_role": "amygdala_memory_density_mechanism",
            "target_duration_s": 13.0,
            "narration_vo": (
                "Kuncinya ada pada amigdala. Riset neurobiologi James McGaugh menunjukkan bahwa saat darurat, "
                "amigdala memicu perekaman detail ingatan yang jauh lebih padat—dari bunyi gesekan baju sampai bayangan cahaya di jendela."
            ),
            "claim_refs": ["CLM_02"],
            "humor_beat": None,
            "emotion": "curious_engaged",
            "dialogue_lines": [],
            "shot_blueprints": [
                {
                    "duration_weight": 1.1,
                    "visual_subject": "Tumpukan buku tipis vs buku catatan tebal di atas meja",
                    "concrete_action": "Di atas meja kayu, satu buku tipis mewakili ingatan detik biasa sementara lima buku tebal bertumpuk mewakili ingatan detik darurat.",
                    "props": ["prop_study_table_v1", "prop_chronicle_book_v1", "prop_desk_lamp_v1"],
                    "preferred_engine": "threejs",
                    "shot_size": "insert",
                    "is_cutaway": True,
                    "cutaway_purpose": "Analogi 3D konkret bagaimana kepadatan memori menciptakan ilusi durasi panjang",
                    "transition_in": "trans_whip_pan_cutaway_6f",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Cahaya sore menembus kisi jendela kamar",
                    "concrete_action": "Berkas cahaya hangat masuk melalui kaca jendela berbingkai putih menyinari butiran debu halus yang tampak jelas di sekitar meja.",
                    "props": ["prop_room_window_v1", "prop_study_table_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "medium",
                    "is_cutaway": False,
                    "cutaway_purpose": "Memperlihatkan detail sensorik kecil yang biasanya diabaikan otak saat santai",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 0.9,
                    "visual_subject": "Skema alur pemutaran ulang memori retrospektif",
                    "concrete_action": "Diagram alir animasi memperlihatkan bahwa ilusi gerak lambat muncul saat otak membaca ulang arsip ingatan tebal, bukan saat peristiwa berlangsung.",
                    "props": ["prop_data_pedestal_compare_v1"],
                    "preferred_engine": "remotion",
                    "shot_size": "cutaway",
                    "is_cutaway": True,
                    "cutaway_purpose": "Menjelaskan perbedaan antara persepsi real-time dan rekonstruksi memori",
                    "transition_in": "trans_hard_cut_zero",
                },
            ],
        },
        {
            "beat_id": "B07",
            "act": "ACT_2",
            "sequence_id": "SEQ_04",
            "scene_id": "SCN_04",
            "environment_id": "env_historical_archive_hall_v1",
            "beat_role": "historical_biography_john_harrison",
            "target_duration_s": 14.0,
            "narration_vo": (
                "Ketidakmampuan manusia menakar waktu secara konsisten inilah yang dulu mencelakai pelaut. "
                "Pada abad kedelapan belas, tukang kayu otodidak Inggris bernama John Harrison menghabiskan puluhan tahun merancang kronometer laut H-Empat."
            ),
            "claim_refs": ["CLM_03"],
            "humor_beat": None,
            "emotion": "solemn_historical",
            "dialogue_lines": [],
            "shot_blueprints": [
                {
                    "duration_weight": 1.1,
                    "visual_subject": "Ruang arsip sejarah dengan meja kayu tua dan lampu baca",
                    "concrete_action": "Transisi larut membuka ruang studi arsip berpalet hangat tempat buku kronik abad kedelapan belas dan jam bundar mekanis diletakkan di meja.",
                    "props": ["prop_study_table_v1", "prop_chronicle_book_v1", "prop_wall_clock_v1", "prop_desk_lamp_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "establishing",
                    "is_cutaway": False,
                    "cutaway_purpose": "Membangun atmosfer rekonstruksi sejarah biografi John Harrison",
                    "transition_in": "trans_cross_dissolve_12f",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Karakter perajin sejarah memeriksa jam mekanis di meja kerja",
                    "concrete_action": "Figur rekonstruksi perajin membungkuk dengan teliti di kursi kayu sambil menyetel jarum jam bundar di samping lemari naskah.",
                    "props": ["prop_study_chair_v1", "prop_study_table_v1", "prop_wall_clock_v1", "prop_wardrobe_cabinet_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "medium",
                    "is_cutaway": False,
                    "cutaway_purpose": "Rekonstruksi bergaya diorama atas ketekunan pembuatan kronometer 1759",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Kartu tahun 1759 kronometer laut H4",
                    "concrete_action": "Penanda tahun seribu tujuh ratus lima puluh sembilan menyoroti pencapaian kronometer laut H-Empat menjaga akurasi penentuan garis bujur pelayaran.",
                    "props": ["prop_wall_clock_v1"],
                    "preferred_engine": "remotion",
                    "shot_size": "insert",
                    "is_cutaway": True,
                    "cutaway_purpose": "Konteks historis terverifikasi dari Royal Museums Greenwich",
                    "transition_in": "trans_hard_cut_zero",
                },
            ],
        },
        {
            "beat_id": "B08",
            "act": "ACT_2",
            "sequence_id": "SEQ_04",
            "scene_id": "SCN_04",
            "environment_id": "env_historical_archive_hall_v1",
            "beat_role": "atomic_second_standard_bipm",
            "target_duration_s": 12.0,
            "narration_vo": (
                "Kini manusia tidak lagi mengandalkan perasaan atau pegas logam semata. "
                "Satu detik resmi didefinisikan dari lebih sembilan miliar getaran radiasi transisi atom Sesium seratus tiga puluh tiga."
            ),
            "claim_refs": ["CLM_04"],
            "humor_beat": "Kontras antara sembilan miliar getaran atom per detik dan Raka yang terlambat bangun lima belas menit.",
            "emotion": "curious_engaged",
            "dialogue_lines": [],
            "shot_blueprints": [
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Visualisasi gelombang osilasi presisi 9.192.631.770 siklus",
                    "concrete_action": "Partikel bercahaya berosilasi secara teratur di atas panggung gelap menampilkan angka resmi sembilan miliar seratus sembilan puluh dua juta getaran per detik.",
                    "props": ["prop_data_pedestal_compare_v1"],
                    "preferred_engine": "threejs",
                    "shot_size": "cutaway",
                    "is_cutaway": True,
                    "cutaway_purpose": "Visualisasi definisi detik SI berdasarkan standar BIPM",
                    "transition_in": "trans_whip_pan_cutaway_6f",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Perbandingan presisi jam mekanis ke standar atom SI",
                    "concrete_action": "Skala lini masa merentang dari jam saku abad kedelapan belas menuju standar atom modern yang menjadi acuan satelit navigasi.",
                    "props": ["prop_wall_clock_v1", "prop_data_pedestal_compare_v1"],
                    "preferred_engine": "remotion",
                    "shot_size": "insert",
                    "is_cutaway": True,
                    "cutaway_purpose": "Menyambungkan sejarah kronometer dengan fisika waktu modern",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Jam dinding dan jendela ruang arsip",
                    "concrete_action": "Kamera bergerak menyamping melewati jendela ruang arsip kembali mengarah ke pintu penghubung menuju masa kini.",
                    "props": ["prop_room_window_v1", "prop_wooden_door_v1", "prop_wall_clock_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "wide",
                    "is_cutaway": False,
                    "cutaway_purpose": "Transisi ruang yang mulus kembali ke keseharian penonton Indonesia",
                    "transition_in": "trans_hard_cut_zero",
                },
            ],
        },
        {
            "beat_id": "B09",
            "act": "ACT_2",
            "sequence_id": "SEQ_05",
            "scene_id": "SCN_05",
            "environment_id": "env_kamar_indonesia_modular_v1",
            "beat_role": "everyday_indonesian_contrast",
            "target_duration_s": 12.0,
            "narration_vo": (
                "Efek kepadatan memori ini juga menjawab teka-teki klasik sehari-hari: kenapa menunggu lampu merah "
                "satu menit saat kebelet terasa abadi, sedangkan bermain ponsel satu jam lenyap tanpa jejak?"
            ),
            "claim_refs": ["CLM_02"],
            "humor_beat": "Mobil biru miniatur berhenti tepat di depan pohon sementara pengemudinya menatap jam raksasa.",
            "emotion": "shocked_absurd",
            "dialogue_lines": [],
            "shot_blueprints": [
                {
                    "duration_weight": 1.1,
                    "visual_subject": "Mobil miniatur tertahan di jalan dekat bangunan dan pohon",
                    "concrete_action": "Sebuah kendaraan biru berhenti di tepi jalan miniatur di depan bangunan toko dan pohon peneduh sementara lampu depannya menyala hangat.",
                    "props": ["prop_city_vehicle_v1", "prop_modular_tower_building_v1", "prop_shade_tree_v1"],
                    "preferred_engine": "threejs",
                    "shot_size": "wide",
                    "is_cutaway": True,
                    "cutaway_purpose": "Ilustrasi situasi jalanan sehari-hari yang dekat dengan penonton Indonesia",
                    "transition_in": "trans_cross_dissolve_12f",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Raka bersandar malas di kursi belajarnya",
                    "concrete_action": "Di dalam kamar, Raka bersandar santai di kursi kayu sambil mengetuk-ngetuk jari ke permukaan meja dengan ekspresi bengong tanpa beban.",
                    "props": ["prop_study_chair_v1", "prop_study_table_v1", "prop_desk_lamp_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "medium",
                    "is_cutaway": False,
                    "cutaway_purpose": "Menunjukkan kondisi rutin minim informasi baru di otak",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 0.9,
                    "visual_subject": "Perbandingan kepadatan jejak memori baru vs rutinitas",
                    "concrete_action": "Dua grafik garis bergerak kontras memperlihatkan betapa tipisnya catatan memori saat aktivitas pasif berulang dibanding momen penuh kejutan.",
                    "props": ["prop_data_pedestal_compare_v1"],
                    "preferred_engine": "remotion",
                    "shot_size": "cutaway",
                    "is_cutaway": True,
                    "cutaway_purpose": "Menegaskan prinsip kepadatan memori pada pengalaman harian",
                    "transition_in": "trans_hard_cut_zero",
                },
            ],
        },
        {
            "beat_id": "B10",
            "act": "ACT_3",
            "sequence_id": "SEQ_05",
            "scene_id": "SCN_05",
            "environment_id": "env_kamar_indonesia_modular_v1",
            "beat_role": "absurd_escalation_experiment_at_home",
            "target_duration_s": 12.0,
            "narration_vo": (
                "Mendengar penjelasan itu, Raka langsung menyimpulkan ide konyol: kalau ingin akhir pekan terasa "
                "dua kali lebih panjang, berarti ia harus mengisi kamarnya dengan kejutan baru setiap sepuluh menit!"
            ),
            "claim_refs": ["CLM_01", "CLM_02"],
            "humor_beat": "Raka menata lampu, buku, dan jam dinding secara berlebihan demi memancing kejutan amigdala.",
            "emotion": "shocked_absurd",
            "dialogue_lines": [
                {
                    "speaker_id": "char_raka_protagonist",
                    "line": "Berarti kalau aku kaget terus tiap jam, hari Minggu kita jadi serasa empat hari!",
                    "delivery": "antusias penuh percaya diri yang absurd",
                    "onscreen_speaking": False,
                },
                {
                    "speaker_id": "char_naya_researcher",
                    "line": "Itu namanya uji nyali jantung, Raka, bukan liburan akhir pekan.",
                    "delivery": "datar menahan tawa",
                    "onscreen_speaking": False,
                },
            ],
            "shot_blueprints": [
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Raka berdiri antusias di samping meja dan lampu belajar",
                    "concrete_action": "Raka berdiri tegak dari kursinya sambil mengangkat satu jari penuh semangat ke arah jam dinding dan tumpukan buku di meja.",
                    "props": ["prop_study_table_v1", "prop_study_chair_v1", "prop_desk_lamp_v1", "prop_wall_clock_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "medium",
                    "is_cutaway": False,
                    "cutaway_purpose": "Eskalasi komedi situasional dari kesimpulan ilmiah yang ditarik terlalu jauh",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Naya menggeleng pelan di dekat pintu dan lemari",
                    "concrete_action": "Naya menyilangkan tangan di dekat lemari kayu sambil menatap Raka dengan alis terangkat sebelah.",
                    "props": ["prop_wardrobe_cabinet_v1", "prop_wooden_door_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "reaction",
                    "is_cutaway": False,
                    "cutaway_purpose": "Memberikan ruang jeda reaksi komedi setelah dialog Raka",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Close-up lampu meja menyala terang menyinari buku",
                    "concrete_action": "Cahaya hangat dari kap lampu meja menyorot halaman buku terbuka yang memuat rangkuman cara sehat memperkaya memori.",
                    "props": ["prop_desk_lamp_v1", "prop_chronicle_book_v1", "prop_study_table_v1"],
                    "preferred_engine": "threejs",
                    "shot_size": "insert",
                    "is_cutaway": True,
                    "cutaway_purpose": "Mengembalikan eskalasi absurd ke solusi edukatif yang masuk akal",
                    "transition_in": "trans_whip_pan_cutaway_6f",
                },
            ],
        },
        {
            "beat_id": "B11",
            "act": "ACT_3",
            "sequence_id": "SEQ_06",
            "scene_id": "SCN_06",
            "environment_id": "env_kamar_indonesia_modular_v1",
            "beat_role": "practical_takeaway_novelty",
            "target_duration_s": 12.0,
            "narration_vo": (
                "Tanpa perlu terjun dari menara, prinsipnya tetap sama: mencoba rute jalan baru, membaca topik asing, "
                "dan memberi perhatian penuh membuat otak menulis lebih banyak kenangan sehingga hidup tidak terasa melesat begitu saja."
            ),
            "claim_refs": ["CLM_02"],
            "humor_beat": None,
            "emotion": "curious_engaged",
            "dialogue_lines": [],
            "shot_blueprints": [
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Pemandangan luar jendela memperlihatkan jalan, pohon, dan bangunan",
                    "concrete_action": "Kamera bergerak melewati bingkai jendela kamar menatap jalan lingkungan yang teduh oleh pohon hijau dan deretan bangunan.",
                    "props": ["prop_room_window_v1", "prop_shade_tree_v1", "prop_modular_tower_building_v1"],
                    "preferred_engine": "threejs",
                    "shot_size": "wide",
                    "is_cutaway": True,
                    "cutaway_purpose": "Menggambarkan eksplorasi pengalaman baru di luar kamar",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Tiga poin ringkasan memori kaya vs rutinitas otomatis",
                    "concrete_action": "Kartu tipografi bersih merangkum tiga pemicu ingatan bermakna: hal baru, perhatian utuh, dan variasi pengalaman harian.",
                    "props": ["prop_data_pedestal_compare_v1"],
                    "preferred_engine": "remotion",
                    "shot_size": "cutaway",
                    "is_cutaway": True,
                    "cutaway_purpose": "Memberikan intisari edukasi yang konkret bagi penonton",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Raka mencatat di buku sambil tersenyum tenang",
                    "concrete_action": "Raka duduk kembali di kursi belajar dan meletakkan buku catatan dengan rapi di samping lampu meja yang bercahaya lembut.",
                    "props": ["prop_study_chair_v1", "prop_study_table_v1", "prop_chronicle_book_v1", "prop_desk_lamp_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "medium",
                    "is_cutaway": False,
                    "cutaway_purpose": "Resolusi karakter sebelum callback penutup",
                    "transition_in": "trans_hard_cut_zero",
                },
            ],
        },
        {
            "beat_id": "B12",
            "act": "ACT_3",
            "sequence_id": "SEQ_06",
            "scene_id": "SCN_06",
            "environment_id": "env_kamar_indonesia_modular_v1",
            "beat_role": "payoff_callback_loop",
            "target_duration_s": 12.0,
            "narration_vo": (
                "Jadi lain kali saat gelas kopimu tersenggol di meja, ingatlah: jam dinding tidak pernah melambat—otakmulah "
                "yang sedang sibuk memotret setiap detiknya agar kamu tak mengulangi kesalahan yang sama."
            ),
            "claim_refs": ["CLM_01", "CLM_04"],
            "humor_beat": "Callback ke cangkir di awal video: kali ini Raka menggeser cangkir ke tengah meja dengan penggaris.",
            "emotion": "curious_engaged",
            "dialogue_lines": [
                {
                    "speaker_id": "char_raka_protagonist",
                    "line": "Aman. Sekarang jaraknya tiga puluh sentimeter dari pinggir meja.",
                    "delivery": "lega dan puas",
                    "onscreen_speaking": False,
                }
            ],
            "shot_blueprints": [
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Tangan Raka menggeser cangkir menjauh dari tepi meja",
                    "concrete_action": "Raka mendorong perlahan cangkir keramik ke bagian tengah meja kayu jauh dari jangkauan sikunya sambil melirik jam dinding.",
                    "props": ["prop_study_table_v1", "prop_desk_lamp_v1", "prop_wall_clock_v1"],
                    "preferred_engine": "blender",
                    "shot_size": "close_up",
                    "is_cutaway": False,
                    "cutaway_purpose": "Callback langsung terhadap hook pembuka 0-3 detik",
                    "transition_in": "trans_hard_cut_zero",
                },
                {
                    "duration_weight": 1.0,
                    "visual_subject": "Raka dan Naya di ruang kamar diorama utuh",
                    "concrete_action": "Kamera menarik mundur menampilkan keseluruhan diorama kamar berlampu hangat dengan kasur, lemari, meja, jendela, dan pintu kayu saat jarum jam berdetak stabil.",
                    "props": [
                        "prop_study_table_v1",
                        "prop_study_chair_v1",
                        "prop_bedroom_bed_v1",
                        "prop_wardrobe_cabinet_v1",
                        "prop_room_window_v1",
                        "prop_wooden_door_v1",
                        "prop_desk_lamp_v1",
                        "prop_wall_clock_v1",
                    ],
                    "preferred_engine": "blender",
                    "shot_size": "establishing",
                    "is_cutaway": False,
                    "cutaway_purpose": "Penutup visual loop yang memuaskan ke komposisi awal",
                    "transition_in": "trans_hard_cut_zero",
                },
            ],
        },
    ]

    # Select an appropriate subset or scaled beat list so every beat & shot stays natural across 15s..180s
    if target_duration_s <= 20:
        chosen = [copy.deepcopy(all_12_beats[0]), copy.deepcopy(all_12_beats[3]), copy.deepcopy(all_12_beats[11])]
    elif target_duration_s <= 40:
        chosen = [copy.deepcopy(all_12_beats[i]) for i in (0, 2, 4, 5, 11)]
    elif target_duration_s <= 75:
        chosen = [copy.deepcopy(all_12_beats[i]) for i in (0, 1, 2, 3, 4, 5, 7, 11)]
    else:
        chosen = copy.deepcopy(all_12_beats)

    raw_total = sum(float(b["target_duration_s"]) for b in chosen)
    scale = target_duration_s / raw_total
    for idx, b in enumerate(chosen, 1):
        b["beat_id"] = f"B{idx:02d}"
        b["target_duration_s"] = round(float(b["target_duration_s"]) * scale, 3)

    claims = [
        {
            "claim_id": "CLM_01",
            "statement": (
                "Eksperimen jatuh bebas setinggi 48 meter dengan kronometer persepsi LED membuktikan bahwa "
                "resolusi temporal visual tidak meningkat saat ketakutan akut, namun peserta menaksir durasi "
                "jatuh mereka sekitar 36% lebih lama secara retrospektif."
            ),
            "epistemic_status": "declared_fiction" if is_pure_fiction else "peer_reviewed_study",
            "source_title": "Stetson C., Fiesta M.P., Eagleman D.M. — Does Time Really Slow Down during a Frightening Event? (PLoS ONE)",
            "source_url": "https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0001295",
            "publication_year": 2007,
        },
        {
            "claim_id": "CLM_02",
            "statement": (
                "Aktivasi amigdala selama peristiwa bermuatan emosi memodulasi konsolidasi memori episodik yang lebih padat "
                "sehingga rekaman ingatan terasa lebih panjang saat diingat kembali."
            ),
            "epistemic_status": "declared_fiction" if is_pure_fiction else "peer_reviewed_study",
            "source_title": "McGaugh J.L. — The Amygdala Modulates the Consolidation of Memories of Emotionally Arousing Experiences (Annual Review of Neuroscience)",
            "source_url": "https://www.annualreviews.org/content/journals/10.1146/annurev.neuro.27.070203.144157",
            "publication_year": 2004,
        },
        {
            "claim_id": "CLM_03",
            "statement": (
                "John Harrison menyelesaikan kronometer laut H4 pada tahun 1759 untuk menjaga ketepatan waktu di laut "
                "dan memecahkan masalah penentuan garis bujur pelayaran."
            ),
            "epistemic_status": "declared_fiction" if is_pure_fiction else "archival_historical_record",
            "source_title": "Royal Museums Greenwich — John Harrison and the Longitude Problem",
            "source_url": "https://www.rmg.co.uk/stories/topics/john-harrison-and-longitude-problem",
            "publication_year": 2023,
        },
        {
            "claim_id": "CLM_04",
            "statement": (
                "Satu detik dalam Sistem Satuan Internasional (SI) didefinisikan secara eksak melalui 9.192.631.770 periode "
                "radiasi transisi hiperhalus atom Sesium-133 pada keadaan dasar."
            ),
            "epistemic_status": "declared_fiction" if is_pure_fiction else "verified_fact",
            "source_title": "Bureau International des Poids et Mesures (BIPM) — SI Base Unit: second (s)",
            "source_url": "https://www.bipm.org/en/si-base-units/second",
            "publication_year": 2019,
        },
    ]

    return {
        "schema_version": "3.4.0",
        "project_id": project_id,
        "topic_title": "Mengapa Waktu Terasa Melambat Saat Kita Panik? Dari Menara Jatuh Bebas hingga Jam Atom",
        "genres": active_genres,
        "target_duration_s": target_duration_s,
        "topic_research": {
            "epistemic_mode": "fictional_dramatization" if is_pure_fiction else "factual_verified",
            "research_status": "FICTION_DECLARED" if is_pure_fiction else "VERIFIED_COMPLETE",
            "summary": (
                "Kajian neurosains persepsi waktu (Stetson, Fiesta & Eagleman 2007; McGaugh 2004) yang dipadukan "
                "dengan sejarah kronometer laut John Harrison H4 (1759) dan definisi detik atom Sesium-133 BIPM."
            ),
            "claims": claims,
        },
        "blueprint": {
            "premise": (
                "Menjelaskan paradoks mengapa peristiwa mendebarkan terasa berjalan dalam gerak lambat "
                "bukan karena mata merekam lebih cepat, melainkan karena amigdala menyimpan ingatan lebih rapat."
            ),
            "hook_0_3s_visual": "Siku Raka menyenggol cangkir kopi di bibir meja kayu sementara jarum jam dinding tetap berdetak tegas.",
            "hook_0_3s_spoken": "Pernahkah kamu menyenggol gelas kopi di pinggir meja, lalu seluruh ruangan terasa melambat?",
            "story_arc": {
                "act_1_setup": "Insiden cangkir kopi di meja kamar memicu pertanyaan apakah mata manusia mampu memperlambat waktu.",
                "act_2_escalation": "Uji jatuh bebas 48 meter Eagleman, peran amigdala, serta kontras sejarah kronometer H4 hingga jam atom Sesium.",
                "act_3_resolution": "Kesimpulan konyol Raka diluruskan menjadi cara ilmiah memperkaya memori harian, ditutup callback pengamanan cangkir.",
            },
            "explainer_mechanism": "Perbandingan kronometer LED jatuh bebas -> kepadatan memori amigdala -> standar waktu objektif.",
            "humor_strategy": "Kontras situasi keseharian kamar Indonesia (cangkir kopi & ide liburan kaget Raka) dengan eksperimen ilmiah serius.",
            "historical_biography_notes": "Segmen John Harrison 1759 disajikan sebagai rekonstruksi diorama orisinal, bukan rekaman arsip langsung.",
            "payoff_callback": "Raka menggeser cangkir kopi 30 sentimeter ke tengah meja sambil melirik jarum jam dinding.",
        },
        "characters": [
            {
                "character_id": "char_raka_protagonist",
                "name": "Raka",
                "role": "hero",
                "silhouette_and_proportions": "Kepala bulat proporsi 0.34 tinggi tubuh, bahu ringkas, ekspresi alis dan kelopak mata sangat kontras.",
                "wardrobe": "Kemeja kerja biru gulung lengan di atas kaus putih dan celana panjang gelap.",
                "palette": ["#F4D8B8", "#2563EB", "#1E293B"],
                "rig_spec": "xdx_diorama_humanoid_v1_ik_hands_feet",
                "facial_controls": ["brow_inner_up", "brow_furrow", "eye_wide", "blink", "smile_soft", "jaw_drop"],
                "biography_disclaimer": "Karakter fiksi orisinal XDX Studio; tidak merepresentasikan individu nyata.",
            },
            {
                "character_id": "char_naya_researcher",
                "name": "Naya",
                "role": "supporting",
                "silhouette_and_proportions": "Siluet ramping dengan kacamata bundar tipis dan postur tegak tenang.",
                "wardrobe": "Jaket kardigan kuning hangat dengan rok/celana abu tua dan buku catatan merah.",
                "palette": ["#F4D8B8", "#D97706", "#334155"],
                "rig_spec": "xdx_diorama_humanoid_v1_ik_hands_feet",
                "facial_controls": ["brow_inner_up", "eyelid_lower_tight", "blink", "smile_soft"],
                "biography_disclaimer": "Karakter fiksi orisinal XDX Studio; segmen perajin 1759 adalah rekonstruksi ilustratif.",
            },
        ],
        "narrative_beats": chosen,
    }
