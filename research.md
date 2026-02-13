# Research Notes: Recursive Language Models (RLM) untuk Target MCP Server

Tanggal riset: 13 Februari 2026  
Sumber utama (wajib): https://arxiv.org/pdf/2512.24601  
Versi paper yang dirujuk: arXiv v2 (revisi 28 Jan 2026)

## 1) Ringkasan Eksekutif

Paper ini memperkenalkan **Recursive Language Models (RLM)** sebagai *inference-time scaffold*:
- Prompt panjang **tidak** langsung dimasukkan ke context window model.
- Prompt dipindahkan ke **environment eksternal** (contoh: variabel `context` di Python REPL).
- Model menulis kode untuk:
  1. inspeksi konteks,
  2. dekomposisi masalah,
  3. melakukan *sub-call* model secara rekursif,
  4. menyimpan hasil antar-langkah dalam state environment.

Intinya: RLM memindahkan bottleneck dari “muat semua token ke transformer” menjadi “orchestration simbolik + tool use + recursive querying”.

## 2) Masalah yang Disasar Paper

Paper menyorot dua masalah utama LLM long-context:
- **Keterbatasan context window fisik**.
- **Context rot**: kualitas menurun saat konteks makin panjang, bahkan pada model frontier.

Mereka mengusulkan bahwa performa long-context tidak hanya fungsi panjang input, tapi juga fungsi **kompleksitas tugas terhadap panjang input** (roughly constant / linear / quadratic).

## 3) Konsep Inti RLM

### 3.1 Abstraksi

RLM tetap punya antarmuka seperti LLM biasa (string in, string out), tetapi secara internal:
- Membuat environment REPL.
- Menaruh prompt user sebagai objek data (mis. `context`) di environment.
- Memberi model kemampuan menjalankan kode + memanggil sub-LLM (`llm_query`) pada potongan konteks terprogram.

### 3.2 Mekanisme eksekusi (operasional)

Pola loop yang dideskripsikan paper:
1. Root LM menerima query + metadata environment.
2. Root LM memilih aksi:
   - eksekusi kode REPL,
   - atau memanggil sub-LLM pada chunk/subtask,
   - atau finalisasi jawaban.
3. Output eksekusi/sub-call kembali ke environment (variabel/buffer).
4. Root LM melanjutkan iterasi berdasarkan state terbaru.
5. Berhenti saat model mengeluarkan jawaban final (`FINAL(...)` atau `FINAL_VAR(...)` pada setup paper).

### 3.3 Intuisi kenapa ini bekerja

- Model bisa **selektif membaca** bagian relevan konteks, bukan ingest semua token.
- Dekomposisi lewat *sub-call* membuat reasoning chain praktis “lebih panjang dari context window call tunggal”.
- State persist di environment memungkinkan komputasi bertahap dan agregasi antar-langkah.

## 4) Setup Eksperimen yang Relevan

### 4.1 Tugas yang dievaluasi

Paper mengevaluasi 4 benchmark dengan profil kompleksitas berbeda:
- **S-NIAH** (roughly constant information requirement).
- **BrowseComp-Plus (1K docs)** (multi-hop dokumen besar, 6M-11M token input).
- **OOLONG** (linear information density).
- **OOLONG-Pairs** (quadratic-style aggregation).
- Plus **LongBench-v2 CodeQA** untuk code-repository understanding.

### 4.2 Metode pembanding

- Base model langsung.
- Summary/compaction agent.
- CodeAct (+ BM25 retriever).
- RLM dengan REPL (penuh).
- RLM REPL tanpa sub-calls (ablation).

## 5) Temuan Empiris Utama

Berdasarkan Table 1 paper:

### 5.1 Hasil utama GPT-5

- **BrowseComp+**: Base `0.00*`, Summary `70.47`, RLM `91.33`.
- **OOLONG**: Base `44.00`, RLM `56.50`.
- **OOLONG-Pairs**: Base `0.04`, RLM `58.00`.
- **CodeQA**: Base `24.00*`, RLM `62.00`.

Interpretasi: RLM sangat unggul pada setting input sangat panjang / information-dense, termasuk kasus di mana base model mentok limit konteks (`*`).

### 5.2 Hasil utama Qwen3-Coder-480B

- **BrowseComp+**: Base `0.00*`, RLM `44.66`, RLM(no sub-calls) `46.00`.
- **OOLONG**: Base `36.00`, RLM `48.00`, RLM(no sub-calls) `43.50`.
- **OOLONG-Pairs**: Base `0.06`, RLM `23.11`, RLM(no sub-calls) `17.34`.
- **CodeQA**: Base `20.00*`, RLM `56.00`, RLM(no sub-calls) `66.00`.

Interpretasi: komponen REPL saja sudah memberi lompatan besar terhadap base; komponen sub-call sangat penting di task information-dense (contoh OOLONG/OOLONG-Pairs), tapi tidak selalu dominan di semua benchmark.

### 5.3 Biaya dan runtime

- Median cost RLM dapat sebanding atau lebih murah dibanding base call pada beberapa setup.
- Distribusi cost/runtime RLM **high variance** (tail panjang) karena panjang trajektori berbeda-beda.
- Implementasi paper masih memakai sub-call sinkron/blokir; penulis eksplisit menyebut async sebagai peluang optimasi besar.

## 6) Pola Trajektori RLM yang Muncul (Penting untuk Arsitektur)

Paper menunjukkan pola praktis berikut:
- **Filtering by code + prior model**: regex/probing untuk narrowing search space.
- **Chunking + recursive sub-calls**: chunk seragam/berbasis struktur, lalu panggil sub-LLM per chunk.
- **Verification via sub-calls**: dipakai untuk validasi jawaban, kadang membantu, kadang boros.
- **Long-output via environment variables**: hasil subtask ditaruh di variabel lalu dijahit menjadi output final.

Insight kunci: kemampuan RLM bukan hanya “bisa baca panjang”, tapi juga “bisa mengelola state kerja” di luar token stream.

## 7) Keterbatasan yang Diakui Paper

- Implementasi sinkron membuat runtime bisa lambat.
- Batas recursion depth pada eksperimen (mereka menyebut depth konservatif; sub-calls adalah LM).
- Model yang coding/tool-use capability-nya lemah kurang efektif sebagai RLM.
- Pemisahan “jawaban final” vs “lanjut berpikir” bisa rapuh jika hanya lewat format prompt/tag.
- Potensi over-calling sub-LLM (khusus model tertentu) meningkatkan cost drastis.

## 8) Implikasi Langsung ke Desain MCP Server (Tanpa Koding)

Untuk target membangun MCP server bergaya RLM, paper mengarah ke kebutuhan arsitektural berikut:

### 8.1 Komponen wajib

1. **Session/State Manager**
- Menyimpan context besar sebagai objek environment (bukan prompt penuh per turn).
- Menyimpan variabel kerja/buffer hasil intermediate.

2. **REPL Sandbox Executor**
- Eksekusi kode terisolasi, timeout, batas memori, dan kebijakan import ketat.
- Semua side effects harus tercatat (auditability/traceability).

3. **Recursive Call Orchestrator**
- API sub-call model dengan depth budget, token budget, dan branching control.
- Mendukung strategi batch chunk agar tidak meledak jumlah call.

4. **Trajectory Controller**
- Loop observe-act sampai final answer.
- Stop conditions: max steps, max runtime, budget cap, confidence/finalization rules.

5. **Cost/Runtime Governor**
- Real-time accounting biaya/token/waktu per session.
- Circuit breaker untuk outlier trajektori.

6. **Finalization Protocol**
- Kontrak output final yang robust (lebih baik dari sekadar tag raw text).
- Mekanisme fallback saat model gagal finalize.

### 8.2 Prinsip desain dari paper yang sebaiknya dipertahankan

- **Offload prompt ke environment state** sebagai prinsip pertama.
- **Biarkan model memilih dekomposisi** (task-agnostic), tapi dengan guardrail biaya.
- **Sub-call opsional namun kritikal** untuk task information-dense.
- **Pertahankan state mutable antar-langkah** untuk agregasi dan output panjang.

### 8.3 Risiko implementasi MCP yang perlu diantisipasi sejak awal

- Loop rekursif tak produktif (biaya tinggi, answer terlambat).
- Over-fragmented sub-calls (thousands of calls) pada model tertentu.
- Drift antara state environment dan jawaban final.
- Dependensi kuat pada kualitas coding behavior model root.

## 9) Kesimpulan Riset

Dari paper ini, RLM bukan sekadar trik prompting, melainkan perubahan **unit komputasi inference**:
- dari “sekali forward pass atas prompt panjang”
- menjadi “program eksekusi bertahap atas state eksternal + recursive LM calls”.

Untuk tujuanmu (MCP server RLM), fondasi ilmiah paling kuat dari paper adalah:
1. prompt harus jadi objek environment,
2. model harus diberi aksi inspeksi/dekomposisi/state update,
3. recursive sub-call perlu diatur oleh budget-aware orchestrator,
4. evaluasi sukses harus menimbang akurasi **dan** distribusi biaya/runtime (bukan mean saja).

## Referensi

- Paper PDF (utama): https://arxiv.org/pdf/2512.24601
- Halaman arXiv (metadata v2, 28 Jan 2026): https://arxiv.org/abs/2512.24601
- HTML paper (render arXiv Labs, dipakai untuk verifikasi bagian tertentu): https://ar5iv.org/html/2512.24601v2
