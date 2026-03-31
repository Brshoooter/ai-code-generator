import logging
from typing import Generator
from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.exceptions import LangChainException
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CodeGenerationError(Exception):
    """Excepție custom pentru erorile serviciului de generare."""
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

        self._setup_chain()
        logger.info(f"GenerateResponseService initiat cu modelul {settings.ollama_model}")

    def _setup_chain(self) -> None:
        prompt_template = ChatPromptTemplate.from_messages(
            [
            ("system", """You are an expert software engineer specialized in clean, correct, and maintainable code.
            Your task is to generate source code based on the user's request.
            Rules:
            1. Return only code unless the user explicitly asks for explanations.
            2. Prefer clean and readable implementations.
            3. Follow best practices for the requested programming language.
            4. Add comments only when they help readability.
            5. Do not invent extra features that were not requested.
            6. If the request is ambiguous, make the safest reasonable assumption and keep the solution minimal.
            7. If the user specifies a framework, library, or language, follow it exactly.
            8. When generating Python code, keep it simple, modular, and easy to extend."""),
            ("human", "Please write the code for the following request: {user_prompt}")
            ]
        )

        self.chain = prompt_template | self.llm | StrOutputParser()

    def generate_code(self, user_prompt: str) -> Generator[str, None, None]:

        if not user_prompt.strip():
            raise CodeGenerationError("promptul nu poate fi gol")
            
        
        try:
            for chunk in self.chain.stream({"user_prompt": user_prompt}):
                yield chunk
        except LangChainException as e:
            logger.error(f"Eroare LangChain mid-stream: {e}")
            yield f"Eroare la comunicarea cu modelul {str(e)}"
        except Exception as e:
            logger.error(f"Eroare neprevazuta mid-stream: {e}")
            yield f"Eroare la generarea codului: {str(e)}"
 

