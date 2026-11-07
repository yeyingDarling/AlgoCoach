import streamlit as st
import os
import base64
import uuid
import time
from openai import OpenAI
from agent_core import run_agent
from supabase import create_client

st.set_page_config(page_title="专属算法教练", page_icon="🤖", layout="wide")

# ==========================================
# 1. 云数据库连接与超强防崩溃保护
# ==========================================
SUPABASE_URL = "https://hcfoywkwikmdpvjvudxf.supabase.co"      
SUPABASE_KEY = "sb_publishable_aOmd47HCxEQoFbSP8mNvjQ_Q8YhAW12"

if "supabase" not in st.session_state:
    st.session_state.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
supabase = st.session_state.supabase

def load_messages(username, session_id):
    retries = 3
    for i in range(retries):
        try:
            res = supabase.table("chat_history").select("*").eq("username", username).eq("session_id", session_id).order("id").execute()
            return [{"role": row["role"], "content": row["content"]} for row in res.data]
        except Exception as e:
            if i == retries - 1: # 最后一次还是失败
                st.warning(f"⚠️ 云端记忆读取失败(网络波动): 请检查网络或代理")
                return []
            time.sleep(1) # 失败后等 1 秒重试

def save_message(username, session_id, role, content):
    retries = 3
    for i in range(retries):
        try:
            supabase.table("chat_history").insert({"username": username, "session_id": session_id, "role": role, "content": content}).execute()
            return # 成功就退出
        except Exception as e:
            if i == retries - 1:
                st.warning(f"⚠️ 云端记忆保存失败(网络波动): 记录不会丢失，下次网络恢复可重试")
            time.sleep(1)

# ==========================================
# 2. 用户身份与 Key (加入防丢失记忆)
# ==========================================
st.sidebar.markdown("### 👤 用户身份")
if "saved_username" not in st.session_state:
    st.session_state.saved_username = ""
username = st.sidebar.text_input("输入你的昵称", value=st.session_state.saved_username)
st.session_state.saved_username = username 

st.sidebar.markdown("### 🔑 API 配置")
if "saved_api_key" not in st.session_state:
    st.session_state.saved_api_key = ""
user_api_key = st.sidebar.text_input("填入你的 DeepSeek API Key", type="password", value=st.session_state.saved_api_key)
st.session_state.saved_api_key = user_api_key

if not username or not user_api_key:
    st.warning("⚠️ 请先在左侧配置昵称和你的专属 API Key 才能使用。")
    st.stop()

# ==========================================
# 3. 会话与功能控制
# ==========================================
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

st.sidebar.markdown("---")
if st.sidebar.button("➕ 开启新对话"):
    st.session_state.session_id = str(uuid.uuid4())[:8]
    st.rerun()

st.sidebar.markdown("---")
ui_lang = st.sidebar.selectbox("UI & 回答语言：", ["中文", "English"])
lang_choice = st.sidebar.selectbox("编程语言：", ["C++", "C", "Python", "Java"])
mode = st.sidebar.radio("核心模式：", [
    "📖 启发式教学", "🔍 静态代码审计", "🛠️ 智能调试与重构", "⚔️ 极限压力测试 (对拍)"
])

# ==========================================
# 4. UI 渲染 (适配手机端)
# ==========================================
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background: radial-gradient(circle at 50% 0%, #1e1e24 0%, #0d0d12 100%); }
    [data-testid="stHeader"] { background: rgba(0,0,0,0) !important; }
    h1 { color: #ffffff !important; font-family: -apple-system, sans-serif; font-weight: 700; }
    [data-testid="stSidebar"] { background: rgba(20, 20, 25, 0.6) !important; backdrop-filter: blur(15px); border-right: 1px solid rgba(255, 255, 255, 0.1); }
    [data-testid="stChatMessage"] { background: rgba(30, 41, 59, 0.7) !important; border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 16px; padding: 20px; margin-bottom: 20px; backdrop-filter: blur(10px); }
    [data-testid="stChatInput"] { background: rgba(15, 23, 42, 0.8) !important; border: 1px solid #4facfe !important; border-radius: 12px !important; }
    [data-testid="stChatInput"] textarea { color: #ffffff !important; }
    
    @media (max-width: 768px) {
        [data-testid="stSidebar"] { min-width: 250px !important; width: 250px !important; }
        h1 { font-size: 24px !important; }
        .stMarkdown p { font-size: 15px !important; }
        [data-testid="stChatInput"] { padding: 10px !important; }
        [data-testid="stHeader"] { display: none !important; }
    }
</style>
""", unsafe_allow_html=True)

st.title("🤖 SYSTEM // 算法教练")
st.caption(f"用户: {username} | 会话: `{st.session_state.session_id}` | 语言: {lang_choice}")

uploaded_code_file = st.file_uploader(f"拖拽上传 {lang_choice} 代码", type=["cpp", "c", "py", "java", "txt", "cc"], label_visibility="collapsed")

current_file_path = ""
if uploaded_code_file is not None:
    ext = uploaded_code_file.name.split(".")[-1]
    if ext == "java":
        current_file_path = os.path.join(os.getcwd(), f"temp_{username}.java")
    else:
        current_file_path = os.path.join(os.getcwd(), f"temp_{username}.{ext}")
        
    with open(current_file_path, "wb") as f:
        f.write(uploaded_code_file.getbuffer())
    st.success(f"✅ 文件已就绪！保存为 `{os.path.basename(current_file_path)}`。")

client = OpenAI(api_key=user_api_key, base_url="https://api.deepseek.com")

if "messages" not in st.session_state or st.session_state.get("current_user") != username:
    st.session_state.messages = load_messages(username, st.session_state.session_id)
    st.session_state.current_user = username

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# 5. 聊天与 Agent 执行逻辑
# ==========================================
if prompt := st.chat_input("输入代码或指令..."):
    final_prompt = prompt
    if current_file_path:
        final_prompt = f"{prompt}\n\n(提示：请读取并分析当前路径下的 `{os.path.basename(current_file_path)}` 文件)"

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message(username, st.session_state.session_id, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)

    context_messages = st.session_state.messages[-20:]

    with st.chat_message("assistant"):
        if mode == "📖 启发式教学":
            sys_prompt = f"你是{lang_choice}教练。只讲思路，不要直接给完整代码。" if ui_lang=="中文" else f"You are a {lang_choice} coach. Only give hints."
            if current_file_path:
                 with open(current_file_path, "r", encoding="utf-8") as f:
                     code_content = f.read()
                 final_prompt = f"这是我的代码：\n```{lang_choice}\n{code_content}\n```\n\n我的问题是：{prompt}"
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": sys_prompt}] + context_messages[:-1] + [{"role": "user", "content": final_prompt}],
                temperature=0, stream=True,
            )
            full_response = ""
            placeholder = st.empty()
            for chunk in response:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
            
        else:
            agent_mode = "review" if mode == "🔍 静态代码审计" else ("stress" if mode == "⚔️ 极限压力测试 (对拍)" else "debug")
            file_target = os.path.basename(current_file_path) if current_file_path else "sol.cpp"
            
            with st.spinner(f"Agent 正在执行 [{mode}] 任务，请稍候..."):
                full_response = run_agent(final_prompt, api_key=user_api_key, mode=agent_mode, lang=lang_choice, file_path=file_target, ui_lang=ui_lang)
                st.markdown(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    save_message(username, st.session_state.session_id, "assistant", full_response)