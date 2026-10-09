import os, sys, time, requests
from pathlib import Path

BASE = 'https://hf-mirror.com/runwayml/stable-diffusion-v1-5/resolve/main'
CACHE = Path(os.path.expanduser('~')) / '.cache' / 'huggingface' / 'hub' / 'sd-v1-5'
CACHE.mkdir(parents=True, exist_ok=True)

FILES = [
    ('model_index.json', 200),
    ('scheduler/scheduler_config.json', 200),
    ('feature_extractor/preprocessor_config.json', 200),
    ('safety_checker/config.json', 300),
    ('safety_checker/model.safetensors', 60*1024*1024),
    ('tokenizer/merges.txt', 500*1024),
    ('tokenizer/vocab.json', 900*1024),
    ('tokenizer/special_tokens_map.json', 200),
    ('tokenizer/tokenizer_config.json', 300),
    ('text_encoder/config.json', 500),
    ('text_encoder/model.safetensors', 492*1024*1024),
    ('unet/config.json', 800),
    ('unet/model.safetensors', 3370*1024*1024),
    ('vae/config.json', 600),
    ('vae/model.safetensors', 335*1024*1024),
]

total = sum(s for _, s in FILES)
print(f'SD 1.5 下载 (仅必要文件)')
print(f'总大小约: {total//1024//1024} MB')
print(f'保存到: {CACHE}')
print()

for fname, expected in FILES:
    url = f'{BASE}/{fname}'
    dest = CACHE / fname
    if dest.exists() and dest.stat().st_size > expected * 0.8:
        sz = dest.stat().st_size // 1024 // 1024
        print(f'  [跳过] {fname} ({sz}MB 已存在)')
        continue
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f'  [下载] {fname} (约{expected//1024//1024}MB)...')
    t0 = time.time()
    try:
        with requests.get(url, stream=True, timeout=60, headers={'User-Agent': 'Mozilla/5.0'}) as r:
            r.raise_for_status()
            with open(dest, 'wb') as f:
                dl = 0
                for chunk in r.iter_content(chunk_size=2*1024*1024):
                    f.write(chunk)
                    dl += len(chunk)
                    pct = dl / max(expected, 1) * 100
                    mb = dl / 1024 / 1024
                    print(f'\r           {pct:5.1f}%  {mb:.0f}MB  ', end='', flush=True)
        dt = time.time() - t0
        sz = dest.stat().st_size // 1024 // 1024
        print(f'  OK ({sz}MB, {dt:.0f}s)')
    except Exception as e:
        print(f'  FAIL: {e}')
        if dest.exists() and dest.stat().st_size < expected * 0.5:
            dest.unlink()

print()
print('✅ 下载完成！现在可以修改 sd_generator.py 指向此路径')
print(f'   local_model_path = r\"{CACHE}\"')
