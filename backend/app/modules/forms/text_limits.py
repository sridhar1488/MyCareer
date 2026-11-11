from typing import Annotated

from pydantic import AfterValidator, Field

from app.core.errors import AppError

HEADER_LIMIT = 500
RESPONSE_LIMIT = 1000
TEXT_MINIMUM = 2


def is_single_character(text):
    return len(text.strip()) == 1


def exceeds_limit(text, limit):
    # Match the browser's native maxlength, which counts UTF-16 code units.
    return len(text.encode("utf-16-le", errors="surrogatepass")) > limit * 2


def validate_text_change(text, previous, label, limit=RESPONSE_LIMIT):
    if text != previous and exceeds_limit(text, limit):
        raise AppError(422, "APPRAISAL_TEXT_LIMIT", f"{label} must be {limit} characters or fewer.")


def validate_answer_lengths(answers, previous):
    for key, text in answers.items():
        validate_text_change(text, previous.get(key), "Question response")


def validate_response(text):
    if exceeds_limit(text, RESPONSE_LIMIT):
        raise ValueError(f"Use {RESPONSE_LIMIT} characters or fewer")
    if is_single_character(text):
        raise ValueError(f"Use at least {TEXT_MINIMUM} characters")
    return text


ResponseText = Annotated[str, Field(max_length=RESPONSE_LIMIT), AfterValidator(validate_response)]
