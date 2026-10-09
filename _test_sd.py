import torch, time, sys
from diffusers import StableDiffusionPipeline, EulerDiscreteScheduler

print('Loading SD 1.5 on CPU...', flush=True)
t0 = time.time()
p = StableDiffusionPipeline.from_pretrained(
    r'C:\Users\OSCORP\.cache\huggingface\hub\sd-v1-5',
    dtype=torch.float32, local_files_only=True, safety_checker=None
)
p.scheduler = EulerDiscreteScheduler.from_config(p.scheduler.config)
p.enable_attention_slicing(1)
p.to('cpu')
print(f'Loaded in {time.time()-t0:.1f}s', flush=True)

print('Generating 512x512, 15 steps...', flush=True)
t1 = time.time()
with torch.no_grad():
    r = p(prompt='a beautiful chinese woman, photo', num_inference_steps=15, guidance_scale=7.5, width=512, height=512)
img = r.images[0]
dt = time.time() - t1
print(f'Generated in {dt:.1f}s', flush=True)
img.save('F:/ai项目/ai项目/test_sd.png')
print('Saved test_sd.png', flush=True)