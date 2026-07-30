import uuid
import streamlit as st
from openai import OpenAI

# 페이지 기본 설정
st.set_page_config(page_title="AI 정보 선생님", page_icon="🤖", layout="wide")

# 비밀 금고(secrets)에서 API 키를 꺼내 접속 준비
client = OpenAI(
    api_key=st.secrets["SOLAR_API_KEY"],
    base_url="https://api.upstage.ai/v1",
)

# AI의 성격 (따뜻하지만 무관심한 선생님)
SYSTEM_PROMPT = (
    "너는 중고등학생에게 대답하는 정보 선생님이야. "
    "말투는 따뜻하고 부드럽지만, 학생의 일이나 사생활에 깊게 간섭하지 않고 쿨하고 무관심한 태도를 유지해. "
    "어려운 말은 쉬운 말로 바꿔 주고, 반드시 순수 한국어로만 답해"
)

# 세션 상태 초기화 (전체 대화 목록 및 현재 활성화된 채팅 ID)
if "chats" not in st.session_state:
    st.session_state.chats = {}

if "current_chat_id" not in st.session_state:
    st.session_state.current_chat_id = None


def create_new_chat():
    chat_id = str(uuid.uuid4())
    st.session_state.chats[chat_id] = {
        "title": "새 대화",
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}],
    }
    st.session_state.current_chat_id = chat_id


# 첫 방문 시 기본 대화 생성
if not st.session_state.chats or st.session_state.current_chat_id is None:
    create_new_chat()

# ================= 사이드바 (대화 목록 관리) =================
with st.sidebar:
    st.title("💬 대화 목록")

    # 새 대화 시작 버튼
    if st.button("➕ 새 대화 시작하기", use_container_width=True):
        create_new_chat()
        st.rerun()

    st.divider()

    # 대화 삭제 및 선택 UI
    chat_ids = list(st.session_state.chats.keys())
    for cid in chat_ids:
        chat = st.session_state.chats[cid]
        col_title, col_del = st.columns([0.8, 0.2])

        # 현재 대화 표시 및 선택 버튼
        is_current = cid == st.session_state.current_chat_id
        button_label = f"{'📌 ' if is_current else ''}{chat['title']}"

        with col_title:
            if st.button(button_label, key=f"select_{cid}", use_container_width=True):
                st.session_state.current_chat_id = cid
                st.rerun()

        # 대화 삭제 버튼
        with col_del:
            if st.button("🗑️", key=f"del_{cid}"):
                del st.session_state.chats[cid]

                # 삭제 후 남은 대화 처리
                remaining_ids = list(st.session_state.chats.keys())
                if remaining_ids:
                    st.session_state.current_chat_id = remaining_ids[0]
                else:
                    create_new_chat()
                st.rerun()

# ================= 메인 화면 (채팅 영역) =================
current_id = st.session_state.current_chat_id
current_chat = st.session_state.chats[current_id]

st.title("🤖 AI 정보 선생님")

# 현재 대화 내용 출력
for msg in current_chat["messages"]:
    if msg["role"] != "system":
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# 채팅 입력창
user_input = st.chat_input("궁금한 것을 물어보세요!")

if user_input:
    # 첫 질문일 경우 대화 제목을 첫 질문으로 변경
    if current_chat["title"] == "새 대화":
        current_chat["title"] = user_input[:15] + ("..." if len(user_input) > 15 else "")

    # 메시지 저장 및 화면 표시
    current_chat["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # AI 응답 호출
    with st.chat_message("assistant"):
        try:
            stream = client.chat.completions.create(
                model="solar-open2",
                messages=current_chat["messages"],
                reasoning_effort="none",
                stream=True,
            )
            answer = st.write_stream(
                chunk.choices[0].delta.content or ""
                for chunk in stream if chunk.choices
            )
            current_chat["messages"].append({"role": "assistant", "content": answer})
            st.rerun()
        except Exception:
            st.error("응답을 받지 못했습니다. 잠시 후 다시 보내 주세요.")
