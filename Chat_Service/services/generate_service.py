import logging
from typing import Generator
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.exceptions import LangChainException
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert software engineer specialized in clean, correct, and maintainable code.
Your task is to generate source code based on the user's request.
Rules:
1. Return only code unless the user explicitly asks for explanations.
2. Prefer clean and readable implementations.
3. Follow best practices for the requested programming language.
4. Add comments only when they help readability.
5. Do not invent extra features that were not requested.
6. If the request is ambiguous, make the safest reasonable assumption and keep the solution minimal.
7. If the user specifies a framework, library, or language, follow it exactly.
8. When generating Python code, keep it simple, modular, and easy to extend."""


class CodeGenerationError(Exception):
    pass


class GenerateResponseService:
    def __init__(self):
        self.llm = ChatOllama(
            model=settings.ollama_model,
            temperature=settings.ollama_temperature,
            repeat_penalty=settings.ollama_repeat_penalty,
            num_ctx=settings.ollama_num_ctx,
            keep_alive=settings.ollama_keep_alive,
            base_url=settings.ollama_base_url,
        )
        logger.info(f"GenerateResponseService initiat cu modelul {settings.ollama_model}")

    def generate_code(self, messages: list[dict]) -> Generator[str, None, None]:
        if not messages or messages[-1]["role"] != "user":
            raise CodeGenerationError("Ultimul mesaj trebuie sa fie de la user")

        # system prompt-ul e adaugat pe server — frontend-ul nu il poate modifica
        lc_messages = [SystemMessage(content=SYSTEM_PROMPT)]
        for m in messages:
            if m["role"] == "user":
                lc_messages.append(HumanMessage(content=m["content"]))
            else:
                lc_messages.append(AIMessage(content=m["content"]))

        try:
            # llm.stream cu lista returneaza AIMessageChunk — accesam .content pentru string
            for chunk in self.llm.stream(lc_messages):
                yield chunk.content
        except LangChainException as e:
            logger.error(f"Eroare LangChain mid-stream: {e}")
            yield f"Eroare la comunicarea cu modelul: {str(e)}"
        except Exception as e:
            logger.error(f"Eroare neprevazuta mid-stream: {e}")
            yield f"Eroare la generarea codului: {str(e)}"


