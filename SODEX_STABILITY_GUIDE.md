# SoDEX Stability & Integration Guide (CRITICAL)

Dokumen ini berisi temuan teknis vital untuk menjaga stabilitas bot dan dashboard SoDEX. JANGAN mengubah logika di bawah ini tanpa verifikasi mendalam.

## 1. Sinkronisasi Nonce & clOrdID
*   **Aturan**: Timestamp pada `clOrdID` **WAJIB** sama persis dengan `X-API-Nonce` yang digunakan untuk tanda tangan (Signature).
*   **Implementasi**: Gunakan satu variabel `nonce = Date.now()` untuk kedua tujuan tersebut sekaligus.
*   **Gejala Error**: Jika tidak sinkron, bursa akan mengembalikan error `API key not found`.

## 2. Urutan Properti JSON (Strict Order)
Bursa SoDEX melakukan hashing pada string JSON mentah. Urutan properti dalam objek **sangat menentukan** validitas signature.

### A. Urutan Order Utama (Normal/Parent):
1. `clOrdID`
2. `modifier`
3. `side`
4. `type`
5. `timeInForce`
6. `price` (Opsional, tapi harus di posisi ini jika ada)
7. `quantity`
8. `reduceOnly`
9. `positionSide`

### B. Urutan Order TP/SL (Attached):
1. `clOrdID`
2. `modifier`
3. `side`
4. `type`
5. `timeInForce`
6. `quantity`
7. `stopPrice`
8. `stopType`
9. `triggerType`
10. `reduceOnly`
11. `positionSide`

## 3. Nilai Modifier
*   **`1` (NORMAL)**: Digunakan untuk order biasa tanpa TP/SL.
*   **`3` (BRACKET)**: **WAJIB** digunakan pada Order Utama jika di dalam batch tersebut terdapat TP atau SL.
*   **`4` (ATTACHED_STOP)**: Digunakan untuk order TP dan SL itu sendiri.

## 4. Konfigurasi Market Order
*   **Market Order (`type: 2`)**: Jangan mengirimkan parameter `price`. 
*   **Alasan**: Jika harga dikirim, bursa menganggapnya sebagai batasan slippage yang sangat ketat (IOC). Jika harga bergerak sedikit saja, order akan langsung dibatalkan (Instantly Cancelled).

## 5. Multi-User & SaaS Architecture (BYOK)
- **Bring Your Own Key (BYOK)**: Setiap user dapat memasukkan API Key Gemini dan OpenRouter mereka sendiri untuk menghindari global rate limits.
- **Parallel Execution**: Bot menggunakan `asyncio.create_task` untuk menganalisis banyak user secara bersamaan, memastikan tidak ada user yang harus mengantre.
- **Isolated State**: Wallet, profil risiko, dan riwayat trading setiap user terisolasi sepenuhnya di database.

## 6. Header Testnet
*   **Testnet**: Jangan mengirimkan header `X-API-Key`. Bursa mendeteksi konflik jika API Key dikirim bersamaan dengan tanda tangan custodial dari wallet.

## 7. Format Signature
*   Selalu gunakan fungsi `formatSodexSignature` untuk memastikan signature berakhir dengan `00` atau `01` (bukan `1b` atau `1c`).
