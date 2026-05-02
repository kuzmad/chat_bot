import streamlit as st
import requests
import uuid
from settings import SettingsFront
from llm import available_models

settings = SettingsFront()

if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("🤖 LangGraph AI Assistant")

# Сайдбар стал чище, осталась только смена модели и очистка
with st.sidebar:
    st.header("Настройки")
    selected_model = st.selectbox("Модель", list(available_models.keys()))
    if st.button("Очистить историю"):
        st.session_state.messages = []
        st.session_state.thread_id = str(uuid.uuid4())
        st.rerun()

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- НОВАЯ МАГИЯ ЗДЕСЬ ---
# Добавляем accept_file="multiple"
if user_action := st.chat_input("Напиши сообщение или прикрепи файл...", accept_file="multiple"):
    
    # Теперь user_action хранит в себе и текст (.text), и список файлов (.files)
    prompt_text = user_action.text
    uploaded_files = user_action.files

    # Формируем текст для отображения в UI (вдруг пользователь отправил только картинку без текста)
    display_text = prompt_text or ""
    if uploaded_files:
        file_names = ", ".join([f.name for f in uploaded_files])
        file_info = f"\n\n📎 Прикреплено: {file_names}"
        display_text = (display_text + file_info).strip()
    if not display_text:
        display_text = "📎 *Файлы прикреплены*"
    
    st.session_state.messages.append({"role": "user", "content": display_text})
    with st.chat_message("user"):
        st.markdown(display_text)

    # Собираем файлы для отправки на бэкенд FastAPI
    files_to_send = []
    if uploaded_files:
        for file in uploaded_files:
            files_to_send.append(("files", (file.name, file.getvalue(), file.type)))

    data = {
        "text": prompt_text or "", 
        "thread_id": st.session_state.thread_id,
        "model": selected_model
    }

    with st.chat_message("assistant"):
        try:
            response = requests.post(
                settings.api_url,
                data=data,
                files=files_to_send,
                stream=True,
                timeout=(settings.connection_timeout,
                          settings.read_timeout
                          )
                )
            response.raise_for_status()
            def stream_parser():
                for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                    if chunk:
                        yield chunk
            bot_reply = st.write_stream(stream_parser())
            st.session_state.messages.append({"role": "assistant", "content": bot_reply})
            
        except Exception as e:
            st.error(f"Ошибка связи с сервером: {e}")