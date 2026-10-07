# AI智能问答Web应用

一个功能完整的AI智能问答系统，支持多种AI服务提供商（DeepSeek、OpenAI、通义千问、文心一言），并集成网络搜索功能。

## 功能特性

- **多平台支持**：DeepSeek、OpenAI、通义千问、文心一言
- **网络搜索**：自动从互联网搜索信息，AI基于搜索结果回答问题
- **Web界面**：现代化的响应式Web界面
- **对话历史**：支持多轮对话，可清空历史
- **灵活搜索**：支持全局搜索开关和单次强制搜索
- **实时交互**：流畅的聊天体验

## 项目结构

```
ai项目/
├── app.py                 # Flask后端应用
├── ai智能问答.py          # AI核心逻辑
├── requirements.txt       # Python依赖
├── templates/
│   └── index.html        # HTML前端页面
└── static/
    ├── style.css         # CSS样式
    └── script.js         # JavaScript交互
```

## 安装步骤

### 1. 安装Python依赖

```bash
pip install -r requirements.txt
```

依赖包：
- requests - HTTP请求
- beautifulsoup4 - 网页解析
- lxml - XML/HTML解析器
- flask - Web框架

### 2. 获取API Key

根据选择的AI服务提供商，获取相应的API Key：

- **DeepSeek**: https://platform.deepseek.com/
- **OpenAI**: https://platform.openai.com/
- **通义千问**: https://dashscope.aliyun.com/
- **文心一言**: https://cloud.baidu.com/product/wenxinworkshop

## 使用方法

### 方式一：命令行模式

```bash
python ai智能问答.py
```

按提示选择AI服务提供商，输入API Key，即可开始对话。

### 方式二：Web应用模式

```bash
python app.py
```

启动后访问：http://localhost:5000

#### Web界面操作：

1. **配置设置**
   - 点击右上角设置图标
   - 选择AI服务提供商
   - 输入模型名称（有默认值）
   - 输入API Key
   - 选择是否启用网络搜索
   - 点击保存

2. **开始对话**
   - 在输入框中输入问题
   - 按Enter或点击发送按钮
   - AI会基于配置和搜索结果回答

3. **快捷功能**
   - `search:问题` - 强制单次搜索
   - 网络搜索开关 - 切换全局搜索模式
   - 新对话 - 清空当前对话
   - 清空历史 - 清空所有对话历史

## 命令行模式快捷命令

- `quit` / `exit` / `q` - 退出程序
- `clear` - 清空对话历史
- `search` - 切换网络搜索开关
- `search:问题` - 强制单次搜索

## 网络搜索功能

系统使用DuckDuckGo进行网络搜索（无需API Key），搜索结果会自动注入到AI对话上下文中，AI可以基于最新的网络信息回答问题。

## 配置说明

### DeepSeek
- 默认模型：deepseek-chat
- API地址：https://api.deepseek.com/

### OpenAI
- 默认模型：gpt-3.5-turbo
- API地址：https://api.openai.com/

### 通义千问
- 默认模型：qwen-turbo
- API地址：https://dashscope.aliyuncs.com/

### 文心一言
- 默认模型：ernie-bot-turbo
- API地址：https://aip.baidubce.com/

## 注意事项

1. API Key请妥善保管，不要泄露
2. 网络搜索功能依赖互联网连接
3. 不同AI服务的API调用限制和费用不同
4. 生产环境部署时请修改Flask的secret_key

## 技术栈

- **后端**：Python + Flask
- **前端**：HTML + CSS + JavaScript
- **AI服务**：DeepSeek/OpenAI/通义千问/文心一言
- **网络搜索**：DuckDuckGo + BeautifulSoup

## 许可证

MIT License
