"""Write all enhanced sample documents and seed data for the RAG demo."""
import pathlib

BASE = pathlib.Path("D:/02_WORK/CLOUDERA/CLAUDE_CODE/demos/cloudera-ai-id-rag-demo/data/sample_docs")


def w(path, text):
    p = BASE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    print(f"  wrote {path} ({len(text):,} chars)")


# ─────────────────────────────────────────────────────────────────────────────
# TELCO DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────

w("telco/kebijakan_layanan_pelanggan.txt", """KEBIJAKAN LAYANAN PELANGGAN DAN SERVICE LEVEL AGREEMENT (SLA)
Nomor: TLC/CS/POL/001/2026 | Revisi: 3.2 | Berlaku: 1 Januari 2026
Ditetapkan oleh: Direksi PT Nusantara Telekomunikasi Tbk

BAB I - KETENTUAN UMUM

Pasal 1 - Definisi

1.1 Service Level Agreement (SLA) adalah komitmen tertulis yang mendefinisikan standar
    kualitas layanan minimum yang dijamin oleh perusahaan kepada pelanggan.
1.2 Churn adalah kondisi dimana pelanggan mengakhiri kontrak berlangganan secara aktif
    atau tidak memperpanjang kontrak yang habis masa berlakunya.
1.3 Churn Risk Score adalah nilai prediktif (skala 0-100) yang menggambarkan kemungkinan
    pelanggan akan churn dalam 90 hari ke depan:
    - Skor 0-30    : Risiko rendah
    - Skor 31-69   : Risiko menengah (pantau bulanan)
    - Skor 70-100  : Risiko tinggi (intervensi aktif wajib dalam 7 hari kerja)
1.4 Net Promoter Score (NPS): ukuran loyalitas pelanggan, skala -100 hingga +100.
1.5 First Call Resolution (FCR): persentase keluhan yang diselesaikan dalam kontak pertama.

BAB II - STANDAR KUALITAS JARINGAN

Pasal 2 - Ketersediaan Jaringan (Network Availability)

Ketersediaan jaringan minimum yang dijamin:
- 4G LTE : minimal 99,5% uptime per bulan (downtime maksimal 3,6 jam/bulan)
- 5G      : minimal 99,7% uptime per bulan (downtime maksimal 2,2 jam/bulan)
- 3G      : minimal 98,0% uptime per bulan

Batas utilisasi jaringan:
- Normal      : utilisasi 0-70% dari kapasitas
- Perhatian   : utilisasi 70-85% (monitoring intensif, rencana ekspansi dipercepat)
- Kritis       : utilisasi 85-95% (pembatasan penambahan pelanggan baru)
- Overcapacity: utilisasi lebih dari 95% (darurat jaringan, aktivasi cadangan wajib)

Pasal 3 - Kecepatan Data Minimum

Kecepatan unduhan minimum yang dijamin dalam SLA:
- Paket Starter (5 GB)  : minimal 5 Mbps rata-rata
- Paket Basic (20 GB)   : minimal 10 Mbps rata-rata
- Paket Standard (50 GB): minimal 20 Mbps rata-rata
- Paket Premium (100 GB): minimal 30 Mbps rata-rata
- Paket Unlimited        : minimal 20 Mbps (tanpa throttle selama FUP)
- Paket Enterprise       : sesuai kontrak individual, minimum 50 Mbps

BAB III - STANDAR LAYANAN PELANGGAN

Pasal 4 - Waktu Penanganan Keluhan

Waktu penyelesaian (ticket resolution time) berdasarkan tingkat keparahan:
- P1 Kritis (layanan mati total, lebih dari 500 pelanggan terdampak): 4 jam
- P2 Tinggi (degradasi signifikan, 100-500 pelanggan terdampak)     : 8 jam
- P3 Menengah (gangguan parsial, kurang dari 100 pelanggan)          : 24 jam
- P4 Rendah (pertanyaan, permintaan non-kritis)                      : 3 hari kerja
- P5 Informasi (saran, masukan umum)                                 : 5 hari kerja

Waktu respons pertama per kanal:
- Hotline 24/7 gangguan kritis : langsung (kurang dari 30 detik)
- Hotline 24/7 pertanyaan umum : kurang dari 2 menit
- Live chat aplikasi            : kurang dari 5 menit
- Email resmi                   : kurang dari 4 jam kerja
- Gerai GraPARI                : kurang dari 15 menit antrian
- Media sosial                  : kurang dari 1 jam

Pasal 5 - Target Kepuasan Pelanggan

- Customer Satisfaction Score (CSAT) minimum : 80% pelanggan puas atau sangat puas
- Net Promoter Score (NPS) target 2026        : minimal +35 poin
- First Call Resolution (FCR):
  * Pelanggan prabayar    : minimal 75%
  * Pelanggan pascabayar  : minimal 80%
  * Pelanggan korporasi   : minimal 85%

BAB IV - PROGRAM RETENSI PELANGGAN

Pasal 6 - Kriteria Eligibilitas Program Retensi

Program retensi aktif ditawarkan kepada pelanggan yang memenuhi semua kriteria berikut:
a. Masa berlangganan minimal 12 bulan berturut-turut
b. Tidak memiliki tunggakan pembayaran dalam 6 bulan terakhir
c. Churn risk score minimal 70 (risiko tinggi), ATAU
   kontrak akan berakhir dalam 60 hari ke depan dengan skor lebih dari 50

Pelanggan dengan skor di bawah 70 tidak memenuhi syarat program retensi aktif.

Pasal 7 - Intervensi Berdasarkan Churn Risk Score

- Skor 70-79  : Penawaran diskon perpanjangan 10-15%
- Skor 80-89  : Penawaran upgrade paket gratis + diskon 15-20%
- Skor 90-100 : Penawaran khusus (diskon 25-30% + bonus kuota + hadiah loyalitas)

Pasal 8 - Diskon Perpanjangan Kontrak

Syarat mendapatkan diskon perpanjangan:
a. Pelanggan pascabayar dengan masa berlangganan minimal 12 bulan
b. Status akun aktif tanpa tunggakan
c. Komitmen perpanjangan minimal 12 bulan ke depan
d. Diskon berlaku untuk tagihan bulanan, tidak untuk perangkat

Besaran diskon berdasarkan masa berlangganan kumulatif:
- 12-23 bulan    : diskon 10% dari tarif langganan bulanan
- 24-35 bulan    : diskon 15% dari tarif langganan bulanan
- 36-47 bulan    : diskon 20% dari tarif langganan bulanan
- 48 bulan ke atas: diskon 25% dari tarif langganan bulanan

Pasal 9 - Target Churn Rate Tahun 2026

Target churn rate bulanan yang tidak boleh terlampaui:
- Pelanggan prabayar  : maksimal 4,5% per bulan
- Pelanggan pascabayar: maksimal 1,8% per bulan
- Pelanggan korporasi : maksimal 0,8% per bulan
- Churn rate total    : maksimal 3,2% per bulan (weighted average)

BAB V - KOMPENSASI PELANGGARAN SLA

Pasal 10 - Kompensasi Gangguan Jaringan

Apabila perusahaan gagal memenuhi komitmen SLA ketersediaan jaringan, pelanggan
berhak mendapatkan kompensasi otomatis:
- Downtime 1-4 jam    : kredit kuota data 500 MB
- Downtime 4-12 jam   : kredit kuota data 2 GB + diskon tagihan 10%
- Downtime 12-24 jam  : kredit kuota data 5 GB + diskon tagihan 25%
- Downtime lebih dari 24 jam: kredit kuota 10 GB + diskon 50% + perpanjangan 1 bulan gratis

Pasal 11 - Kompensasi Keterlambatan Penanganan Keluhan

- Melewati target P1 : kredit Rp 50.000 ke akun pelanggan
- Melewati target P2 : kredit Rp 25.000 ke akun pelanggan
- Melewati target P3 : kredit Rp 10.000 ke akun pelanggan

BAB VI - PEMANTAUAN DAN PELAPORAN

Pasal 12 - KPI Bulanan

Divisi Customer Experience wajib melaporkan kepada Direksi setiap bulan:
- Tingkat churn per segmen dan perbandingan dengan target
- Distribusi churn risk score portofolio aktif
- CSAT, NPS, dan CES bulanan
- SLA achievement rate per kategori keluhan
- FCR per kanal layanan

Pasal 13 - Eskalasi

Apabila churn rate melampaui batas atau SLA achievement rate turun di bawah 90%
dalam dua bulan berturut-turut, Kepala Divisi Customer Experience wajib menyampaikan
rencana perbaikan kepada Direksi dalam 5 hari kerja.

Ditetapkan di Jakarta, 1 Januari 2026
Direktur Customer Experience: Dewi Pertiwi Rahayu
Direktur Utama               : Reza Firmansyah
""")

w("telco/regulasi_spektrum_frekuensi.txt", """PANDUAN OPERASIONAL JARINGAN DAN REGULASI FREKUENSI
Nomor: TLC/NET/OPS/002/2026 | Revisi: 2.1 | Berlaku: 1 Januari 2026
Ditetapkan oleh: Direktur Teknologi PT Nusantara Telekomunikasi Tbk

BAB I - ALOKASI FREKUENSI DAN LISENSI

Pasal 1 - Alokasi Spektrum yang Dimiliki

PT Nusantara Telekomunikasi Tbk mengelola spektrum frekuensi berikut sesuai
izin yang diterbitkan oleh Kementerian Komunikasi dan Informatika (Kominfo):

Frekuensi 4G LTE:
- 1800 MHz (Band 3)  : 20 MHz FDD, cakupan nasional
- 2100 MHz (Band 1)  : 15 MHz FDD, 32 kota besar
- 2300 MHz (Band 40) : 30 MHz TDD, area metropolitan

Frekuensi 5G:
- 3500 MHz (Band n78): 100 MHz TDD, tahap 1: 10 kota (2024-2026)
- 26 GHz (mmWave)    : 400 MHz, pilot hotspot Jakarta dan Surabaya

Frekuensi Legacy:
- 900 MHz (Band 8)   : 10 MHz FDD, cakupan rural dan pelosok
- 2100 MHz (3G/UMTS) : 5 MHz FDD, dijadwalkan sunset 2027

Pasal 2 - Kewajiban Cakupan (Coverage Obligation)

Sesuai izin dari Kominfo dan perjanjian Universal Service Obligation (USO):
- Cakupan 4G di seluruh ibu kota kabupaten/kota: 100% sebelum akhir 2025 (TERPENUHI)
- Cakupan 4G di kecamatan dengan populasi lebih dari 10.000 jiwa: 95% sebelum akhir 2026
- Cakupan 3G di seluruh wilayah daratan: 98% (terpenuhi per 2023)
- Cakupan 5G di 50 kota besar: 60% sebelum akhir 2028

BAB II - STANDAR TEKNIS JARINGAN

Pasal 3 - Kapasitas dan Utilisasi BTS

Standar kapasitas jaringan yang ditetapkan:
- Kapasitas BTS 4G/LTE standard: 50-150 Mbps (downlink) tergantung konfigurasi
- Kapasitas BTS 5G NR: 500-2000 Mbps (downlink) tergantung carrier aggregation
- Jumlah pengguna aktif per BTS maksimum: 200 pengguna simultan (QoS terjaga)

Threshold utilisasi yang memerlukan tindakan:
- Utilisasi 70-80% : Perencanaan kapasitas dipercepat, koordinasi dengan regional
- Utilisasi 80-85% : Optimasi frekuensi dan parameter jaringan wajib dilakukan
- Utilisasi 85-90% : Eskalasi ke NOC pusat, rencana pengadaan BTS tambahan
- Utilisasi lebih dari 90%: Status kritis, pembatasan aktivasi SIM baru di area terdampak

Posisi utilisasi jaringan per Maret 2026 (area prioritas pemantauan):
- Bali (Denpasar dan sekitarnya)   : 90,1% - STATUS KRITIS, eskalasi aktif
- Jawa Timur (Surabaya raya)       : 85,6% - Status kritis, rencana penambahan BTS
- Jawa Barat (Bandung metropolitan): 71,2% - Status perhatian, monitoring intensif
- Jakarta                           : 78,3% - Status perhatian, carrier aggregation aktif
- Jawa Tengah (Semarang)           : 68,9% - Normal
- Sumatera Utara (Medan)           : 55,0% - Normal, kapasitas memadai
- Sulawesi Selatan (Makassar)      : 48,2% - Normal
- Kalimantan Timur (Balikpapan)    : 42,7% - Normal

Pasal 4 - Penanganan Gangguan Jaringan

Klasifikasi gangguan dan prosedur penanganan:
- Gangguan Tingkat 1 (Minor): kurang dari 10% BTS terdampak di satu area
  Penanganan: tim lokal, target resolusi 4 jam
- Gangguan Tingkat 2 (Major): 10-30% BTS terdampak atau area kritis
  Penanganan: tim regional + NOC pusat, target resolusi 8 jam
- Gangguan Tingkat 3 (Catastrophic): lebih dari 30% BTS terdampak atau backbone down
  Penanganan: crisis team + Direksi, target resolusi 24 jam + laporan ke Kominfo

Pasal 5 - Pemeliharaan Jaringan Terjadwal

Jadwal pemeliharaan jaringan (planned maintenance):
- Pemeliharaan rutin BTS: maksimal 2 jam per bulan per BTS, antara 02:00-05:00 WIB
- Upgrade software jaringan: dijadwalkan akhir pekan, maksimal 4 jam
- Pemberitahuan pelanggan: minimal 72 jam sebelum pemeliharaan yang mempengaruhi layanan

BAB III - RENCANA EKSPANSI 5G

Pasal 6 - Roadmap 5G 2024-2028

Fase 1 (2024-2025) - SELESAI:
- Deployment 5G di Jakarta, Surabaya, Bandung, Medan, Makassar
- 1.250 BTS 5G aktif dengan kapasitas total 450 Gbps
- Cakupan populasi: 28% dari populasi nasional

Fase 2 (2026-2027) - BERJALAN:
- Ekspansi ke 30 kota tier-2: Semarang, Yogyakarta, Palembang, Balikpapan, dll.
- Target tambahan 3.000 BTS 5G
- Target investasi: Rp 8,5 triliun

Fase 3 (2028) - PLANNED:
- Ekspansi ke 50+ kota dan kawasan industri prioritas
- Integrasi dengan jaringan satelit LEO untuk daerah terpencil
- Target cakupan 5G: 60% populasi nasional

Pasal 7 - Persyaratan Kualitas Layanan 5G

Standar minimum layanan 5G yang harus dipenuhi:
- Kecepatan unduhan puncak        : minimal 1 Gbps di area urban
- Kecepatan unggahan puncak       : minimal 100 Mbps
- Latency end-to-end               : maksimal 10ms (ultra-low latency slice)
- Kepadatan koneksi                : minimal 1 juta perangkat per km persegi
- Ketersediaan jaringan 5G         : minimal 99,7% uptime bulanan

BAB IV - KEAMANAN DAN KEPATUHAN JARINGAN

Pasal 8 - Keamanan Infrastruktur

Standar keamanan yang diwajibkan untuk seluruh infrastruktur jaringan:
- Enkripsi end-to-end untuk semua komunikasi suara dan data (3GPP standar)
- Pemantauan keamanan siber 24/7 oleh Security Operations Center (SOC)
- Penetration testing jaringan inti: minimal 2 kali per tahun oleh pihak ketiga independen
- Backup power system: minimal 8 jam UPS + genset di setiap site kritis

Pasal 9 - Kepatuhan Regulasi

Laporan wajib kepada Kominfo dan BRTI:
- Laporan kualitas layanan (QoS) bulanan: paling lambat tanggal 15 bulan berikutnya
- Laporan gangguan jaringan signifikan: dalam 2 jam sejak kejadian
- Laporan penggunaan frekuensi tahunan: setiap 31 Januari

Denda pelanggaran regulasi frekuensi:
- Penggunaan frekuensi tanpa izin: Rp 500 juta - Rp 2 miliar per kasus
- Keterlambatan laporan QoS: Rp 100 juta per laporan yang terlambat
- Tidak memenuhi kewajiban cakupan: Rp 1 miliar per kuartal per wilayah

Ditetapkan di Jakarta, 1 Januari 2026
Direktur Teknologi: Hendra Kusuma Wijaya
""")

# ─────────────────────────────────────────────────────────────────────────────
# GOVERNMENT DOCUMENTS
# ─────────────────────────────────────────────────────────────────────────────

w("government/kebijakan_pelayanan_publik.txt", """KEBIJAKAN STANDAR PELAYANAN PUBLIK PEMERINTAH DAERAH
Nomor: PEMDA/YAN/POL/001/2026 | Revisi: 2.0 | Berlaku: 1 Januari 2026
Ditetapkan oleh: Sekretaris Daerah Pemerintah Kota Nusantara

BAB I - DASAR HUKUM DAN KETENTUAN UMUM

Pasal 1 - Dasar Hukum

a. Undang-Undang No. 25 Tahun 2009 tentang Pelayanan Publik
b. Undang-Undang No. 23 Tahun 2014 tentang Pemerintahan Daerah
c. Peraturan Pemerintah No. 96 Tahun 2012 tentang Pelaksanaan UU Pelayanan Publik
d. Permenpan-RB No. 15 Tahun 2014 tentang Pedoman Standar Pelayanan
e. Peraturan Daerah Kota Nusantara No. 4 Tahun 2023 tentang Standar Pelayanan Publik

Pasal 2 - Definisi

2.1 Standar Pelayanan adalah tolok ukur yang dipergunakan sebagai pedoman penyelenggaraan
    pelayanan publik dan acuan penilaian kualitas pelayanan.
2.2 Indeks Kepuasan Masyarakat (IKM) adalah data dan informasi tentang tingkat kepuasan
    masyarakat yang diperoleh dari hasil pengukuran secara kuantitatif dan kualitatif
    atas pendapat masyarakat dalam memperoleh pelayanan.
2.3 Maklumat Pelayanan adalah pernyataan tertulis dari penyelenggara pelayanan yang berisi
    komitmen untuk memberikan pelayanan sesuai standar yang telah ditetapkan.
2.4 Pengaduan adalah penyampaian ketidakpuasan yang disebabkan oleh adanya kerugian, baik
    yang sudah maupun yang akan dialami oleh pemohon layanan.

BAB II - STANDAR WAKTU PELAYANAN

Pasal 3 - Standar Waktu Penyelesaian Layanan Kependudukan

Layanan Disdukcapil (Dinas Kependudukan dan Pencatatan Sipil):

| Jenis Layanan              | Waktu Penyelesaian | Biaya      |
|---------------------------|--------------------|------------|
| KTP Elektronik (baru)     | 3 hari kerja       | Gratis     |
| KTP Elektronik (rusak)    | 1 hari kerja       | Gratis     |
| Kartu Keluarga (baru)     | 1 hari kerja       | Gratis     |
| Kartu Keluarga (perubahan)| 1 hari kerja       | Gratis     |
| Akta Kelahiran            | 1 hari kerja       | Gratis     |
| Akta Kematian             | 1 hari kerja       | Gratis     |
| Akta Perkawinan           | 3 hari kerja       | Rp 50.000  |
| Surat Pindah              | 1 hari kerja       | Gratis     |
| Legalisir dokumen         | Hari yang sama     | Gratis     |

Pasal 4 - Standar Waktu Layanan Perizinan

Layanan Dinas Perizinan Terpadu Satu Pintu (DPTSP):

| Jenis Izin                        | Waktu Penyelesaian | Biaya          |
|----------------------------------|--------------------|----------------|
| Nomor Induk Berusaha (NIB)       | Otomatis (online)  | Gratis         |
| Sertifikat Standar Usaha         | 3 hari kerja       | Sesuai PNBP    |
| IMB/PBG rumah tinggal            | 10 hari kerja      | Sesuai PNBP    |
| IMB/PBG non-rumah tinggal        | 14 hari kerja      | Sesuai PNBP    |
| Izin Lingkungan (UKL-UPL)        | 21 hari kerja      | Sesuai PNBP    |
| Sertifikat Layak Fungsi (SLF)    | 7 hari kerja       | Sesuai PNBP    |
| Izin Usaha Perdagangan (IUP)     | 3 hari kerja       | Gratis         |
| Izin Keramaian                   | 3 hari kerja       | Rp 250.000     |

Pasal 5 - Standar Waktu Layanan Sosial dan Kemasyarakatan

| Jenis Layanan                     | Waktu Penyelesaian | Biaya   |
|----------------------------------|--------------------|---------|
| Surat Keterangan Tidak Mampu (SKTM)| 1 hari kerja    | Gratis  |
| Rekomendasi Beasiswa              | 3 hari kerja       | Gratis  |
| Surat Keterangan Domisili         | Hari yang sama     | Gratis  |
| Bantuan Sosial (verifikasi)       | 14 hari kerja      | Gratis  |

Pasal 6 - Kompensasi Keterlambatan Pelayanan

Apabila pelayanan melampaui waktu standar yang ditetapkan, pemohon berhak mendapatkan:
a. Permintaan maaf resmi dari kepala unit pelayanan
b. Prioritas antrian pada kunjungan berikutnya
c. Layanan antar dokumen ke alamat pemohon (untuk keterlambatan lebih dari 2x standar)
d. Laporan eskalasi ke atasan kepala unit untuk keterlambatan sistemik

Untuk layanan IMB/PBG yang terlambat:
- Keterlambatan 1-5 hari  : diskon biaya PNBP 10%
- Keterlambatan 6-14 hari : diskon biaya PNBP 25%
- Keterlambatan lebih dari 14 hari: diskon biaya PNBP 50% + investigasi internal

BAB III - STANDAR INDEKS KEPUASAN MASYARAKAT

Pasal 7 - Target IKM dan Standar Kepuasan

Target Indeks Kepuasan Masyarakat (IKM) tahun 2026 per unit layanan:

| Unit Layanan           | Target IKM Minimum | Nilai Mutu Minimum |
|-----------------------|--------------------|---------------------|
| Disdukcapil            | 82,0 (Baik)        | B                   |
| Dinas Perizinan (DPTSP)| 80,0 (Baik)        | B                   |
| Dinas Sosial           | 83,0 (Baik)        | B                   |
| Kecamatan              | 81,0 (Baik)        | B                   |
| RSUD Kota              | 80,0 (Baik)        | B                   |
| Target rata-rata kota  | 81,5 (Baik)        | B                   |

Konversi nilai IKM ke kategori mutu:
- IKM 88,31 - 100,00 : Mutu A (Sangat Baik)
- IKM 76,61 - 88,30  : Mutu B (Baik)
- IKM 65,00 - 76,60  : Mutu C (Kurang Baik)
- IKM kurang dari 65,00: Mutu D (Tidak Baik) - wajib rencana perbaikan

Pasal 8 - Pengukuran IKM

IKM diukur berdasarkan 9 unsur sesuai Permenpan-RB No. 14 Tahun 2017:
1. Persyaratan     - kemudahan dan kejelasan persyaratan
2. Prosedur        - kemudahan dan kejelasan alur pelayanan
3. Waktu           - kesesuaian waktu dengan standar yang ditetapkan
4. Biaya           - kesesuaian biaya dengan ketentuan
5. Produk          - kesesuaian jenis layanan yang diterima
6. Kompetensi      - kemampuan petugas dalam pelayanan
7. Perilaku        - kesopanan dan keramahan petugas
8. Penanganan pengaduan - kemampuan menangani pengaduan
9. Sarana dan prasarana - kenyamanan lingkungan pelayanan

BAB IV - KANAL PENGADUAN DAN PENANGANANNYA

Pasal 9 - Kanal Pengaduan Resmi

Kanal pengaduan yang tersedia untuk masyarakat:
a. Aplikasi NusantaraKu (mobile app Android/iOS):
   - Respons pertama: kurang dari 24 jam
   - Tersedia 24/7, integrasi langsung dengan SKPD terkait

b. Hotline Kota 1500-XXX:
   - Layanan hari kerja: Senin-Jumat 08:00-16:00 WIB
   - Darurat infrastruktur: 24/7

c. Loket Pengaduan di Balai Kota:
   - Jam operasional: Senin-Jumat 08:00-15:00 WIB
   - Petugas khusus penanganan pengaduan

d. Email resmi: pengaduan@nusantarakota.go.id
   - Respons awal: kurang dari 2 hari kerja

e. Surat resmi ke kantor Ombudsman Kota:
   - Untuk pengaduan yang tidak terselesaikan di tingkat SKPD

Pasal 10 - Prosedur Penanganan Pengaduan

Tahapan penanganan pengaduan:
1. Registrasi dan verifikasi: 1 hari kerja
2. Klarifikasi ke unit terkait: 3 hari kerja
3. Investigasi dan analisis: 5-10 hari kerja (tergantung kompleksitas)
4. Respons kepada pelapor: paling lambat 14 hari kerja sejak pengaduan diterima
5. Monitoring tindak lanjut: 30 hari setelah respons

Batas waktu penyelesaian pengaduan berdasarkan kategori:
- Pengaduan administrasi (dokumen, waktu proses): 7 hari kerja
- Pengaduan perilaku petugas: 10 hari kerja
- Pengaduan kebijakan/regulasi: 21 hari kerja
- Pengaduan lintas SKPD: 30 hari kerja

BAB V - MEKANISME KONTROL DAN EVALUASI

Pasal 11 - Pelaporan Rutin

Unit layanan wajib menyampaikan laporan kepada Sekretaris Daerah:
- Laporan kinerja pelayanan bulanan (IKM, volume permohonan, tingkat tepat waktu)
- Laporan pengaduan bulanan (jumlah, jenis, status penyelesaian)
- Laporan tahunan evaluasi standar pelayanan

Pasal 12 - Sanksi Unit Pelayanan

Unit layanan yang secara konsisten tidak memenuhi standar:
- Peringatan tertulis pertama: IKM di bawah target 2 bulan berturut-turut
- Peringatan tertulis kedua dan rencana perbaikan 30 hari: IKM di bawah target 3 bulan
- Audit pelayanan eksternal: IKM di bawah target 4 bulan atau banyak pengaduan
- Evaluasi kepemimpinan unit: IKM di bawah target 6 bulan berturut-turut

Ditetapkan di Kota Nusantara, 1 Januari 2026
Sekretaris Daerah: Dr. Andi Prasetyo, M.Si.
Walikota         : H. Bambang Triyono, S.H., M.H.
""")

w("government/regulasi_anggaran_daerah.txt", """REGULASI PENGELOLAAN ANGGARAN PENDAPATAN DAN BELANJA DAERAH (APBD)
Nomor: PEMDA/KEU/REG/001/2026 | Berlaku: 1 Januari 2026
Ditetapkan oleh: Kepala Badan Pengelola Keuangan Daerah (BPKD) Kota Nusantara

BAB I - DASAR HUKUM DAN KETENTUAN UMUM

Pasal 1 - Dasar Hukum

a. Undang-Undang No. 17 Tahun 2003 tentang Keuangan Negara
b. Undang-Undang No. 1 Tahun 2004 tentang Perbendaharaan Negara
c. Undang-Undang No. 23 Tahun 2014 tentang Pemerintahan Daerah
d. PP No. 12 Tahun 2019 tentang Pengelolaan Keuangan Daerah
e. Permendagri No. 77 Tahun 2020 tentang Pedoman Teknis Pengelolaan Keuangan Daerah
f. Peraturan Daerah Kota Nusantara No. 1 Tahun 2026 tentang APBD TA 2026

Pasal 2 - Definisi

2.1 APBD adalah rencana keuangan tahunan pemerintah daerah yang ditetapkan dengan
    peraturan daerah.
2.2 Pagu Anggaran adalah batas maksimum anggaran yang diizinkan untuk suatu program
    atau kegiatan dalam satu tahun anggaran.
2.3 Realisasi Anggaran adalah jumlah belanja yang benar-benar telah dikeluarkan dan
    dipertanggungjawabkan dalam suatu periode.
2.4 Serapan Anggaran adalah persentase realisasi terhadap pagu anggaran yang ditetapkan.
2.5 Satuan Kerja Perangkat Daerah (SKPD) adalah unit organisasi pemerintah daerah yang
    bertanggung jawab atas pelaksanaan program dan kegiatan tertentu.

BAB II - STRUKTUR APBD KOTA NUSANTARA TAHUN 2026

Pasal 3 - Total APBD dan Distribusi

Total APBD Kota Nusantara Tahun Anggaran 2026:
- Total Pendapatan Daerah : Rp 4,82 triliun
- Total Belanja Daerah    : Rp 5,15 triliun
- Pembiayaan Netto        : Rp 330 miliar (dari SILPA 2025)

Komposisi Pendapatan:
- PAD (Pajak Daerah, Retribusi, dll.) : Rp 1,95 triliun (40,5%)
- Transfer Pusat (DAU, DAK, DBH)      : Rp 2,58 triliun (53,5%)
- Lain-lain Pendapatan Sah            : Rp 290 miliar (6,0%)

Pasal 4 - Alokasi Belanja per Urusan

| Urusan/SKPD                    | Pagu 2026          | Pagu 2025          | Perubahan  |
|-------------------------------|--------------------|--------------------|------------|
| Pendidikan                     | Rp 1.250 miliar    | Rp 1.150 miliar    | +8,7%      |
| Kesehatan                      | Rp 820 miliar      | Rp 760 miliar      | +7,9%      |
| Pekerjaan Umum dan PR          | Rp 680 miliar      | Rp 720 miliar      | -5,6%      |
| Perhubungan                    | Rp 540 miliar      | Rp 500 miliar      | +8,0%      |
| Sosial                         | Rp 310 miliar      | Rp 290 miliar      | +6,9%      |
| Lingkungan Hidup (DLHK)        | Rp 275 miliar      | Rp 250 miliar      | +10,0%     |
| BPBD (Penanggulangan Bencana)  | Rp 185 miliar      | Rp 160 miliar      | +15,6%     |
| Perizinan (DPTSP)              | Rp 95 miliar       | Rp 85 miliar       | +11,8%     |
| Administrasi Pemerintahan      | Rp 620 miliar      | Rp 590 miliar      | +5,1%      |
| Lainnya                        | Rp 375 miliar      | Rp 340 miliar      | +10,3%     |

BAB III - SIKLUS PENGANGGARAN DAN PELAKSANAAN

Pasal 5 - Jadwal Siklus Anggaran

Jadwal baku pelaksanaan anggaran tahun 2026:

Perencanaan dan Penetapan:
- Musrenbang Kelurahan     : Januari-Februari (selesai)
- Musrenbang Kecamatan     : Februari (selesai)
- Musrenbang Kota          : Maret (selesai)
- Penetapan RKPD           : Mei 2025 (selesai)
- Penetapan APBD 2026      : Desember 2025 (selesai)

Pelaksanaan:
- Penyusunan DPA-SKPD      : Januari 2026 (selesai)
- Pelaksanaan Anggaran TW1 : Januari-Maret 2026
- Evaluasi TW1             : April 2026
- Pelaksanaan Anggaran TW2 : April-Juni 2026
- Evaluasi TW2 + APBD Perubahan: Juli-Agustus 2026
- Pelaksanaan TW3          : Juli-September 2026
- Pelaksanaan TW4          : Oktober-Desember 2026

Pertanggungjawaban:
- Penyusunan Laporan Keuangan: Januari-Februari 2027
- Audit BPK                : Maret-Mei 2027
- Penetapan Perda LKPD     : Juli 2027

Pasal 6 - Target Serapan Anggaran Triwulanan

Target serapan anggaran kumulatif yang ditetapkan Walikota:
| Triwulan | Target Serapan Kumulatif | Batas Minimum   |
|---------|--------------------------|-----------------|
| TW1     | 20% dari pagu            | 15%             |
| TW2     | 45% dari pagu            | 38%             |
| TW3     | 70% dari pagu            | 60%             |
| TW4     | 95% dari pagu            | 85%             |

Catatan: Target minimum adalah batas yang tidak boleh dilampaui ke bawah.
SKPD yang tidak mencapai target minimum wajib menyampaikan laporan dan
rencana percepatan kepada TAPD dalam 5 hari kerja.

BAB IV - KETENTUAN PENGENDALIAN DAN SANKSI

Pasal 7 - Mekanisme Monitoring

Monitoring realisasi anggaran dilaksanakan oleh:
a. Internal SKPD: setiap 2 minggu oleh Kepala SKPD
b. BPKD: bulanan, laporan ke Sekretaris Daerah
c. Inspektorat Daerah: kuartalan, audit kinerja anggaran
d. TAPD (Tim Anggaran Pemerintah Daerah): evaluasi komprehensif per triwulan

Pasal 8 - Sanksi Serapan Rendah

SKPD yang realisasi anggarannya rendah dikenakan sanksi progresif:

Serapan di bawah target minimum TW3 (kurang dari 60% pagu):
- Pemanggilan Kepala SKPD oleh Sekretaris Daerah
- Kewajiban menyerahkan rencana akselerasi anggaran dalam 5 hari kerja
- Pembatasan pengajuan anggaran tambahan pada tahun berikutnya

Serapan akhir tahun di bawah 75% pagu (melampaui ambang penalti):
- Pengembalian sisa anggaran ke kas daerah (wajib, sesuai peraturan perundangan)
- Pemotongan pagu anggaran tahun berikutnya sebesar 2x kelebihan dari batas minimum
  Contoh: serapan 65% (kurang 10% dari batas 75%) maka pagu tahun depan dipotong 20%
- Evaluasi kinerja Kepala SKPD oleh Walikota
- Rekomendasi Inspektorat untuk pemeriksaan lebih lanjut jika ada indikasi penyimpangan

Serapan akhir tahun di bawah 60% pagu (serapan sangat rendah):
- Seluruh sanksi di atas berlaku
- Audit khusus oleh Inspektorat dalam 30 hari setelah tutup buku
- Laporan kepada BPK dan DPRD
- Evaluasi kelembagaan SKPD (potensi merger atau restrukturisasi)

Pasal 9 - Efisiensi dan Penghematan

SKPD yang berhasil melaksanakan program dengan serapan 90-100% dan mencapai
target kinerja (output dan outcome) mendapatkan:
- Reward berupa prioritas dalam perencanaan anggaran tahun berikutnya
- Tambahan insentif kinerja ASN sesuai regulasi yang berlaku
- Penghargaan Walikota untuk unit dengan kinerja anggaran terbaik

Pasal 10 - Pelaporan Keuangan

Laporan keuangan wajib yang dihasilkan SKPD:
- Laporan Realisasi Anggaran (LRA): bulanan, paling lambat tanggal 10 bulan berikutnya
- Laporan Operasional (LO): triwulanan
- Laporan Arus Kas (LAK): bulanan untuk SKPD yang mengelola bendahara penerimaan/pengeluaran
- Neraca: semesteran
- Catatan atas Laporan Keuangan (CaLK): tahunan

Ditetapkan di Kota Nusantara, 1 Januari 2026
Kepala BPKD   : Dra. Sri Wahyuni, M.M., Ak., CA
Sekretaris Daerah: Dr. Andi Prasetyo, M.Si.
""")

print("\nAll documents written successfully.")
