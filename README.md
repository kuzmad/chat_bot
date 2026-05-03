# 🤖 LangGraph AI Assistant

Чат-бот с поддержкой истории диалога, потоковой генерацией ответов и загрузкой файлов. Построен на стеке **FastAPI + LangGraph + Streamlit** с доступом к моделям OpenAI и Anthropic через прокси.

---

## Архитектура

```
┌─────────────────────┐        HTTP (multipart/form-data)        ┌──────────────────────────┐
│   frontend.py       │  ──────────────────────────────────────► │   backend.py             │
│   Streamlit UI      │  ◄──────────────────────────────────────  │   FastAPI + LangGraph    │
│   :8501             │        StreamingResponse (text/plain)     │   :8000                  │
└─────────────────────┘                                           └──────────┬───────────────┘
                                                                             │
                                                                    ┌────────▼────────┐
                                                                    │   llm.py        │
                                                                    │   ProxyAPI      │
                                                                    │  (OpenAI-compat)│
                                                                    └─────────────────┘
```

Два независимых процесса запускаются одновременно через `honcho start` (см. [Запуск](#запуск)).

---

## Структура файлов

| Файл | Назначение |
|---|---|
| `backend.py` | FastAPI-сервер, LangGraph-граф, обработка файлов, стриминг |
| `frontend.py` | Streamlit-интерфейс, отображение чата, загрузка файлов |
| `llm.py` | Конфигурация моделей и системный промпт |
| `settings.py` | Настройки через Pydantic Settings / `.env` |
| `Procfile` | Описание процессов для honcho |
| `chat_bot.ipynb` | Jupyter-ноутбук (прототипирование/эксперименты) |

---

## Возможности

- **Потоковая генерация** — ответ модели отображается по мере появления токенов (`StreamingResponse` + `st.write_stream`)
- **Память диалога** — история хранится в `MemorySaver` (LangGraph), изолирована по `thread_id` (UUID на сессию)
- **Обрезка истории** — последние N сообщений (по умолчанию 4) передаются в контекст, чтобы не раздувать prompt
- **Загрузка файлов** (несколько файлов за раз):
  - 🖼️ Изображения → передаются как base64 `image_url` напрямую в LLM (vision)
  - 📄 PDF → текст извлекается через `pypdf` и добавляется к сообщению
  - 📝 Текстовые файлы (`.py`, `.txt` и др.) → декодируются UTF-8 и вставляются в контекст
- **Мультимодельность** — переключение между моделями прямо в UI
- **Лимит размера файла** — настраивается через `MAX_FILE_SIZE_MB` (по умолчанию 10 МБ), файлы не сохраняются на диск

---

## Доступные модели

| Ключ | Модель |
|---|---|
| `gpt_5.4_nano` | `openai/gpt-5.4-nano` (по умолчанию) |
| `gpt_5.4_mini` | `openai/gpt-5.4-mini` |
| `claude_sonnet_4.6` | `anthropic/claude-sonnet-4-6` |
| `claude_opus_4.6` | `anthropic/claude-opus-4-6` |

Все модели подключены через [ProxyAPI](https://proxyapi.ru) с OpenAI-совместимым интерфейсом (`ChatOpenAI` из `langchain-openai`).

---

## Конфигурация

Настройки читаются из файла `.env` через **Pydantic Settings**.

Создайте `.env` в корне проекта:

```env
# Обязательно
OPENAI_API_KEY=your_proxyapi_key_here

# Опционально (значения по умолчанию)
PROXY_BASE_URL=https://openai.api.proxyapi.ru/v1
DEFAULT_MODEL=gpt_5.4_nano
MAX_FILE_SIZE_MB=10
MAX_HISTORY_MESSAGES=4
HOST=0.0.0.0
PORT=8000

# Для фронтенда (если бэкенд запущен отдельно)
API_URL=http://localhost:8000/chat
CONNECTION_TIMEOUT=5
READ_TIMEOUT=120
```

---

## Запуск

### Через honcho (рекомендуется)

`honcho start` читает `Procfile` и запускает оба процесса параллельно с цветными префиксами в логах:

```
api:  uvicorn backend:app --host 0.0.0.0 --port 8000
web:  streamlit run frontend.py --server.port 8501 --server.address 127.0.0.1 --server.headless true
```

```bash
pip install honcho
honcho start
```

После запуска:
- **UI**: [http://localhost:8501](http://localhost:8501)
- **API docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

### Раздельный запуск

```bash
# Терминал 1 — бэкенд
uvicorn backend:app --host 0.0.0.0 --port 8000

# Терминал 2 — фронтенд
streamlit run frontend.py
```

---

## API

### `POST /chat`

Принимает `multipart/form-data`:

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `text` | `str` | Нет | Текст сообщения |
| `thread_id` | `str` | **Да** | ID диалога (для хранения истории) |
| `model` | `str` | Нет | Ключ модели из `available_models` |
| `files` | `UploadFile[]` | Нет | Прикреплённые файлы |

Возвращает: `StreamingResponse` (`text/plain`) — токены ответа в потоке.

---

## Зависимости

```
fastapi
uvicorn
streamlit
langgraph
langchain-core
langchain-openai
pypdf
pydantic-settings
honcho
requests
```

---

## Схема LangGraph-графа

```
START → chatbot → END
```

Простой линейный граф с одним узлом `chatbot`. Состояние (`ChatState`) содержит список сообщений с автоматическим мёрджем через `add_messages`. Checkpointing реализован через `MemorySaver` (in-memory).
