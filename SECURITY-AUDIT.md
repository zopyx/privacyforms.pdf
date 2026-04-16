# Security Audit Report

Project: `privacyforms.pdf`
Date: 2026-04-16
Auditor: Codex with parallel specialist subagents
Scope: local source review of `privacyforms_pdf/`, CLI commands, tests, and limited local runtime verification

## Executive Summary

This package does not appear to expose a direct remote code execution or shell injection path in its own code. The realistic risk profile is:

- local secret exposure through `pdfcpu` password arguments
- arbitrary file overwrite or symlink clobber when callers control output paths
- denial of service through malformed or oversized PDFs
- denial of service through malformed JSON input to `fill-form`

Two crash cases were verified locally:

1. `fill-form` crashes on `[]` with `AttributeError: 'list' object has no attribute 'items'`
2. `extract` on an invalid PDF bubbles a raw `pypdf.errors.PdfStreamError`

## Methodology

- Static review of package source, CLI commands, and tests
- Parallel subagent review across three specialties:
  - parser abuse and PDF attack surface
  - subprocess and OS interaction
  - CLI and API misuse scenarios
- Local verification of selected crash paths using the project CLI

## Findings

### 1. High: Password Leakage via Process Arguments

Affected files:

- `privacyforms_pdf/security.py:259`
- `privacyforms_pdf/security.py:327`
- `privacyforms_pdf/security.py:400`
- `privacyforms_pdf/commands/pdf_encrypt.py:17`
- `privacyforms_pdf/commands/pdf_set_permissions.py:18`
- `privacyforms_pdf/commands/pdf_list_permissions.py:17`

Description:

The package passes `owner_password` and `user_password` to `pdfcpu` as command-line arguments using `-opw` and `-upw`. This is not shell injection, but it is a confidentiality issue because process arguments are often visible to other local users, process monitors, container runtimes, audit tooling, and CI logs.

Impact:

- exposure of PDF owner passwords
- exposure of PDF user passwords
- unauthorized decryption or permission changes if stolen credentials are reused

Exploitability:

High on multi-user systems, shared CI runners, containers with process visibility, and environments where command invocation is logged.

Exploit scenario:

1. A privileged workflow runs `pdf-forms encrypt ... -opw secret`.
2. Another local user reads `ps`, `/proc/<pid>/cmdline`, or job logs.
3. The attacker obtains the password and can decrypt or reconfigure protected PDFs.

Origin:

- package-intrinsic at the wrapper layer
- partially inherited from `pdfcpu`'s argv-based interface

Recommended remediation:

- avoid passing secrets in argv where possible
- prefer stdin, environment variables with careful scrubbing, or temporary protected config files if supported by the backend
- document that current password handling is unsafe on shared hosts if backend constraints remain

### 2. High: Unsafe Output Path Handling Enables File Clobber

Affected files:

- `privacyforms_pdf/extractor.py:181`
- `privacyforms_pdf/extractor.py:312`
- `privacyforms_pdf/backends/pdfcpu.py:165`
- `privacyforms_pdf/security.py:275`

Description:

The package writes directly to caller-controlled paths using normal file opens or delegated tool output. There are no protections against symlink traversal, clobbering sensitive files, or unsafe in-place overwrite behavior. Several commands default to modifying the input file when no output path is supplied.

Impact:

- overwrite of arbitrary writable files
- symlink-following writes
- corruption of source PDFs through in-place modification

Exploitability:

High if a higher-level application exposes `output_path` to untrusted users or derives it from user-controlled input.

Exploit scenario:

1. A web app or worker wraps this package and accepts an output filename.
2. An attacker points the output to a symlink or sensitive writable target.
3. The package overwrites the target during extract, fill, or encrypt operations.

Origin:

- package-intrinsic

Recommended remediation:

- use safe file creation with explicit overwrite controls
- reject symlinks for output targets
- write to a temporary file and atomically replace only intended targets
- consider disabling implicit in-place modification by default

### 3. Medium: Malformed or Oversized PDFs Can Crash or Exhaust Resources

Affected files:

- `privacyforms_pdf/extractor.py:147`
- `privacyforms_pdf/extractor.py:282`
- `privacyforms_pdf/reader.py:142`
- `privacyforms_pdf/reader.py:265`

Description:

`pypdf` parsing is invoked directly with no normalization layer around parser exceptions and no explicit size or complexity limits. The code walks all pages, annotations, widgets, `/Kids`, and options. The configured timeout only protects `pdfcpu` subprocesses, not the `pypdf` code path.

Impact:

- process crash from raw parser exceptions
- CPU exhaustion
- memory exhaustion
- stuck worker or batch job

Exploitability:

Medium to High for any service or automation that processes untrusted PDFs.

Exploit scenario:

1. An attacker submits a malformed or oversized PDF.
2. `PdfReader` raises a low-level exception or spends excessive resources traversing objects.
3. The caller sees a traceback or suffers degraded availability.

Verified behavior:

- invalid PDF input caused a raw `pypdf.errors.PdfStreamError` traceback through the CLI

Origin:

- largely dependency-inherited from `pypdf`
- package-intrinsic because exceptions are not normalized and no defensive bounds are applied

Recommended remediation:

- wrap `PdfReader` failures in `PDFFormError`
- add configurable limits for file size, page count, annotation count, and field count
- document that untrusted PDFs should be processed in isolated workers with memory and CPU limits

### 4. Medium: `fill-form` Crashes on Valid-but-Wrong JSON Types

Affected files:

- `privacyforms_pdf/commands/pdf_fill_form.py:73`
- `privacyforms_pdf/extractor.py:213`
- `privacyforms_pdf/extractor.py:290`
- `privacyforms_pdf/backends/pdfcpu.py:102`

Description:

The CLI accepts JSON input but assumes the parsed value is a mapping. Arrays, strings, numbers, or `null` are not rejected cleanly. The code later calls `.items()` on the value and raises `AttributeError`.

Impact:

- command crash instead of validation failure
- easy denial of service for wrappers that accept attacker-controlled JSON payloads

Exploitability:

Medium.

Verified behavior:

- input `[]` caused `AttributeError: 'list' object has no attribute 'items'`

Origin:

- package-intrinsic

Recommended remediation:

- validate that decoded JSON is a `dict[str, Any]` before processing
- raise `FormValidationError` or `click.ClickException` with a clean message
- add tests for `[]`, `null`, strings, and numeric JSON

### 5. Low/Medium: Temporary JSON Files May Persist After Abnormal Termination

Affected files:

- `privacyforms_pdf/backends/pdfcpu.py:48`
- `privacyforms_pdf/backends/pdfcpu.py:179`
- `privacyforms_pdf/extractor.py:505`

Description:

Temporary JSON files are created with `delete=False` and cleaned up in `finally`. That is correct for normal execution, but if the process is killed or crashes before cleanup, form data can remain on disk in temporary storage.

Impact:

- disclosure of extracted form structure
- disclosure of filled form values

Exploitability:

Low to Medium. Requires same-user or privileged local disk access after abnormal termination.

Origin:

- package-intrinsic

Recommended remediation:

- minimize temp file lifetime
- ensure restrictive permissions on temp files
- consider secure cleanup or alternative IPC if backend allows it

## Non-Findings

The review did not identify:

- shell injection in subprocess execution
- obvious direct remote code execution in package code
- obvious network-exposed attack surface in the package itself

Subprocess calls consistently use argv lists rather than invoking a shell.

## Test Gaps

Current tests are strong on mocked behavior but weaker on hostile-input handling. Notable gaps:

- `fill-form` does not test valid JSON with invalid top-level types such as `[]` or `null`
- CLI tests do not cover raw `pypdf` parser failures from malformed PDFs
- no tests enforce safe handling of symlinked or dangerous output paths
- no tests exercise resource-limiting behavior for oversized PDFs

## Risk Prioritization

Immediate priority:

1. Remove or mitigate password exposure in process arguments
2. Harden output-path handling and in-place overwrite behavior
3. Normalize parser exceptions and reject invalid JSON top-level types

Secondary priority:

1. Add operational and code-level defenses against parser-driven DoS
2. Reduce temp-file confidentiality exposure

## Practical Exploit Options

Realistic attacker actions against deployments using this package:

1. Read `pdfcpu` passwords from process arguments on shared hosts or CI
2. Supply a crafted output path to overwrite a file or follow a symlink
3. Submit malformed or oversized PDFs to crash or stall workers
4. Supply non-object JSON to crash `fill-form`
5. If a wrapper exposes `pdfcpu_path` or PATH control, redirect subprocess execution to an attacker-chosen binary

## Conclusion

This package is not obviously vulnerable to direct code execution, but it has several meaningful local-security and availability issues. The strongest findings are secret leakage through command-line arguments and unsafe path handling. The most likely operational failures are parser-driven denial of service and crashable bad-input paths.
