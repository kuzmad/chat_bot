import base64
import io
from typing import Annotated, TypedDict, List, Optional
from pypdf import PdfReader
from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import StreamingResponse
import uvicorn
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessageChunk
from langchain_core.runnables import RunnableConfig
from langchain_core.messages.utils import trim_messages
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from settings import SettingsBack
from llm import available_models, prompts

settings = SettingsBack()

# 1. Используем TypedDict для состояния
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

trimmer_by_count = trim_messages(
    max_tokens=settings.max_history_messages,           # Сохранит последние 4 сообщения
    strategy="last",
    token_counter=len,      # <-- Считаем каждое сообщение за 1 "токен"
    include_system=True,
)
    
# 2. Узел бота (чистая функция)
async def chatbot(state: ChatState, config: RunnableConfig) -> ChatState:
    system_prompt = SystemMessage(
        content=prompts["system_prompt"]
    )
    model_name = config.get("configurable", {}).get("model", settings.default_model)
    if model_name not in available_models:
        raise ValueError(f"Неизвестная модель: '{model_name}'. "
                         f"Доступные: {list(available_models.keys())}")
    llm = available_models[model_name]
    messages = [system_prompt] + trimmer_by_count.invoke(state["messages"])
    response = await llm.ainvoke(messages)
    return {"messages": [response]}


builder = StateGraph(ChatState)
builder.add_node("chatbot", chatbot)
builder.add_edge(START, "chatbot")
builder.add_edge("chatbot", END)

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)


app = FastAPI(title="LangGraph Chat API")

@app.post("/chat")
async def chat_endpoint(
    # Теперь мы принимаем данные не как JSON, а как Form (чтобы поддерживать файлы)
    text: str = Form("", description="Текст пользователя"),
    thread_id: str = Form(..., description="ID диалога"),
    model: str = Form(settings.default_model, description="Модель"),
    files: Optional[List[UploadFile]] = File(None, description="Загруженные файлы")
):
    try:
        config = {"configurable": {"thread_id": thread_id, "model": model}}
        
        # Подготавливаем структуру сообщения
        content_elements = [{"type": "text", "text": text}]
        attached_text = ""

        # Обрабатываем файлы прямо в оперативной памяти (без сохранения на диск!)
        if files:
            for file in files:
                file_bytes = await file.read() # Читаем байты

                if len(file_bytes) > settings.max_file_size_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Файл '{file.filename}' превышает лимит {settings.max_file_size_mb} МБ"
                    )

                mime_type = file.content_type

                if mime_type and mime_type.startswith("image/"):
                    encoded = base64.b64encode(file_bytes).decode("utf-8")
                    content_elements.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{encoded}"}
                    })
                elif file.filename.endswith(".pdf") or mime_type == "application/pdf":
                    # Читаем PDF из байтов в памяти
                    reader = PdfReader(io.BytesIO(file_bytes))
                    extracted = "\n".join([page.extract_text() or "" for page in reader.pages])
                    attached_text += f"\n\n--- Содержимое файла {file.filename} ---\n{extracted}"
                else:
                    # Считаем, что это обычный текст (.py, .txt и т.д.)
                    try:
                        attached_text += f"\n\n--- Содержимое файла {file.filename} ---\n{file_bytes.decode('utf-8')}"
                    except UnicodeDecodeError:
                        attached_text += f"\n\n--- Содержимое файла {file.filename} не удалось прочитать"


        # Приклеиваем текст из файлов к основному запросу пользователя
        if attached_text:
            content_elements[0]["text"] += attached_text

        message = HumanMessage(content=content_elements)

        async def event_generator():
            # graph.astream с stream_mode="messages" выдает чанки ответа модели по мере генерации
            async for chunk, metadata in graph.astream({"messages": [message]}, config=config, stream_mode="messages"):
                # Нас интересуют только кусочки ответа (AIMessageChunk), у которых есть текстовый контент
                if isinstance(chunk, AIMessageChunk) and chunk.content:
                    yield chunk.content

        # Возвращаем StreamingResponse вместо обычного JSON
        return StreamingResponse(event_generator(), media_type="text/plain")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)