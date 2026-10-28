import os, sys, json, requests, time, base64

album_dir = sys.argv[1] if len(sys.argv) > 1 else r"D:\simpleGraphy\galleries\Marmot_Buckhorn_Key_Exchange_72023"
lr_dir = os.path.join(album_dir, ".lr")
api_url = "http://localhost:8080/v1/chat/completions"
api_key = "sk-123"

prompt = "Describe this photo in 1-2 sentences. Focus on subjects, setting, and mood."

headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

# Get all image files, skip HEIC (llama-server cannot decode without ffprobe)
all_images = [f for f in os.listdir(album_dir) if f.lower().endswith(('.jpg', '.jpeg'))]
uncaptioned = []
for img in sorted(all_images):
    caption_file = os.path.join(album_dir, img + ".caption")
    if not os.path.exists(caption_file):
        uncaptioned.append(img)

print(f"Processing {len(uncaptioned)} uncaptioned JPEG images...")
print(f"Skipping HEIC files (ffprobe not available)")


def lr_name_for(basename):
    # Mirror of generate_gallery.lr_name_for: 'IMG.jpg' -> 'IMG_jpg_LR.jpg'
    stem, ext = os.path.splitext(basename)
    return f"{stem}_{ext.lower().lstrip('.')}_LR.jpg"


# No numeric checkpoint: the .caption sidecar files ARE the resume state, so a
# re-run naturally continues where the last one stopped.
for i, img in enumerate(uncaptioned, 1):
    # Try LR version first, fall back to original
    lr_path = os.path.join(lr_dir, lr_name_for(img))
    if os.path.exists(lr_path):
        img_path = lr_path
        print(f"[{i}/{len(uncaptioned)}] {img} (using LR)")
    else:
        img_path = os.path.join(album_dir, img)
        print(f"[{i}/{len(uncaptioned)}] {img} (full res)")

    # Read image as base64
    with open(img_path, 'rb') as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')

    payload = {
        "model": "Qwen3.6-27B Vision",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}
                ]
            }
        ],
        "max_tokens": 512,
        "temperature": 0.6
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = requests.post(api_url, headers=headers, json=payload, timeout=180)
            if resp.status_code == 200:
                data = resp.json()
                caption = data["choices"][0]["message"]["content"].strip().strip('"').strip()
                if caption:
                    caption_file = os.path.join(album_dir, img + ".caption")
                    with open(caption_file, 'w', encoding='utf-8') as f:
                        f.write(caption)
                    print(f"  OK: {caption[:80]}")
                    break
                else:
                    print(f"  EMPTY response from server")
            else:
                print(f"  FAIL HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            print(f"  FAIL Error: {e}")

        if attempt < max_retries - 1:
            wait = 5 * (attempt + 1)
            print(f"  Retrying in {wait}s...")
            time.sleep(wait)
    else:
        print(f"  FAILED after {max_retries} attempts, skipping")

    time.sleep(1)

print("\nDone!")
