# RLM MCP Codex Companion

MCP server Python untuk workflow Recursive Language Model (RLM) yang dipakai bersama Codex.

Tujuan server ini:
- memindahkan context panjang ke environment state,
- memberi primitive tools untuk loop rekursif,
- menjaga guardrail langkah/runtime/budget saat reasoning bertahap.

## Architecture Ringkas

- `src/rlm_mcp/service.py`: orchestration stateful session, guardrail, finalize.
- `src/rlm_mcp/sandbox.py`: eksekusi REPL Python terbatas.
- `src/rlm_mcp/server.py`: registrasi FastMCP tools `rlm_*` + input schema Pydantic.
- `bin/run-rlm-mcp.sh`: launcher stdio server untuk Codex CLI.

## Prerequisites

- Python `>= 3.11`
- Codex CLI terbaru
- Lingkungan shell yang bisa jalankan script launcher (contoh: WSL/Linux shell)

## Setup Dari Nol

### 1) Clone dan masuk repo

```bash
git clone https://github.com/z0zero/mcp-rlm.git ~/mcp-rlm
cd ~/mcp-rlm
```

### 2) Buat virtualenv dan install dependency

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

### 3) Verifikasi server bisa start

```bash
timeout 5s ./bin/run-rlm-mcp.sh; echo $?
```

Expected:
- Exit code `124` artinya server hidup dan dihentikan oleh timeout (normal untuk smoke test).

## Integrasi Dengan Codex CLI

Ada 2 cara: CLI command (disarankan) atau edit config manual.

### Opsi A - via `codex mcp add` (disarankan)

```bash
codex mcp add rlm -- ~/mcp-rlm/bin/run-rlm-mcp.sh
```

### Opsi B - edit `~/.codex/config.toml` manual

Tambahkan:

```toml
[mcp_servers.rlm]
command = "~/mcp-rlm/bin/run-rlm-mcp.sh"
startup_timeout_sec = 20.0
tool_timeout_sec = 60.0
enabled_tools = ["rlm_init_context", "rlm_run_repl", "rlm_get_var", "rlm_finalize", "rlm_get_trace"]
```

Lalu restart Codex CLI.

### Verifikasi registrasi MCP

```bash
codex mcp list
codex mcp get rlm
```

Expected:
- server `rlm` status `enabled`
- transport `stdio`
- command menunjuk `bin/run-rlm-mcp.sh`

## MCP Tools

Tool utama yang diekspos:

- `rlm_init_context`
  - Membuat session baru + memuat context panjang.
  - Input penting: `context_text`, `max_steps`, `max_runtime_ms`, `budget_limit`.
- `rlm_run_repl`
  - Menjalankan snippet Python pada environment session.
  - Input penting: `session_id`, `code`.
- `rlm_get_var`
  - Membaca variabel dari state session.
- `rlm_finalize`
  - Menutup session dengan `final_text` atau `final_var_name`.
- `rlm_get_trace`
  - Mengambil jejak langkah (debug trajectory rekursif).

Semua tool mendukung `response_format`:
- `json` (default)
- `markdown`

## Guardrails

Guardrail aktif di service:

- `max_steps`: membatasi jumlah langkah REPL.
- `max_runtime_ms`: batas waktu total sesi.
- `budget_limit`: batas budget proxy berbasis ukuran I/O.

Jika terlampaui, sesi berhenti dengan reason code (contoh: `max_steps`, `timeout`, `budget_exceeded`).

## Production Sandbox Mode (Container)

Default saat ini memakai subprocess terisolasi. Untuk production, aktifkan mode container:

```bash
export RLM_SANDBOX_MODE=container
export RLM_SANDBOX_CONTAINER_RUNTIME=docker
export RLM_SANDBOX_CONTAINER_IMAGE=python:3.12-alpine
```

Rekomendasi:
- Set `RLM_SANDBOX_MODE=container` di environment service yang menjalankan MCP server.
- Pastikan image sandbox tersedia di host/container registry.
- Secara default sandbox container dijalankan dengan:
  - `--network none`
  - `--read-only`
  - `--cap-drop ALL`
  - `--security-opt no-new-privileges`
  - `--pids-limit` + memory/cpu limit + tmpfs terbatas.

Catatan:
- Jika runtime container tidak tersedia, executor akan fallback ke mode subprocess (untuk local/dev compatibility).
- Untuk lingkungan production ketat, nonaktifkan fallback di level konfigurasi aplikasi (next hardening step).

## Cara Pakai Di Codex (Contoh Alur)

### 1) Inisialisasi context panjang

Contoh intent ke Codex:
- "Gunakan `rlm_init_context` dengan context berikut dan `max_steps=40`."

### 2) Jalankan loop rekursif

Contoh intent:
- "Pecah context jadi chunks lewat `rlm_run_repl`, proses tiap chunk, simpan agregat."

### 3) Inspeksi state

Contoh intent:
- "Cek variabel `summary_by_chunk` dengan `rlm_get_var`."

### 4) Finalisasi

Contoh intent:
- "Finalize dari variabel `final_answer` via `rlm_finalize`."

### 5) Audit trajectory

Contoh intent:
- "Ambil trace langkah 0-20 dengan `rlm_get_trace`."

## Troubleshooting

### `MCP startup failed: ... initialize response`

Langkah cek:

1. Pastikan dependency terpasang di `.venv`:

```bash
. .venv/bin/activate
python -m pip install -e .
```

2. Pastikan launcher path di config benar:
- `~/mcp-rlm/bin/run-rlm-mcp.sh`

3. Smoke test launcher:

```bash
timeout 5s ~/mcp-rlm/bin/run-rlm-mcp.sh; echo $?
```

4. Restart Codex CLI setelah update config/dependency.

### Tool timeout saat `rlm_run_repl`

- Kurangi ukuran `code` per step.
- Turunkan kompleksitas loop.
- Naikkan `tool_timeout_sec` seperlunya di config Codex.

### Session not found

- Gunakan `session_id` terbaru dari output `rlm_init_context`.
- Hindari finalize lalu reuse session yang sama.

## Running Tests

```bash
. .venv/bin/activate
PYTHONPATH=src pytest -v
```

## Catatan Operasional

- Server saat ini single-process in-memory (state hilang saat process restart).
- Cocok untuk MVP/dev workflow dengan Codex.
- Untuk penggunaan lebih luas, lanjutkan hardening sandbox (isolasi subprocess/container) sebelum production-like usage.
