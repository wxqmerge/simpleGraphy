# Caption Generation Pipeline

## Architecture

The LLM runs **locally** on your machine via `llama-server` — no cloud service involved.

```
caption_remaining.py  -->  llama-server (localhost:8080)  -->  GPU (32GB VRAM)
       ^                       |
       |                       v
  .caption files    Qwen3.6-27B Vision model
```

## Flow

1. **Image Selection** — `caption_remaining.py` scans an album directory for `.jpg`/`.jpeg` files without a `.caption` file. HEIC files are skipped (requires ffprobe in PATH).

2. **LR Preference** — Checks `.lr/IMG_XXXX_LR.jpg` first. LR images are ~400 KB vs ~14 KB full res, producing far fewer embedding tokens.

3. **API Request** — Sends image as base64 to local `llama-server` via OpenAI-compatible chat API:
   - `max_tokens: 512` — model generates internal reasoning (~1400 chars) before the actual caption. `128` was too low and caused empty responses.
   - `temperature: 0.6` — moderate creativity
   - Prompt: `"Describe this photo in 1-2 sentences. Focus on subjects, setting, and mood."`

4. **Response Handling** — Extracts `content` field. The `reasoning_content` field is discarded. Empty responses retry up to 3 times with exponential backoff.

5. **KV Cache Management** — Server runs with `--ctx-size 65536`. Each image consumes ~1k–50k tokens in the KV cache. Sequential processing (1 at a time) prevents cache exhaustion on 32GB VRAM.

6. **Persistence** — Caption written to `image.jpg.caption` alongside the image. Checkpoint file (`.caption_progress`) tracks progress for resume on interruption.

7. **Gallery Integration** — `generate_gallery.py` reads `.caption` files and renders them in thumbnail overlays and lightbox via CSS class `.caption`.

## Processing Speed

| Image Type | File Size | Embedding Tokens | Time per Image |
|------------|-----------|-----------------|----------------|
| LR (`.lr/`) | ~400 KB | ~1,063 tokens | 8–13 seconds |
| Full res | ~14 MB | ~50,000 tokens | 28–37 seconds |

The bottleneck is the **image embedding** (prompt eval), not text generation. The vision model converts the image into tokens proportional to its resolution.

**Estimated throughput:**
- LR images: ~5–7 images/minute
- Full res: ~2 images/minute

## Server Config

`D:\llama.cpp.b10153\runq36MTP27Bvision.bat`:
```
--model "D:\models\Qwen3.6-27B-UD-Q5_K_XL.gguf"
--mmproj "D:\models\mmproj-BF16-27B.gguf"
--ctx-size 65536
--n-predict 512
--threads 24
--image-min-tokens 1024
--spec-type draft-mtp --spec-draft-n-max 2
```

## Key Lessons

- `max_tokens: 128` → empty captions (model hit limit during reasoning phase)
- `--ctx-size 32768` → KV cache overflow after ~2 images (each consumes ~27k tokens)
- HEIC format → needs FFmpeg conversion to JPEG before processing
- Batch processing → crashes server; sequential is required on 32GB VRAM

## Scripts

- `caption_remaining.py [album_path]` — Process uncaptioned images in an album (supports resume)
- `generate_captions.py` — List/track caption progress for an album
- `generate_gallery.py` — Regenerate gallery HTML with caption overlays
