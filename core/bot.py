import time
import base64

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from openai import OpenAI as _OpenAIClient

from config import (
    API_KEYS,
    PROVIDER_DEFAULT_MODELS,
    DASHSCOPE_BASE_URL,
    QIANFAN_BASE_URL,
)
from core.storage import (
    load_history_from_file,
    save_history_to_file,
    trim_history,
)
from core.search import WebSearcher


class AIChatBot:

    _provider_cooldown = {}

    def __init__(self, api_key: str, model: str = "", provider: str = "deepseek", enable_search: bool = False):
        self.api_key = api_key
        self.provider = provider
        default_model = PROVIDER_DEFAULT_MODELS.get(provider, "deepseek-chat")
        self.model = model if model and self._is_model_for_provider(model, provider) else default_model
        self.conversation_history = trim_history(load_history_from_file())
        self.current_conversation_id = None
        self.enable_search = enable_search
        self.searcher = WebSearcher() if enable_search else None
        self.vision_model = "gpt-4o-mini" if provider == "openai" else "qwen-vl-plus" if provider == "qwen" else "ernie-5.0" if provider == "wenxin" else "deepseek-chat" if provider == "deepseek" else None

        PROVIDER_IMAGE_MODELS = {
            "openai": {"dall-e-3", "dall-e-2"},
            "qwen": {"wanx2.1-t2i-turbo", "wanx2.1-t2i-plus", "wanx-v1", "qwen-image"},
            "wenxin": {"qwen-image", "ernie-image", "ernie-image-turbo", "ERNIE-ViLG-2.0", "ernie-vilg-v2", "ERNIE-ViLG", "sd_xl", "irag-1.0", "flux.1-schnell"},
        }
        default_img = "dall-e-3" if provider == "openai" else "wanx2.1-t2i-turbo" if provider == "qwen" else "qwen-image" if provider == "wenxin" else None
        img_set = PROVIDER_IMAGE_MODELS.get(provider, set())
        self.image_model = self.model if self.model in img_set else default_img

        self.session = requests.Session()
        retry_strategy = Retry(
            total=1,
            backoff_factor=0.2,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=20
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.dashscope_base_url = DASHSCOPE_BASE_URL.rstrip("/")

        self._wenxin_client = None
        if provider == "wenxin" and api_key:
            self._wenxin_client = _OpenAIClient(
                api_key=api_key,
                base_url=QIANFAN_BASE_URL
            )

    @staticmethod
    def _is_model_for_provider(model: str, provider: str) -> bool:
        provider_prefixes = {
            "deepseek": ("deepseek",),
            "qwen": ("qwen", "wanx"),
            "wenxin": ("ernie",),
            "openai": ("gpt", "dall"),
        }
        prefixes = provider_prefixes.get(provider, ())
        return any(model.lower().startswith(p) for p in prefixes)

    @classmethod
    def _mark_provider_cooldown(cls, provider_name: str, reason: str = "error", cooldown_sec: float = 30.0):
        cls._provider_cooldown[provider_name] = {
            "until": time.time() + cooldown_sec,
            "reason": reason
        }

    @classmethod
    def _is_provider_cooled_down(cls, provider_name: str) -> bool:
        info = cls._provider_cooldown.get(provider_name)
        if not info:
            return True
        if time.time() < info["until"]:
            return False
        cls._provider_cooldown.pop(provider_name, None)
        return True

    @classmethod
    def _handle_provider_error(cls, provider_name: str, error_msg: str):
        msg_lower = error_msg.lower()
        if "429" in error_msg or "rate_limit" in msg_lower or "rate limit" in msg_lower or "rpm" in msg_lower:
            cls._mark_provider_cooldown(provider_name, "rate_limit", cooldown_sec=45.0)
        elif "403" in error_msg or "account_overdue" in msg_lower or "access_denied" in msg_lower:
            cls._mark_provider_cooldown(provider_name, "account_issue", cooldown_sec=120.0)
        elif "401" in error_msg or "unauthorized" in msg_lower:
            cls._mark_provider_cooldown(provider_name, "auth_error", cooldown_sec=60.0)
        else:
            cls._mark_provider_cooldown(provider_name, "other", cooldown_sec=15.0)

    def _call_provider_text(self, provider_name: str, api_key: str, model: str) -> str:
        old_provider = self.provider
        old_model = self.model
        old_key = self.api_key
        old_wenxin = self._wenxin_client
        try:
            self.provider = provider_name
            self.model = model
            self.api_key = api_key
            if provider_name == "wenxin":
                self._wenxin_client = _OpenAIClient(
                    api_key=api_key, base_url=QIANFAN_BASE_URL
                )
            if provider_name == "deepseek":
                return self._call_deepseek()
            elif provider_name == "qwen":
                return self._call_qwen()
            elif provider_name == "wenxin":
                return self._call_wenxin()
            else:
                raise ValueError(f"不支持的提供商: {provider_name}")
        finally:
            self.provider = old_provider
            self.model = old_model
            self.api_key = old_key
            self._wenxin_client = old_wenxin

    def _available_text_providers(self):
        providers = ["deepseek", "qwen", "wenxin"]
        ordered = [self.provider] + [p for p in providers if p != self.provider]
        result = []
        for name in ordered:
            key = API_KEYS.get(name, "")
            if not key:
                continue
            if not self._is_provider_cooled_down(name):
                continue
            default_model = PROVIDER_DEFAULT_MODELS.get(name, "deepseek-chat")
            result.append((name, key, default_model))
        return result

    def ask(self, question: str, force_search: bool = False,
            user_api_key: str = None, user_provider: str = None, user_model: str = None) -> str:
        search_results = ""
        if (self.enable_search or force_search) and self.searcher:
            print("正在搜索网络...", end="")
            search_results = self.searcher.search(question, max_results=3)
            print("完成")

        if search_results.strip():
            enhanced_question = f"""用户问题: {question}

网络搜索结果:
{search_results}

请基于以上搜索结果回答用户的问题。"""
            self.conversation_history.append({"role": "user", "content": enhanced_question})
        else:
            self.conversation_history.append({"role": "user", "content": question})

        errors = []
        response = None

        provider_chain = []
        if user_api_key and user_provider:
            um = user_model or PROVIDER_DEFAULT_MODELS.get(user_provider, "deepseek-chat")
            provider_chain.append((user_provider, user_api_key, um))
            is_user_mode = True
        else:
            is_user_mode = False
            for pn, pk, pm in self._available_text_providers():
                if not any(p == pn and k == pk for p, k, m in provider_chain):
                    provider_chain.append((pn, pk, pm))

        for provider_name, api_key, model in provider_chain:
            try:
                self.conversation_history = trim_history(self.conversation_history)
                response = self._call_provider_text(provider_name, api_key, model)
                is_user_key = (user_api_key and api_key == user_api_key)
                if not is_user_key and provider_name != self.provider:
                    print(f"[text fallback] {self.provider} 失败，已自动切换到 {provider_name}")
                self.conversation_history.append({"role": "assistant", "content": response})
                return response
            except Exception as e:
                err_msg = str(e)
                self._handle_provider_error(provider_name, err_msg)
                errors.append(f"{provider_name}: {err_msg[:160]}")
                print(f"  [文本请求] {provider_name} 失败: {err_msg[:100]}")
                continue

        self.conversation_history.pop()
        if not errors:
            return "所有可用的 AI 服务均未配置，请在 .env 中设置 API Key"
        if len(errors) == 1:
            return f"错误: {errors[0]}"
        return "所有 AI 服务均不可用：\n" + "\n".join(f"  - {e}" for e in errors)

    def _call_deepseek(self) -> str:
        url = "https://api.deepseek.com/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": self.conversation_history,
            "temperature": 0.3
        }

        response = self.session.post(url, headers=headers, json=data, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else ""
            raise RuntimeError(f"DeepSeek API 错误 HTTP {e.response.status_code}: {body}") from e
        result = response.json()
        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"DeepSeek API 返回格式异常: {result}") from e

    def _call_qwen(self) -> str:
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": self.model,
            "messages": self.conversation_history,
            "temperature": 0.3
        }

        response = self.session.post(url, headers=headers, json=data, timeout=30)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else ""
            raise RuntimeError(f"通义千问 API 错误 HTTP {e.response.status_code}: {body}") from e
        result = response.json()
        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"通义千问 API 返回格式异常: {result}") from e

    def _call_wenxin(self) -> str:
        if not self._wenxin_client:
            raise RuntimeError("百度文心助手 API Key 未配置")

        response = self._wenxin_client.chat.completions.create(
            model=self.model,
            messages=self.conversation_history,
            temperature=0.3
        )
        try:
            return response.choices[0].message.content
        except (KeyError, IndexError, AttributeError) as e:
            raise RuntimeError(f"百度文心助手 API 返回格式异常: {response}") from e

    def clear_history(self):
        import os
        self.conversation_history = []
        try:
            if os.path.exists(HISTORY_FILE):
                os.remove(HISTORY_FILE)
        except Exception:
            pass

    def get_history(self) -> list:
        return trim_history(self.conversation_history)

    def analyze_file(self, file_path: str, file_content: str = None) -> str:
        import os
        try:
            if file_content is not None:
                content = file_content
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

            file_ext = os.path.splitext(file_path)[1].lower()
            file_name = os.path.basename(file_path)
            total_chars = len(content)
            total_lines = content.count('\n') + 1

            MAX_PROMPT_CHARS = 15000

            if total_chars <= MAX_PROMPT_CHARS:
                sample = content
            else:
                sample = self._smart_sample(content, MAX_PROMPT_CHARS)

            prompt = f"""请分析以下文件内容：

文件名: {file_name}
文件类型: {file_ext}
文件统计: {total_chars} 字符，约 {total_lines} 行
{'（以下为文件关键内容采样）' if total_chars > MAX_PROMPT_CHARS else ''}

文件内容:
{sample}

请提供:
1. 文件概述（一两句话）
2. 主要内容总结
3. 关键信息提取
4. 建议或注意事项"""

            result = self._call_ai_with_fallback(prompt)

            if result and not result.startswith("错误") and not result.startswith("所有"):
                history_user_msg = f"【上传文件分析】\n文件名: {file_name}\n文件大小: {total_chars} 字符（约 {total_lines} 行）\n{'（大文件，AI 基于关键采样分析）' if total_chars > MAX_PROMPT_CHARS else ''}\n\n请记住这份文件的内容和你的分析结果，我接下来的问题可能会涉及这份文件。"
                self.conversation_history.append({"role": "user", "content": history_user_msg})
                self.conversation_history.append({"role": "assistant", "content": result})
                self.conversation_history = trim_history(self.conversation_history)
                save_history_to_file(self.conversation_history)

            return result

        except Exception as e:
            return f"文件分析失败: {str(e)}"

    def _smart_sample(self, text: str, max_chars: int = 15000) -> str:
        third = max_chars // 3
        total = len(text)
        start_portion = text[:third]
        mid_start = (total - third) // 2
        mid_portion = text[mid_start:mid_start + third]
        end_portion = text[-third:] if total >= third else text

        start_lines = start_portion.count('\n') + 1
        mid_lines = mid_portion.count('\n') + 1
        end_lines = end_portion.count('\n') + 1

        return (
            f"---【文件开头】(约前 {start_lines} 行) ---\n"
            f"{start_portion}\n\n"
            f"---【文件中间】(约 {mid_lines} 行) ---\n"
            f"{mid_portion}\n\n"
            f"---【文件结尾】(约后 {end_lines} 行) ---\n"
            f"{end_portion}"
        )

    def _call_ai_with_fallback(self, prompt: str) -> str:
        temp_history = self.conversation_history.copy()
        self.conversation_history = [{"role": "user", "content": prompt}]

        errors = []
        result = None
        for provider_name, api_key, model in self._available_text_providers():
            try:
                result = self._call_provider_text(provider_name, api_key, model)
                if provider_name != self.provider:
                    print(f"[fallback] {self.provider} 失败，切换到 {provider_name}")
                break
            except Exception as e:
                err_msg = str(e)
                self._handle_provider_error(provider_name, err_msg)
                errors.append(f"{provider_name}: {err_msg[:120]}")
                continue

        self.conversation_history = temp_history

        if result is not None:
            return result
        if not errors:
            return "错误：所有 AI 服务均未配置"
        if len(errors) == 1:
            return f"错误: {errors[0]}"
        return "所有服务不可用：\n" + "\n".join(f"  - {e}" for e in errors)

    def recognize_image(self, image_data: str, prompt: str = "请描述这张图片的内容") -> str:
        vision_fallback = [
            ("openai",  "gpt-4o-mini",      "openai",  self._call_openai_vision),
            ("qwen",    "qwen-vl-plus",      "qwen",    self._call_qwen_vision),
            ("wenxin",  "ernie-5.0",        "wenxin",  self._call_wenxin_vision),
            ("deepseek","deepseek-chat",    "deepseek",self._call_deepseek_vision),
        ]
        API_KEYS_MAP = {
            "openai":   API_KEYS.get("openai",   ""),
            "qwen":     API_KEYS.get("qwen",     ""),
            "wenxin":   API_KEYS.get("wenxin",   ""),
            "deepseek": API_KEYS.get("deepseek", ""),
        }

        ordered = []
        for entry in vision_fallback:
            if entry[0] == self.provider:
                ordered.append(entry)
        for entry in vision_fallback:
            if entry[0] != self.provider:
                ordered.append(entry)

        errors = []
        skipped = []
        for provider_name, default_model, key_label, call_fn in ordered:
            api_key = API_KEYS_MAP.get(key_label, "")
            if not api_key:
                continue
            if not self._is_provider_cooled_down(provider_name):
                info = self._provider_cooldown.get(provider_name, {})
                remaining = max(0, info.get("until", 0) - time.time())
                skipped.append((provider_name, remaining))
                continue
            try:
                result = call_fn(image_data, prompt, api_key=api_key,
                                 vision_model=default_model)
                if provider_name != self.provider:
                    print(f"[vision fallback] {self.provider} 失败，已自动切换到 {provider_name}")
                return result
            except Exception as e:
                err_msg = str(e)
                self._handle_provider_error(provider_name, err_msg)
                errors.append(f"{provider_name}: {err_msg[:160]}")
                continue

        if skipped:
            for name, remain in skipped:
                print(f"  [图片识别] 跳过 {name}（冷却中，剩 {remain:.0f}s）")

        if len(errors) == 1:
            return f"图片识别失败: {errors[0]}"
        return "图片识别失败，所有可用服务均不可用：\n" + "\n".join(f"  - {e}" for e in errors)

    def _call_openai_vision(self, image_data: str, prompt: str,
                            api_key: str = None, vision_model: str = None) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        key = api_key or self.api_key
        model = vision_model or self.vision_model or "gpt-4o-mini"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                        }
                    ]
                }
            ],
            "max_tokens": 1500
        }

        response = self.session.post(url, headers=headers, json=data, timeout=45)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else ""
            raise RuntimeError(f"HTTP {e.response.status_code}: {body}") from e
        return response.json()["choices"][0]["message"]["content"]

    def _call_deepseek_vision(self, image_data: str, prompt: str,
                              api_key: str = None, vision_model: str = None) -> str:
        url = "https://api.deepseek.com/v1/chat/completions"
        key = api_key or self.api_key
        model = vision_model or self.vision_model or "deepseek-chat"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                        }
                    ]
                }
            ],
            "max_tokens": 1500
        }

        response = self.session.post(url, headers=headers, json=data, timeout=45)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else ""
            raise RuntimeError(f"HTTP {e.response.status_code}: {body}") from e
        return response.json()["choices"][0]["message"]["content"]

    def _call_qwen_vision(self, image_data: str, prompt: str,
                          api_key: str = None, vision_model: str = None) -> str:
        key = api_key or self.api_key
        model = vision_model or self.vision_model or "qwen-vl-plus"
        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                        }
                    ]
                }
            ],
            "max_tokens": 1500
        }

        response = self.session.post(url, headers=headers, json=data, timeout=45)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else ""
            raise RuntimeError(f"HTTP {e.response.status_code}: {body}") from e
        result = response.json()
        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"返回格式异常: {result}") from e

    def _call_wenxin_vision(self, image_data: str, prompt: str,
                            api_key: str = None, vision_model: str = None) -> str:
        key = api_key or self.api_key
        model = vision_model or self.vision_model or "ernie-5.0"

        url = f"{QIANFAN_BASE_URL.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"}
                        }
                    ]
                }
            ],
            "max_tokens": 1500
        }

        response = self.session.post(url, headers=headers, json=data, timeout=45)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else ""
            raise RuntimeError(f"HTTP {e.response.status_code}: {body}") from e
        result = response.json()
        try:
            return result["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"返回格式异常: {result}") from e

    @staticmethod
    def _enhance_image_prompt(prompt: str) -> str:
        original = prompt.strip()
        quality_tags = ", high quality, highly detailed, masterpiece, professional photography, 8k resolution, sharp focus, cinematic lighting"
        style_map = [
            (("写真", "照片", "摄影", "photo", "photograph"), "portrait photo, DSLR camera, natural lighting"),
            (("动漫", "二次元", "anime", "cartoon"), "anime style, studio ghibli, vibrant colors"),
            (("油画", "oil paint"), "oil painting, renaissance style, classical art"),
            (("水墨", "国画", "中国风"), "chinese ink painting style, traditional art"),
            (("赛博朋克", "cyberpunk"), "cyberpunk style, neon lights, futuristic city"),
            (("仙侠", "玄幻"), "fantasy art, ethereal atmosphere, mystical"),
            (("古装", "汉服"), "traditional chinese costume, period drama, elegant"),
        ]
        extra = ""
        for keywords, tag in style_map:
            if any(kw.lower() in original.lower() for kw in keywords):
                extra = ", " + tag
                break
        celebrity_map = {
            "鞠婧祎": "Japanese-Chinese actress, short black hair, round face, delicate features, idol singer, 90s style",
            "迪丽热巴": "Uyghur ethnicity beauty, long wavy hair, deep eyes, tall figure, chinese actress",
            "杨幂": "Chinese actress, long hair, sharp features, fashion icon",
            "刘亦菲": "Chinese actress, elegant, fairy-like temperament, long black hair",
            "赵丽颖": "Chinese actress, round face, cute, gentle temperament",
            "易烊千玺": "Chinese actor and singer, handsome, youthful, talented",
            "王一博": "Chinese actor and idol, cool style, motorcycle lover",
            "肖战": "Chinese actor and singer, handsome, gentle features",
        }
        for name, desc in celebrity_map.items():
            if name in original:
                extra += f", {desc}, face reference"
                break
        return original + extra + quality_tags

    def generate_image(self, prompt: str, size: str = "1024x1024",
                      user_api_key: str = None, user_provider: str = None,
                      reference_image: str = None, use_local_sd: bool = True) -> dict:
        ALLOWED_SIZES = {"256x256", "512x512", "1024x1024", "1792x1024", "1024x1792"}
        if size not in ALLOWED_SIZES:
            size = "1024x1024"

        enhanced = self._enhance_image_prompt(prompt)
        print(f"  [图片生成] 原始提示: {prompt}")
        print(f"  [图片生成] 增强提示: {enhanced[:120]}...")
        if reference_image:
            print(f"  [图片生成] 参考图: 有 (len={len(reference_image)})")

        if use_local_sd:
            try:
                from core import sd_generator
                ok, msg = sd_generator.is_available()
                if ok:
                    print("  [图片生成] 尝试本地 Stable Diffusion...")
                    lora_name = None
                    for available_lora in sd_generator.list_available_loras():
                        if any(n in prompt.lower() for n in [available_lora.lower()]):
                            lora_name = available_lora
                            break
                    result = sd_generator.generate_local(
                        prompt=enhanced,
                        size=size,
                        reference_image=reference_image,
                        lora_name=lora_name,
                    )
                    if result.get("success"):
                        result["provider_used"] = "local-sd"
                        return result
                    print(f"  [图片生成] 本地SD失败: {result.get('error', '')[:100]}")
                else:
                    print(f"  [图片生成] 本地SD不可用: {msg}")
            except Exception as e:
                print(f"  [图片生成] 本地SD模块加载失败: {e}")

        image_fallback = [
            ("openai",  "dall-e-3",                  "openai",  self._call_dalle),
            ("wenxin",  "qwen-image",                "wenxin",  self._call_wenxin_image),
        ]
        API_KEYS_MAP = {
            "openai": API_KEYS.get("openai", ""),
            "qwen":   API_KEYS.get("qwen", ""),
            "wenxin": API_KEYS.get("wenxin", ""),
        }

        if user_api_key and user_provider:
            API_KEYS_MAP[user_provider] = user_api_key

        ordered = []
        if user_provider:
            for entry in image_fallback:
                if entry[0] == user_provider:
                    ordered.append(entry)
            is_user_image_mode = True
        else:
            is_user_image_mode = False
            for entry in image_fallback:
                ordered.append(entry)

        errors = []
        skipped = []
        for provider_name, default_model, key_label, call_fn in ordered:
            api_key = API_KEYS_MAP.get(key_label, "")
            if not api_key:
                continue
            if not self._is_provider_cooled_down(provider_name):
                info = self._provider_cooldown.get(provider_name, {})
                remaining = max(0, info.get("until", 0) - time.time())
                skipped.append((provider_name, remaining))
                continue
            try:
                result = call_fn(enhanced, size, api_key=api_key,
                                 image_model=default_model,
                                 reference_image=reference_image)
                if result.get("success"):
                    if provider_name != self.provider:
                        print(f"[image fallback] {self.provider} 失败，已自动切换到 {provider_name}")
                    return result
                err = result.get("error", "未知错误")
                self._handle_provider_error(provider_name, err)
                errors.append(f"{provider_name}: {err[:160]}")
            except Exception as e:
                err_str = str(e)
                self._handle_provider_error(provider_name, err_str)
                errors.append(f"{provider_name}: {err_str[:160]}")

        if skipped:
            for name, remain in skipped:
                print(f"  [图片生成] 跳过 {name}（冷却中，剩 {remain:.0f}s）")

        if len(errors) == 1:
            return {"success": False, "error": errors[0]}
        return {"success": False, "error": "图片生成失败，所有可用服务均不可用：\n" + "\n".join(f"  - {e}" for e in errors)}

    def _call_dalle(self, prompt: str, size: str,
                    api_key: str = None, image_model: str = None,
                    reference_image: str = None) -> dict:
        key = api_key or self.api_key
        model = image_model or self.image_model or "dall-e-3"

        if reference_image:
            url = "https://api.openai.com/v1/images/edits"
            headers = {
                "Authorization": f"Bearer {key}",
            }
            import io
            try:
                img_bytes = base64.b64decode(reference_image)
            except Exception:
                img_bytes = base64.b64decode(reference_image.split(",")[-1] if "," in reference_image else reference_image)

            import tempfile
            import os as _os
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(img_bytes)
                tmp_path = f.name
            try:
                data = {
                    "model": model,
                    "prompt": prompt[:4000],
                    "size": size,
                    "response_format": "b64_json",
                    "n": 1,
                }
                if model == "dall-e-3":
                    data["style"] = "vivid"
                with open(tmp_path, "rb") as img_file:
                    files = {"image": img_file}
                    form_data = {}
                    for k, v in data.items():
                        form_data[k] = (None, str(v))
                    response = self.session.post(url, headers=headers,
                                                 data=data, files=files, timeout=120)
            finally:
                try:
                    _os.unlink(tmp_path)
                except Exception:
                    pass
        else:
            url = "https://api.openai.com/v1/images/generations"
            headers = {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": model,
                "prompt": prompt[:4000],
                "n": 1,
                "size": size,
                "response_format": "b64_json"
            }
            if model == "dall-e-3":
                data["style"] = "vivid"
                data["quality"] = "hd"
            response = self.session.post(url, headers=headers, json=data, timeout=120)

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else ""
            return {"success": False, "error": f"HTTP {e.response.status_code}: {body}"}
        result = response.json()

        img_obj = result["data"][0]
        if "b64_json" in img_obj:
            image_data = img_obj["b64_json"]
        elif "url" in img_obj:
            img_resp = self.session.get(img_obj["url"], timeout=30)
            img_resp.raise_for_status()
            image_data = base64.b64encode(img_resp.content).decode("utf-8")
        else:
            return {"success": False, "error": f"返回格式异常: {result}"}
        return {
            "success": True,
            "image_data": image_data,
            "revised_prompt": img_obj.get("revised_prompt", "")
        }

    def _call_wenxin_image(self, prompt: str, size: str,
                           api_key: str = None, image_model: str = None,
                           reference_image: str = None) -> dict:
        key = api_key or self.api_key
        model = image_model or self.image_model or "ernie-image-v2"
        width, height = 1024, 1024
        if "x" in size:
            try:
                w, h = size.split("x")
                width, height = int(w), int(h)
            except ValueError:
                pass
        url = f"{QIANFAN_BASE_URL.rstrip('/')}/images/generations"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "prompt": prompt[:2000],
            "n": 1,
            "size": f"{width}x{height}",
            "response_format": "url"
        }
        if reference_image:
            clean_ref = reference_image.split(",")[-1] if "," in reference_image else reference_image
            data["image"] = clean_ref
            data["strength"] = 0.75

        response = self.session.post(url, headers=headers, json=data, timeout=120)
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            body = e.response.text[:500] if e.response is not None else ""
            return {"success": False, "error": f"HTTP {e.response.status_code}: {body}"}
        result = response.json()
        err = result.get("error")
        if err:
            ec = err.get("code", "")
            em = err.get("message", "")
            return {"success": False, "error": f"百度API错误 [{ec}]: {em}"}
        try:
            img_obj = result["data"][0]
            if "url" in img_obj:
                img_resp = self.session.get(img_obj["url"], timeout=30)
                img_resp.raise_for_status()
                image_data = base64.b64encode(img_resp.content).decode("utf-8")
            elif "b64_json" in img_obj and img_obj["b64_json"]:
                image_data = img_obj["b64_json"]
            else:
                return {"success": False, "error": f"返回格式异常: {result}"}
            return {
                "success": True,
                "image_data": image_data,
                "revised_prompt": result.get("data", [{}])[0].get("revised_prompt", "")
            }
        except (KeyError, IndexError) as e:
            return {"success": False, "error": f"返回格式异常: {result}"}

    def _call_wanx(self, prompt: str, size: str,
                   api_key: str = None, image_model: str = None,
                   reference_image: str = None) -> dict:
        key = api_key or self.api_key
        model = image_model or self.image_model or "wanx2.1-t2i-turbo"
        if reference_image and "wanx2.1-imageedit" not in model:
            model = "wanx2.1-imageedit"

        create_url = f"{self.dashscope_base_url}/services/aigc/text2image/image-synthesis"
        query_url = f"{self.dashscope_base_url}/tasks/{{task_id}}"

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable"
        }

        size_map = {
            "256x256":   "512*512",
            "512x512":   "512*512",
            "1024x1024": "1024*1024",
            "1792x1024": "1280*720",
            "1024x1792": "720*1280"
        }
        wanx_size = size_map.get(size, "1024*1024")

        data = {
            "model": model,
            "input": {
                "prompt": prompt[:2000]
            },
            "parameters": {
                "size": wanx_size,
                "n": 1
            }
        }

        if reference_image:
            clean_ref = reference_image.split(",")[-1] if "," in reference_image else reference_image
            data["input"]["image"] = clean_ref
            data["parameters"]["strength"] = 0.75

        print(f"  [图片生成] 正在提交任务 (模型: {model})...")
        t0 = time.time()

        try:
            response = self.session.post(create_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.HTTPError as e:
            http_code = e.response.status_code
            try:
                err_body = e.response.json()
                err_msg = err_body.get("message", str(e))
                err_code = err_body.get("code", "")
            except Exception:
                err_msg = e.response.text or str(e)
                err_code = ""

            print(f"  [图片生成] HTTP {http_code} [{err_code}]: {err_msg}")

            return {"success": False, "error": f"HTTP {http_code} [{err_code}]: {err_msg}"}

        task_id = result.get("output", {}).get("task_id")
        if not task_id:
            return {"success": False, "error": f"未获取到任务ID，响应: {result}"}

        print(f"  [图片生成] 任务已提交 (ID: {task_id})，等待生成...")

        task_headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json"
        }

        max_wait = 90
        poll_schedule = [1, 0.8, 0.8, 0.8, 0.8, 0.8, 1, 1, 1.2, 1.5, 1.5, 2] + [2] * 40
        elapsed = 0
        poll_idx = 0

        while elapsed < max_wait and poll_idx < len(poll_schedule):
            sleep_time = poll_schedule[poll_idx]
            poll_idx += 1
            time.sleep(sleep_time)
            elapsed += sleep_time

            try:
                q_response = self.session.get(
                    query_url.format(task_id=task_id),
                    headers=task_headers,
                    timeout=10
                )
                q_response.raise_for_status()
                q_result = q_response.json()
            except requests.exceptions.HTTPError:
                continue

            task_status = q_result.get("output", {}).get("task_status", "")

            if task_status == "SUCCEEDED":
                results = q_result.get("output", {}).get("results", [])
                if not results:
                    return {"success": False, "error": "任务成功但未返回图片结果"}

                image_url = results[0].get("url")
                if not image_url:
                    return {"success": False, "error": "任务成功但未返回图片URL"}

                print(f"  [图片生成] 生成完成，用时 {elapsed:.1f}s，正在下载...")

                try:
                    img_response = self.session.get(image_url, timeout=30, stream=True)
                    img_response.raise_for_status()
                    img_bytes = b"".join(img_response.iter_content(chunk_size=8192))
                    image_base64 = base64.b64encode(img_bytes).decode('utf-8')
                except Exception as e:
                    return {"success": False, "error": f"下载图片失败: {str(e)}"}

                total = time.time() - t0
                print(f"  [图片生成] 总耗时 {total:.1f}s")

                return {
                    "success": True,
                    "image_data": image_base64,
                    "revised_prompt": ""
                }

            elif task_status in ("FAILED", "CANCELED"):
                err_msg = q_result.get("output", {}).get("message", "未知错误")
                err_code = q_result.get("output", {}).get("code", "")
                return {"success": False, "error": f"图片生成任务失败 [{err_code}]: {err_msg}"}

        return {"success": False, "error": f"图片生成超时（{max_wait}秒），任务ID: {task_id}"}

    def generate_file(self, prompt: str, file_type: str = "txt") -> dict:
        try:
            type_prompts = {
                "txt": "请生成一个纯文本文件内容",
                "md": "请生成一个Markdown格式的文档",
                "json": "请生成一个JSON格式的数据，确保格式正确",
                "csv": "请生成CSV格式的数据，包含表头",
                "html": "请生成一个HTML文件内容，包含完整的HTML结构",
                "py": "请生成Python代码，确保语法正确",
                "js": "请生成JavaScript代码，确保语法正确"
            }

            base_prompt = type_prompts.get(file_type, "请生成文件内容")
            full_prompt = f"""{base_prompt}

需求: {prompt}

请只输出文件内容，不要包含任何解释或说明。"""

            temp_history = self.conversation_history.copy()
            self.conversation_history = [{"role": "user", "content": full_prompt}]

            errors = []
            content = None
            for provider_name, api_key, model in self._available_text_providers():
                try:
                    content = self._call_provider_text(provider_name, api_key, model)
                    if provider_name != self.provider:
                        print(f"[文件生成 fallback] {self.provider} 失败，已自动切换到 {provider_name}")
                    break
                except Exception as e:
                    err_msg = str(e)
                    self._handle_provider_error(provider_name, err_msg)
                    errors.append(f"{provider_name}: {err_msg[:160]}")
                    print(f"  [文件生成] {provider_name} 失败: {err_msg[:100]}")
                    continue

            self.conversation_history = temp_history

            if content is not None:
                return {
                    "success": True,
                    "content": content,
                    "file_type": file_type
                }
            if not errors:
                return {"success": False, "error": "所有 AI 服务均未配置"}
            if len(errors) == 1:
                return {"success": False, "error": errors[0]}
            return {"success": False, "error": "所有 AI 服务均不可用：\n" + "\n".join(f"  - {e}" for e in errors)}

        except Exception as e:
            return {"success": False, "error": f"文件生成失败: {str(e)}"}