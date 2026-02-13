# RLM MCP Codex Companion MVP Design

Tanggal: 2026-02-13  
Status: Approved in brainstorming

## 1. Tujuan

Membangun MCP server berbasis pola Recursive Language Models (RLM) untuk dipakai bersama Codex, dengan pendekatan **Thin MCP State Engine**:
- Server memegang state sesi, eksekusi REPL sandbox, guardrail, dan trace.
- Codex tetap bertindak sebagai orchestrator reasoning dan recursive loop.

Target MVP harus lulus tiga kategori sekaligus:
1. End-to-end loop,
2. Recursive pattern,
3. Governance minimum (step/runtime/budget).

## 2. Scope dan Non-Goals

### In Scope
- Primitive MCP tools untuk orkestrasi eksplisit oleh Codex.
- In-memory session state (tanpa persistence lintas restart).
- REPL sandbox Python terbatas.
- Guardrail: `max_steps`, `max_runtime_ms`, `budget_limit`.
- Trace per langkah dan finalization reason code.

### Non-Goals (MVP)
- Multi-tenant auth/authorization.
- Database persistence.
- Internal LLM orchestration di sisi server.
- Scheduler async kompleks.

## 3. Keputusan Arsitektur

### 3.1 Pendekatan Terpilih: Thin MCP State Engine

Alasan:
- Paling selaras dengan kebutuhan “dipakai bersama Codex langsung”.
- Scope MVP tetap fokus dan cepat divalidasi.
- Transparan untuk observasi trajectory rekursif.

Konsekuensi:
- Kualitas strategi dekomposisi sangat bergantung pada behavior Codex.
- Server wajib punya guardrail kuat karena loop dikendalikan eksternal.

### 3.2 Komponen

1. **MCP Transport Layer**
- Mengekspos primitive tools.
- Validasi payload dan mapping error standar.

2. **Session State Manager (In-Memory)**
- Menyimpan `session_id`, `context_text`, environment vars, counters, trace.
- Menyediakan operasi read/write atomic sederhana.

3. **REPL Sandbox Executor**
- Menjalankan kode Python terbatas.
- Timeout per eksekusi, builtins terbatas, import whitelist.
- Menulis output/stdout/stderr ke trace.

4. **Guardrail Controller**
- Evaluasi pre/post aksi:
  - batas langkah,
  - batas runtime sesi,
  - batas budget.
- Menghasilkan `finish_reason` deterministik.

5. **Finalization Handler**
- Menutup sesi dari `final_text` atau `final_var_name`.
- Mengembalikan ringkasan statistik sesi.

6. **Trace Logger**
- Event terstruktur per langkah (aksi, ringkasan input, outcome, counters).

## 4. Kontrak Tool MCP (Primitive)

### `init_context`
Tujuan: membuat sesi dan memuat context panjang.

Input:
- `context_text: string`
- `session_config?: { max_steps, max_runtime_ms, budget_limit }`

Output:
- `session_id`
- config aktif
- counters awal

### `run_repl`
Tujuan: eksekusi snippet Python di sandbox terhadap state sesi.

Input:
- `session_id`
- `code`

Output:
- `stdout`
- `stderr`
- `updated_vars_summary`
- `step_index`
- status guardrail

### `get_var`
Tujuan: baca variabel tertentu dari sesi.

Input:
- `session_id`
- `var_name`

Output:
- nilai terserialisasi (preview + truncation flag untuk nilai besar)
- metadata tipe

### `finalize`
Tujuan: menutup sesi dan mengembalikan jawaban final.

Input:
- `session_id`
- salah satu dari `final_text` atau `final_var_name`

Output:
- `final_answer`
- `finish_reason`
- statistik sesi (`steps`, `runtime_ms`, `budget_used`)

### `get_trace`
Tujuan: audit trajectory rekursif.

Input:
- `session_id`
- `from_step?`, `to_step?`

Output:
- daftar event trace terstruktur

## 5. Model Data In-Memory

Entity inti per sesi:
- `session_id: str`
- `context_text: str`
- `vars: dict[str, Any]`
- `created_at: monotonic/time`
- `step_index: int`
- `runtime_ms: int`
- `budget_used: int`
- `status: active|stopped|finalized`
- `finish_reason: optional[str]`
- `trace: list[TraceEvent]`

`TraceEvent` minimal:
- `step_index`
- `action` (`init_context`, `run_repl`, `get_var`, `finalize`)
- `timestamp`
- `summary`
- `guardrail_snapshot`
- `result_status`

## 6. Guardrail dan Safety

Guardrail wajib:
- `max_steps` hard stop.
- `max_runtime_ms` hard stop.
- `budget_limit` hard stop.

Safety sandbox:
- Tanpa filesystem/network by default.
- Import whitelist terbatas.
- Builtins terbatas.
- Timeout per call untuk mencegah infinite loop.

Error handling:
- Error eksekusi REPL tidak otomatis mematikan sesi.
- Sesi hanya berhenti saat hard guardrail atau finalization eksplisit.

## 7. Acceptance Criteria MVP

1. End-to-end loop lulus:
- `init_context -> run_repl (multi-step) -> finalize` berhasil.

2. Recursive pattern terbukti:
- Trace menunjukkan pola dekomposisi/iterasi/agregasi.

3. Governance aktif:
- Terdapat uji untuk `max_steps`, `timeout`, `budget_exceeded`.

4. Observability minimum:
- `get_trace` dan statistik finalize tersedia konsisten.

## 8. Risiko dan Mitigasi

1. Loop eksternal liar dari sisi Codex.
- Mitigasi: hard stop guardrail + reason code eksplisit.

2. Eksekusi Python berbahaya.
- Mitigasi: sandbox policy ketat + timeout + whitelist.

3. State drift antar langkah.
- Mitigasi: trace event per aksi dan serialisasi variabel konsisten.

4. Sulit debugging.
- Mitigasi: event trace terstruktur + counters yang mudah diinspeksi.

## 9. Rencana Transisi

Fase berikutnya adalah penulisan implementation plan detail (task-by-task, TDD-first), lalu eksekusi bertahap.
