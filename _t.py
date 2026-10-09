import torch, time, sys, os
os.environ['TQDM_DISABLE'] = '1'
from diffusers import AutoPipelineForText2Image
sys.stdout.reconfigure(line_buffering=True)
print('Downloading SD Turbo via hf-mirror...', flush=True)
t0=time.time()
try:
    p=AutoPipelineForText2Image.from_pretrained('stabilityai/sd-turbo', torch_dtype=torch.float32)
    print(f'Download+Load: {time.time()-t0:.1f}s', flush=True)
    print('Generating 512x512 1step...', flush=True)
    p.to('cpu')
    t1=time.time()
    with torch.no_grad():
        r=p(prompt='a beautiful chinese woman photo', num_inference_steps=1, guidance_scale=0.0, width=512, height=512)
    dt=time.time()-t1
    print(f'OK! Gen: {dt:.1f}s', flush=True)
    r.images[0].save('F:/ai项目/ai项目/test_turbo.png')
    print('Saved test_turbo.png!')
except Exception as e:
    print(f'FAIL: {e}', flush=True)
