import streamlit as st
import os
import time
import uuid
import glob
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

def get_all_sessions(username):
    try:
        res = supabase.table("chat_history").select("session_id, content, id").eq("username", username).eq("role", "user").order("id").execute()
        sessions_dict = {}
        for row in res.data:
            s_id = row["session_id"]
            if s_id not in sessions_dict:
                title = row["content"][:12] + "..." if len(row["content"]) > 12 else row["content"]
                sessions_dict[s_id] = title
        return list(sessions_dict.items())
    except Exception:
        return []

def load_messages(username, session_id):
    retries = 3
    for i in range(retries):
        try:
            res = supabase.table("chat_history").select("*").eq("username", username).eq("session_id", session_id).order("id").execute()
            return [{"role": row["role"], "content": row["content"]} for row in res.data]
        except Exception:
            if i == retries - 1: return []
            time.sleep(1)

def save_message(username, session_id, role, content):
    retries = 3
    for i in range(retries):
        try:
            supabase.table("chat_history").insert({"username": username, "session_id": session_id, "role": role, "content": content}).execute()
            return
        except Exception:
            if i == retries - 1: st.warning("⚠️ 网络波动，记录暂存本地")
            time.sleep(1)

def clean_temp_files(username):
    """清理服务器上该用户的旧临时代码文件"""
    for f in glob.glob(f"temp_{username}.*"):
        try:
            os.remove(f)
        except:
            pass

# ==========================================
# 2. 用户身份与 Key
# ==========================================
st.sidebar.markdown("### 👤 用户身份")
if "saved_username" not in st.session_state:
    st.session_state.saved_username = ""

username = st.sidebar.text_input("输入你的昵称", value=st.session_state.saved_username)
st.session_state.saved_username = username 

if username:
    st.sidebar.info("💡 请牢记昵称！只要昵称相同，就能找回你的所有历史对话。")

st.sidebar.markdown("### 🔑 API 配置")
if "saved_api_key" not in st.session_state:
    st.session_state.saved_api_key = ""

user_api_key = st.sidebar.text_input("填入你的 DeepSeek API Key", type="password", value=st.session_state.saved_api_key)
st.session_state.saved_api_key = user_api_key

if not username or not user_api_key:
    st.warning("⚠️ 请先在左侧配置昵称和你的专属 API Key 才能使用。")
    st.stop()

# ==========================================
# 3. 多会话管理与功能控制
# ==========================================
st.sidebar.markdown("---")
st.sidebar.markdown("### 📂 我的对话")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

if st.sidebar.button("➕ 开启新对话", use_container_width=True):
    st.session_state.session_id = str(uuid.uuid4())[:8]
    clean_temp_files(username) # 新建对话时清理旧代码
    st.rerun()

sessions = get_all_sessions(username)
if not sessions:
    st.sidebar.caption("暂无历史对话")
else:
    for s_id, s_title in sessions:
        prefix = "▶ " if s_id == st.session_state.session_id else "💬 "
        if st.sidebar.button(f"{prefix}{s_title}", key=s_id, use_container_width=True):
            st.session_state.session_id = s_id
            st.rerun()

st.sidebar.markdown("---")

# 🎭 人设切换
persona = st.sidebar.selectbox("🎭 教练人设：", [
    "严谨导师", "温柔学姐", "大厂面试官", "暴躁老哥"
])
persona_prompt = {
    "严谨导师": "你是一位严谨的算法教练，注重代码规范和极端边界条件。",
    "温柔学姐": "你是一位温柔耐心的学姐，会鼓励学生，耐心指出错误。",
    "大厂面试官": "你是一位严厉的大厂面试官，非常看重时间复杂度和空间复杂度，如果学生写得很烂，你会直接指出。",
    "暴躁老哥": "你是一位脾气暴躁的ACM金牌老哥，看到低级错误（如没开long long、数组越界）会直接开骂，但技术极其牛逼。"
}[persona]

ui_lang = st.sidebar.selectbox("UI & 回答语言：", ["中文", "English"])
lang_choice = st.sidebar.selectbox("编程语言：", ["C++", "C", "Python", "Java"])
mode = st.sidebar.radio("核心模式：", [
    "📖 启发式教学", "🔍 静态代码审计", "🛠️ 智能调试与重构", "⚔️ 极限压力测试 (对拍)"
])

# ==========================================
# 4. UI 渲染
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
st.caption(f"用户: {username} | 人设: {persona} | 语言: {lang_choice}")

# 上传代码 & 粘贴报错
col1, col2 = st.columns(2)
with col1:
    st.markdown(f"**📁 上传 {lang_choice} 代码**")
    uploaded_code_file = st.file_uploader("上传代码文件", type=["cpp", "c", "py", "java", "txt", "cc"], label_visibility="collapsed")
with col2:
    st.markdown("**🐛 OJ 报错日志 (可选)**")
    oj_error_log = st.text_area("粘贴洛谷/CF的报错", placeholder="例如：Compilation Error... 或者 Wrong Answer on test 3...", label_visibility="collapsed", height=100)

current_file_path = ""
if uploaded_code_file is not None:
    clean_temp_files(username) # 每次上传新文件前，清理旧文件
    ext = uploaded_code_file.name.split(".")[-1]
    if ext == "java":
        current_file_path = os.path.join(os.getcwd(), f"temp_{username}.java")
    else:
        current_file_path = os.path.join(os.getcwd(), f"temp_{username}.{ext}")
        
    with open(current_file_path, "wb") as f:
        f.write(uploaded_code_file.getbuffer())
    st.success(f"✅ 文件已就绪！保存为 `{os.path.basename(current_file_path)}`。")

client = OpenAI(api_key=user_api_key, base_url="https://api.deepseek.com")

# 加载记忆
if "messages" not in st.session_state or st.session_state.get("current_session_id") != st.session_state.session_id:
    st.session_state.messages = load_messages(username, st.session_state.session_id)
    st.session_state.current_session_id = st.session_state.session_id

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# 5. 聊天与 Agent 执行逻辑
# ==========================================
if prompt := st.chat_input("输入代码或指令..."):
    
    # 组合最终发给 AI 的 Prompt
    final_prompt = prompt
    
    # 如果贴了报错日志
    if oj_error_log:
        final_prompt = f"【OJ 报错日志如下】\n{oj_error_log}\n\n【我的问题】\n{prompt}"
        
    # 如果传了代码，自动引导 AI 去读
    if current_file_path:
        final_prompt += f"\n\n(提示：请读取并分析当前路径下的 `{os.path.basename(current_file_path)}` 文件)"

    st.session_state.messages.append({"role": "user", "content": prompt})
    save_message(username, st.session_state.session_id, "user", prompt)
    with st.chat_message("user"):
        st.markdown(prompt)
        if oj_error_log:
            st.info("📎 已附带报错日志")

    context_messages = st.session_state.messages[-20:]

    with st.chat_message("assistant"):
        if mode == "📖 启发式教学":
            # 融入人设
            sys_prompt = f"{persona_prompt} 你是{lang_choice}教练。只讲思路，不要直接给完整代码。" if ui_lang=="中文" else f"You are a {lang_choice} coach. Only give hints."
            
            if current_file_path:
                 with open(current_file_path, "r", encoding="utf-8") as f:
                     code_content = f.read()
                 final_prompt = f"这是我的代码：\n```{lang_choice}\n{code_content}\n```\n\n{final_prompt}"
            
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
            
            # 把报错日志拼接到发给 Agent 的 Prompt 中
            agent_prompt = f"{persona_prompt}\n\n{final_prompt}"
            
            with st.spinner(f"Agent 正在执行 [{mode}] 任务，请稍候..."):
                full_response = run_agent(agent_prompt, api_key=user_api_key, mode=agent_mode, lang=lang_choice, file_path=file_target, ui_lang=ui_lang)
                st.markdown(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})
    save_message(username, st.session_state.session_id, "assistant", full_response)
