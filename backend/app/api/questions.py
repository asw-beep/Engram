from fastapi import APIRouter, HTTPException

from app.api.deps import ScopeDep, ServicesDep, SessionDep
from app.api.schemas import QuestionIn, QuestionOut
from app.questions import RetrievalUnavailable, answer_question

router = APIRouter(prefix="/api/questions")


@router.post("", response_model=QuestionOut)
def ask_question(body: QuestionIn, services: ServicesDep, session: SessionDep, scope: ScopeDep):
    question = body.question.strip()
    limit = services.settings.max_question_chars
    if not question or len(question) > limit:
        raise HTTPException(422, f"A question must be 1 to {limit} characters long.")
    try:
        return answer_question(
            session,
            question,
            scope,
            services.retriever,
            services.llm,
            services.embedder.count_tokens,
            services.settings,
        )
    except RetrievalUnavailable:
        raise HTTPException(503, "Search is unavailable right now. Try again shortly.") from None
