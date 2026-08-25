import os, sys, json, requests, time, base64

album_dir = sys.argv[1] if len(sys.argv) > 1 else r"D:\xampp\htdocs\simpleGraphy\galleries\Marmot_Buckhorn_Key_Exchange_72023"
lr_dir = os.path.join(album_dir, ".lr")
api_url = "http://localhost:8080/v1/chat/completions"
api_key = "sk-123"

prompt = "Describe this photo in 1-2 sentences. Focus on subjects, setting, and mood."

headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

# Get all image files, skip HEIC (llama-server cannot decode without ffprobe)
all_images = [f for f in os.listdir(album_dir) if f.endswith(('.jpg', '.jpeg'))]
uncaptioned = []
for img in sorted(all_images):
    caption_file = os.path.join(album_dir, img + ".caption")
    if not os.path.exists(caption_file):
        uncaptioned.append(img)

print(f"Processing {len(uncaptioned)} uncaptioned JPEG images...")
print(f"Skipping HEIC files (ffprobe not available)")

# Resume from checkpoint
checkpoint_file = os.path.join(album_dir, ".caption_progress")
start_idx = 0
if os.path.exists(checkpoint_file):
    with open(checkpoint_file, 'r') as f:
        start_idx = int(f.read().strip())
    print(f"Resuming from index {start_idx}")

for i, img in enumerate(uncaptioned, 1):
    if i <= start_idx:
        continue
    # Try LR version first, fall back to original
    if img.lower().endswith('.jpg'):
        lr_name = img.replace('.jpg', '_LR.jpg')
        lr_path = os.path.join(lr_dir, lr_name)
        if os.path.exists(lr_path):
            img_path = lr_path
            print(f"[{i}/{len(uncaptioned)}] {img} (using LR)")
        else:
            img_path = os.path.join(album_dir, img)
            print(f"[{i}/{len(uncaptioned)}] {img} (full res)")
    else:
        img_path = os.path.join(album_dir, img)
        print(f"[{i}/{len(uncaptioned)}] {img} (jpeg)")

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
                    # Save checkpoint
                    with open(checkpoint_file, 'w') as cf:
                        cf.write(str(i))
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

# Clean up checkpoint
if os.path.exists(checkpoint_file):
    os.remove(checkpoint_file)

print("\nDone!")
