# RLM MCP Codex Companion

MCP server Python untuk workflow Recursive Language Models (RLM) bersama Codex.
Server ini menyediakan primitive tools agar context panjang disimpan di state session, lalu Codex menjalankan loop REPL rekursif secara bertahap.

## Status Project Saat Ini

- Versi paket: `0.1.0`
- Session store: in-memory (state hilang saat process restart)
- Tool MCP aktif: `rlm_init_context`, `rlm_run_repl`, `rlm_get_var`, `rlm_finalize`, `rlm_get_trace`
- Guardrail aktif: langkah, runtime, budget
- Sandbox tersedia dalam 2 mode: `subprocess` (default) dan `container`

## Arsitektur Ringkas

- `src/rlm_mcp/server.py`
  Menyediakan FastMCP app, schema input (Pydantic), dan registrasi tool `rlm_*`.
- `src/rlm_mcp/service.py`
  Orkestrasi session stateful: init, run REPL, get var, finalize, trace.
- `src/rlm_mcp/sandbox.py`
  Eksekusi kode Python terisolasi dengan limit resource + allowlist import.
- `src/rlm_mcp/guardrails.py`
  Evaluasi stop condition `max_steps`, `timeout`, `budget_exceeded`.
- `src/rlm_mcp/session_store.py`
  In-memory store untuk `SessionState`.
- `bin/run-rlm-mcp.sh`
  Launcher stdio yang dipakai Codex CLI.

## Prerequisites

- Python `>= 3.11`
- Codex CLI
- Shell Linux/WSL/macOS (untuk menjalankan launcher script)

## Setup

### 1) Clone repository

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

### 3) Smoke test server launcher

```bash
timeout 5s ./bin/run-rlm-mcp.sh; echo $?
```

Expected:
- `124` artinya server berhasil start dan dihentikan oleh `timeout` (normal untuk stdio server).

Catatan penting:
- `bin/run-rlm-mcp.sh` saat ini memakai `REPO_DIR` hardcoded.
- Jika path clone kamu berbeda, sesuaikan nilai `REPO_DIR` di script tersebut terlebih dahulu.

## Integrasi Dengan Codex CLI

### Opsi A: `codex mcp add` (disarankan)

```bash
codex mcp add rlm -- ~/mcp-rlm/bin/run-rlm-mcp.sh
```

### Opsi B: edit `~/.codex/config.toml` manual

```toml
[mcp_servers.rlm]
command = "/home/<username>/mcp-rlm/bin/run-rlm-mcp.sh"
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

Pastikan:
- server `rlm` terdaftar `enabled`
- transport `stdio`
- command menunjuk launcher yang benar

## MCP Tools

- `rlm_init_context`
  Membuat session baru dan memuat `context_text`.
  Input config: `max_steps`, `max_runtime_ms`, `budget_limit`.
- `rlm_run_repl`
  Menjalankan snippet Python (`code`) terhadap environment session.
- `rlm_get_var`
  Membaca satu variabel session (`var_name`).
- `rlm_finalize`
  Menutup session menggunakan `final_text` atau `final_var_name`.
- `rlm_get_trace`
  Mengambil jejak langkah untuk debugging trajectory.

Semua tool mendukung `response_format`:
- `json` (default)
- `markdown`

## Guardrails

Guardrail dievaluasi setiap langkah:

- `max_steps`: stop jika `step_index >= max_steps`
- `max_runtime_ms`: stop jika runtime session melewati batas
- `budget_limit`: stop jika akumulasi budget I/O melampaui limit

Jika stop terjadi, `guardrail_stop` akan berisi salah satu nilai:
- `max_steps`
- `timeout`
- `budget_exceeded`

## Sandbox Dan Isolasi

### Mode default: `subprocess`

- Worker Python dijalankan terisolasi (`python -I -S`)
- Builtins dibatasi
- Import dibatasi ke allowlist:
  - `math`, `statistics`, `re`, `json`, `datetime`, `itertools`, `functools`, `collections`
- Resource limit aktif:
  - CPU time
  - memory limit
  - file descriptor limit
  - output truncation limit

### Mode production: `container`

Aktifkan via environment:

```bash
export RLM_SANDBOX_MODE=container
export RLM_SANDBOX_CONTAINER_RUNTIME=docker
export RLM_SANDBOX_CONTAINER_IMAGE=python:3.12-alpine
```

Container dijalankan dengan hardening default:
- `--network none`
- `--read-only`
- `--cap-drop ALL`
- `--security-opt no-new-privileges`
- `--pids-limit`
- memory/cpu limit
- `--tmpfs /tmp` terbatas
- non-root user (`65532:65532`)

Catatan fallback:
- Jika runtime container tidak tersedia, executor akan fallback ke mode `subprocess` (default behavior).
- Fallback bisa dimatikan lewat inisialisasi `SandboxExecutor(fallback_to_subprocess=False)` di kode aplikasi.
- Saat ini belum ada env var khusus untuk toggle fallback.

## Contoh Alur Pakai Di Codex

1. Inisialisasi context:
   "Panggil `rlm_init_context` dengan context ini, set `max_steps=40`."
2. Jalankan loop rekursif:
   "Pakai `rlm_run_repl` untuk chunking context dan agregasi hasil."
3. Inspeksi variabel:
   "Panggil `rlm_get_var` untuk `summary_by_chunk`."
4. Finalisasi:
   "Panggil `rlm_finalize` dari `final_answer`."
5. Audit langkah:
   "Panggil `rlm_get_trace` untuk langkah 0 sampai 20."

## Troubleshooting

### `MCP startup failed: ... initialize response`

1. Pastikan dependency terpasang:

```bash
. .venv/bin/activate
python -m pip install -e .
```

2. Validasi launcher:
- path benar
- executable bit aktif (`chmod +x bin/run-rlm-mcp.sh`)
- `REPO_DIR` di script sesuai lokasi repo

3. Smoke test launcher:

```bash
timeout 5s ./bin/run-rlm-mcp.sh; echo $?
```

4. Restart Codex CLI.

### `Import "mcp.server.fastmcp" could not be resolved`

- Ini biasanya dari language server/editor.
- Pastikan interpreter editor menunjuk `.venv` project.
- Pastikan paket terpasang dengan `python -m pip install -e .`.

### Tool timeout saat `rlm_run_repl`

- Kecilkan `code` per langkah.
- Kurangi kompleksitas loop.
- Naikkan `tool_timeout_sec` di config Codex bila perlu.

### `SESSION_NOT_FOUND`

- Gunakan `session_id` terbaru dari output `rlm_init_context`.
- Jangan reuse session yang sudah di-finalize.

## Running Tests

```bash
. .venv/bin/activate
PYTHONPATH=src pytest -v
```

## Catatan Operasional

- Project ini masih berfokus pada in-memory workflow (MVP).
- Belum ada persistence lintas restart process.
- Cocok untuk companion MCP server saat Codex menjadi orchestrator utama RLM loop.
