import os
d = r'C:\Users\OSCORP\.cache\huggingface\hub\sd-v1-5'
required = [
    'model_index.json',
    'scheduler/scheduler_config.json',
    'feature_extractor/preprocessor_config.json',
    'safety_checker/config.json',
    'safety_checker/model.safetensors',
    'tokenizer/merges.txt',
    'tokenizer/vocab.json',
    'tokenizer/special_tokens_map.json',
    'tokenizer/tokenizer_config.json',
    'text_encoder/config.json',
    'text_encoder/model.safetensors',
    'unet/config.json',
    'unet/diffusion_pytorch_model.safetensors',
    'vae/config.json',
    'vae/diffusion_pytorch_model.safetensors',
]
all_ok = True
for f in required:
    p = os.path.join(d, f)
    ok = os.path.exists(p) and os.path.getsize(p) > 1000
    sz = os.path.getsize(p)//1024//1024 if os.path.exists(p) else 0
    mark = 'OK ' if ok else 'FAIL'
    print(f'  [{mark}] {f} ({sz}MB)')
    if not ok: all_ok = False
print()
print('All ready!' if all_ok else 'Missing files!')
