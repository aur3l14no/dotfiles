---
name: mineru-ocr
description: Extract PDF text, tables and figure layout when the user or a paper-reading workflow requests MinerU OCR.
---

# MinerU OCR

Use the v4 API at `https://mineru.net`. Choose an output directory from the current project's storage rules and keep task responses, ZIPs and extracted files there. Resolve `scripts/poll.py` relative to this skill. Commands use Bash, curl, jq and Python's standard library.

## Authentication

Curl reads `~/.config/mineru/curl.conf` (or `$XDG_CONFIG_HOME/mineru/curl.conf`), mode `600`, in a directory with mode `700`:

```text
header = "Authorization: Bearer <token>"
```

Keep credentials out of skill text, command arguments and output. If authentication fails, have the credential refreshed in this file; do not repeatedly resubmit. The credential config is only for MinerU API requests, never presigned upload/download URLs.

```bash
MINERU_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/mineru/curl.conf"
```

Run the following commands inside the chosen output directory. Check every HTTP/API error before continuing; successful API responses have `.code == 0` and the expected id/data. `model_version` may be `vlm` or `pipeline`; default to `vlm` unless the task calls for the other model.

## Public PDF URL

```bash
jq -n --arg url "$PDF_URL" '{url: $url, model_version: "vlm"}' |
  curl -q --config "$MINERU_CONFIG" -fsS --max-time 60 \
    -H 'Content-Type: application/json' --data-binary @- \
    https://mineru.net/api/v4/extract/task > submit.json
TASK_ID=$(jq -er 'select(.code == 0) | .data.task_id // empty' submit.json)
python3 /path/to/mineru-ocr/scripts/poll.py task "$TASK_ID" --output status.json
```

Replace the script path with its resolved location. Polling stops on completion, failure, HTTP/API errors or a 15-minute deadline (`--timeout SECONDS` overrides it). Resume an unfinished task with the same id. Read the saved response for failure details.

On `done`, download `.data.full_zip_url` immediately with `curl -q -fLSs --max-time 300 -o result.zip "$ZIP_URL"` and extract it into `extracted/`. Presigned URLs are short-lived; do not reuse them as permanent references.

## Local PDFs

POST JSON to `https://mineru.net/api/v4/file-urls/batch` with the same authenticated curl options:

```json
{"enable_formula": true, "enable_table": true, "model_version": "vlm", "files": [{"name": "doc.pdf", "is_ocr": false}]}
```

Save the response as `submit-batch.json`. Use `is_ocr: true` for scanned documents. Each `.data.file_urls[i]` corresponds to the submitted `files[i]`; PUT the matching PDF with `curl -q -fsS --max-time 300 -X PUT "$UPLOAD_URL" -T "$PDF_PATH"`. Do not attach the credential config, Authorization or Content-Type headers to these presigned requests.

```bash
BATCH_ID=$(jq -er 'select(.code == 0) | .data.batch_id // empty' submit-batch.json)
python3 /path/to/mineru-ocr/scripts/poll.py batch "$BATCH_ID" --output status-batch.json
jq -r '.data.extract_result[] | select(.state == "done") | [.file_name, .full_zip_url] | @tsv' status-batch.json
```

Download successful entries into separate file-specific output directories, then extract their ZIPs. A partially failed batch still has usable `done` entries; report each failed entry's `err_msg` and retain its response.

## Read the result

`extracted/full.md` is the reading entrypoint. `content_list_v2.json` and `layout.json` provide block/layout detail; `images/` contains OCR crops useful for locating figures. For a presentation-quality figure, export or crop the original PDF into the destination project's asset location.
