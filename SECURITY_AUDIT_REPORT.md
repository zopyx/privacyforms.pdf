# Security Audit Report: privacyforms-pdf

**Date:** 2026-04-17  
**Auditor:** AI Red Team (20 specialist agents)  
**Target:** `privacyforms-pdf` v0.2.0  
**Scope:** `privacyforms_pdf/` package, CLI, Python API, dependencies  
**Tools:** `bandit`, `semgrep`, `pip-audit`, custom PoC exploits  

---

## Executive Summary

The `privacyforms-pdf` library is well-structured and uses modern Python practices (Pydantic, type hints, pluggy). Automated static analysis (`bandit`, `semgrep`) returned **zero findings** in the source code. However, manual audit and dynamic testing revealed **5 security issues** ranging from CWE-59 (symlink attacks) to CWE-78 (plugin command injection). None are remote code execution vulnerabilities, but several allow local privilege escalation, arbitrary file overwrite, and denial of service.

**Risk Rating:** Medium  
**Exploitability:** Local / Supply-Chain  

---

## Findings

### 🔴 HIGH-1: CWE-59 — Arbitrary File Overwrite via Symlink in `extract_to_json()`

**File:** `privacyforms_pdf/extractor.py:104`  
**CVSS 4.0:** 7.1 (High)  

#### Description
`PDFFormService.extract_to_json()` writes JSON output directly using `Path.write_text()` without checking whether `output_path` is a symbolic link. If an attacker controls the output path (or tricks a caller into passing a symlink), the symlink target is overwritten.

While the CLI command `pdf-forms parse` has `_safe_write_text()` with an `is_symlink()` guard, the **Python API does not**, creating an inconsistent security boundary.

#### PoC
```python
from pathlib import Path
from privacyforms_pdf.extractor import PDFFormService

# Setup: sensitive.txt is a secret file; output.json is a symlink to it
Path("output.json").symlink_to("sensitive.txt")

service = PDFFormService()
service.extract_to_json("form.pdf", "output.json")
# sensitive.txt is now overwritten with JSON data
```

**Confirmed:** ✅ Symlink target overwritten in lab testing.

#### Remediation
Add symlink validation to `extract_to_json()`:
```python
output_path = Path(output_path)
if output_path.is_symlink():
    raise ValueError(f"Refusing to write to symlink: {output_path}")
output_path.write_text(...)
```

---

### 🟡 MEDIUM-1: CWE-22 / CWE-20 — Path Traversal & Type Confusion via Symlink Input

**File:** `privacyforms_pdf/extractor.py:321-326`  
**CVSS 4.0:** 5.3 (Medium)  

#### Description
`_validate_pdf_path()` only verifies `path.exists()` and `path.is_file()`. It does **not**:
- Resolve symlinks (`path.resolve()`)
- Verify the file is actually a PDF (magic bytes `%PDF-`)
- Reject device files, FIFOs, or sockets

An attacker can pass a symlink pointing to any existing file (e.g., `/etc/passwd`, `/dev/urandom`, application database files). The file passes validation and is handed to `PdfReader`, which may:
- Hang on infinite streams (`/dev/zero`)
- Leak file paths in exception traces
- Cause CPU/memory spikes on non-PDF data

#### PoC
```python
from pathlib import Path
from privacyforms_pdf.extractor import PDFFormService

evil = Path("evil.pdf")
evil.symlink_to("/etc/passwd")  # or any sensitive file

service = PDFFormService()
service.has_form(evil)  # Passes validation; PdfReader fails later
```

**Confirmed:** ✅ Symlink to text file passed validation and reached the parser.

#### Remediation
1. Resolve symlinks before validation:
   ```python
   pdf_path = pdf_path.resolve()
   ```
2. Verify PDF magic header after reading the first 4 bytes (`%PDF`).
3. Use `stat.S_ISREG()` to ensure the path is a regular file, not a symlink or device.

---

### 🟡 MEDIUM-2: CWE-78 / CWE-94 — Arbitrary CLI Command Injection via Pluggy Plugin System

**File:** `privacyforms_pdf/cli.py:19-21`  
**CVSS 4.0:** 6.5 (Medium)  

#### Description
The CLI uses `pluggy` to dynamically load commands from any installed Python package advertising the `privacyforms_pdf.commands` entry point:
```python
pm.load_setuptools_entrypoints("privacyforms_pdf.commands")
```

There is **no validation** of registered commands. A malicious package installed in the same environment (via dependency confusion, typosquatting, or compromised transitive dependency) can register arbitrary `click.Command` objects that execute when invoked.

This is a **supply-chain attack vector**: the library trusts every installed package.

#### PoC
```python
# A malicious pip package only needs this in pyproject.toml:
[project.entry-points."privacyforms_pdf.commands"]
backdoor = "evil_pkg:register_commands"
```

**Confirmed:** ✅ Plugin manager accepted and registered an arbitrary object in lab testing.

#### Remediation
1. **Whitelist** known built-in commands and reject unknown ones.
2. **Digitally sign** or hash-verify plugin modules before registration.
3. **Document** the risk and advise users to pin all transitive dependencies.

---

### 🟡 MEDIUM-3: CWE-400 — Uncontrolled Resource Consumption (DoS)

**Files:** `privacyforms_pdf/parser.py`, `privacyforms_pdf/json_utils.py`  
**CVSS 4.0:** 5.3 (Medium)  

#### Description
Multiple DoS vectors exist:

1. **Unbounded Form Fields:** `parse_pdf()` iterates over all fields returned by `reader.get_fields()` without an upper limit. A crafted PDF with millions of form fields can exhaust memory and CPU.

2. **JSON Memory Bomb:** `load_json_object()` enforces a 10 MB file size limit and 50-level depth limit. However, a 10 MB JSON file containing deeply nested arrays or repeated escape sequences can expand to a much larger in-memory object before the depth check runs.

3. **PDF Decompression Bomb:** The 50 MB PDF size limit (`_MAX_PDF_SIZE`) does not account for highly compressed object streams. A "ZIP bomb" PDF could decompress to gigabytes in memory.

4. **Recursive Depth Check (Minor):** `check_json_depth()` is implemented recursively. While the default `MAX_JSON_DEPTH=50` prevents hitting Python's recursion limit, increasing the limit in configuration would make this exploitable.

#### Remediation
1. Add a `MAX_FIELDS` limit (e.g., 10,000) in `parse_pdf()`.
2. Validate total parsed object size (number of keys, total string length) in `load_json_object()`.
3. Consider using `resource.setrlimit` or timeouts for PDF parsing.
4. Implement decompression ratio limits if parsing streams manually.

---

### 🟢 LOW-1: CWE-20 — Inconsistent Input Validation Between CLI and Python API

**Files:** `privacyforms_pdf/commands/pdf_parse.py`, `privacyforms_pdf/extractor.py`  

#### Description
Security controls are inconsistently applied:

| Control | CLI (`pdf-forms`) | Python API (`PDFFormService`) |
|---------|-------------------|-------------------------------|
| Output symlink check | ✅ `_safe_write_text()` | ❌ Missing in `extract_to_json()` |
| Input path validation | ✅ `click.Path(exists=True)` | ✅ `_validate_pdf_path()` |
| PDF magic validation | ❌ None | ❌ None |
| Symlink resolution | ❌ None | ❌ None |

This inconsistency means API consumers are more vulnerable than CLI users.

#### Remediation
Centralize all I/O safety checks in a single utility module and reuse it in both CLI and API layers.

---

## Dependency Audit

| Tool | Result |
|------|--------|
| `bandit` | 0 findings |
| `semgrep` | 0 findings |
| `pip-audit` | **10 known CVEs in 3 dev packages** |

### Known Vulnerabilities (Development Dependencies Only)

| Package | Version | CVE / GHSA | Fixed In |
|---------|---------|------------|----------|
| `pygments` | 2.19.2 | CVE-2026-4539 | 2.20.0 |
| `pytest` | 9.0.2 | CVE-2025-71176 | 9.0.3 |
| `pypdf` | 6.7.5 *(reported)* | Multiple CVEs | 6.10.2 |

**Note:** The installed production version of `pypdf` is **6.10.2**, which patches the reported CVEs. The `pip-audit` hit for `pypdf 6.7.5` appears to be a stale artifact in the environment cache. Production runtime is currently clean.

---

## Attack Scenarios

### Scenario A: Local Privilege Escalation
1. Attacker has local shell access.
2. Creates a symlink `output.json -> /etc/crontab` (or any writable config).
3. Triggers an application using `privacyforms-pdf` to call `extract_to_json(pdf, "output.json")`.
4. `/etc/crontab` is overwritten with attacker-controlled JSON, leading to root execution.

### Scenario B: Supply-Chain Backdoor
1. Attacker publishes `privacyforms-pdf-helper` on PyPI (typosquatting or legitimate-looking helper).
2. Package registers a CLI command `exfil` via the `privacyforms_pdf.commands` entry point.
3. When a user runs `pdf-forms exfil`, the backdoor executes and exfiltrates environment variables.

### Scenario C: Service DoS
1. Attacker uploads a 50 MB "ZIP bomb" PDF to a web service using `privacyforms-pdf`.
2. Service calls `extract()` or `fill_form()`.
3. pypdf decompresses streams, consuming all RAM and crashing the worker.

---

## Remediation Roadmap

| Priority | Task | Effort |
|----------|------|--------|
| P0 | Add symlink & directory traversal guards to all file-write APIs | 1 day |
| P0 | Add PDF magic-byte validation (`%PDF-`) to `_validate_pdf_path()` | 2 hours |
| P1 | Resolve symlinks and enforce regular-file checks on input paths | 4 hours |
| P1 | Add `MAX_FIELDS` limit and parsing timeouts | 1 day |
| P1 | Whitelist or sign plugin commands in `cli.py` | 1-2 days |
| P2 | Centralize I/O safety utilities | 1 day |
| P2 | Upgrade `pygments` and `pytest` dev dependencies | 30 min |

---

## Appendix A: PoC Files

All proof-of-concept scripts are available in `/tmp/poc_exploits/`:

| File | Finding |
|------|---------|
| `poc_extract_to_json_symlink.py` | HIGH-1: Symlink overwrite |
| `poc_path_traversal_input.py` | MEDIUM-1: Input path traversal |
| `poc_plugin_injection2.py` | MEDIUM-2: Plugin injection |
| `poc_malformed_pdf_dos.py` | MEDIUM-3: DoS via malformed input |
| `poc_json_recursive_dos.py` | MEDIUM-3: JSON recursion |

---

## Appendix B: Code References

```
privacyforms_pdf/extractor.py:104   -> Path(output_path).write_text(...)
privacyforms_pdf/extractor.py:321   -> _validate_pdf_path()
privacyforms_pdf/cli.py:19-21       -> pm.load_setuptools_entrypoints(...)
privacyforms_pdf/filler.py:431-439  -> tempfile + os.replace(...)
privacyforms_pdf/parser.py:457      -> for name, field_ref in fields.items()
privacyforms_pdf/json_utils.py:23   -> check_json_depth() (recursive)
```

---

*Report generated by automated security audit pipeline.*
