import os
import subprocess
import httpx
from langchain_openai import ChatOpenAI
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool

@tool
def read_file(path: str) -> str:
    """读取本地代码文件。"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"读取失败: {e}"

@tool
def run_command(cmd: str) -> str:
    """执行终端命令。"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15, encoding='utf-8', errors='replace')
        return f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    except Exception as e:
        return f"执行失败: {e}"

@tool
def write_file(path: str, content: str) -> str:
    """写入或修改代码文件。"""
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"成功写入文件: {path}"
    except Exception as e:
        return f"写入失败: {e}"

def run_agent(query: str, api_key: str, mode: str = "debug", lang: str = "C++", file_path: str = "sol.cpp", ui_lang: str = "中文"):
    # ==========================================
    # 🛡️ 终极防断线装甲 (修复 WinError 10054)
    # ==========================================
    # 1. 每次请求完立刻断开连接，不给服务器掐线的机会。
    # 2. 如果遇到网络波动，自动在后台重试 3 次。
    # 3. 强制使用 IPv4，防止部分校园网 IPv6 解析抽风。
    custom_http_client = httpx.Client(
        transport=httpx.HTTPTransport(local_address="0.0.0.0", retries=3),
        limits=httpx.Limits(max_keepalive_connections=0), # 不保留长连接
        timeout=httpx.Timeout(connect=15.0, read=120.0, write=15.0, pool=15.0)
    )

    llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=api_key,
        base_url="https://api.deepseek.com",
        temperature=0,
        http_client=custom_http_client,
        default_headers={"Connection": "close"} # 强杀长连接
    )
    
    lang_hint = f"请始终使用{ui_lang}回答。" if ui_lang == "中文" else "Please always answer in English."
    
    if mode == "review":
        sys_prompt = f"""你是 {lang} 算法竞赛教练。你现在的任务是【静态代码审计】。{lang_hint}
规则：
1. 可以使用 read_file 读取代码。
2. 绝对禁止修改代码，也尽量不要运行代码。
3. 找出语法错误、边界条件、复杂度问题。
4. 告诉学生哪里错了，把修改留给学生。"""
        current_tools = [read_file] 
        
    elif mode == "stress":
        compile_cmd = f"g++ -std=c++17 -O2 {file_path} -o sol && g++ -std=c++17 -O2 brute.cpp -o brute"
        sys_prompt = f"""你是 {lang} 算法竞赛教练。你现在的任务是【极限压力测试 (对拍)】。{lang_hint}
环境信息：
- 待测代码：{file_path}
- 暴力参考代码：brute.cpp
- 编译命令：{compile_cmd}
任务：
1. 用 write_file 生成 `gen.py`，随机生成符合题目规模的小数据并打印到标准输出。
2. 用 run_command 编译上述两份代码。
3. 写一个循环，用 gen.py 生成 100 次数据，对比 sol 和 brute 的输出。
4. 如果发现不一致，把出错的具体输入数据告诉我，并分析。
5. 【防死循环】：尝试 3 次没找到错就立刻停止总结。"""
        current_tools = [read_file, run_command, write_file]
        
    else:
        if lang == "C++":
            compile_cmd = f"g++ -std=c++17 -O2 -Wall {file_path} -o sol && ./sol"
        elif lang == "C":
            compile_cmd = f"gcc -std=c11 -O2 -Wall {file_path} -o sol && ./sol"
        elif lang == "Python":
            compile_cmd = f"python {file_path}"
        else:
            compile_cmd = f"javac {file_path} && java Main"
            
        sys_prompt = f"""你是 {lang} 算法竞赛教练。任务：【自动调试与重构】。{lang_hint}
规则：
1. 读代码，编译运行验证。
2. 文件路径：{file_path}
3. 运行命令参考：{compile_cmd}
4. 发现错误，用 write_file 覆盖修改原文件，再跑一次。
5. 【防死循环】：尝试 3 次失败立刻停止并说明原因。"""
        current_tools = [read_file, run_command, write_file]

    prompt = ChatPromptTemplate.from_messages([
        ("system", sys_prompt),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    agent = create_tool_calling_agent(llm, current_tools, prompt)
    executor = AgentExecutor(
        agent=agent, tools=current_tools, verbose=True,
        max_iterations=20, early_stopping_method="generate", handle_parsing_errors=True
    )
    
    result = executor.invoke({"input": query})
    return result["output"]