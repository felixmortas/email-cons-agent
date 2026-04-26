"""
Email Verification Utilities

A collection of functions for identifying verification emails and extracting 
codes or URLs using LLM-powered structured output.
"""

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage

from models.llm import EmailSelection, VerificationCode, VerificationURL


def select_verification_email(
    llm_name: str,
    website_name: str,
    emails_list: list,
) -> str:
    """
    Selects the most likely verification email from a list of recent emails.

    Args:
        llm_name:     Name of the LLM model to use (passed to init_chat_model).
        website_name: Name of the website/service we expect the code from.
        emails_list:  List of email metadata dicts returned by OutlookService.

    Returns:
        The email ID string of the selected email.

    Raises:
        ValueError: If no matching email is found (id == "not-found").
        Exception:  Any LLM invocation error is propagated to the caller.
    """
    model = init_chat_model(llm_name).with_structured_output(EmailSelection)

    prompt = (
        f"Given the website name '{website_name}', pick the most likely official email "
        f"of them for a verification code or email from this list: {emails_list}.\n"
        "Return the email ID in a JSON format without any other text or explanation.\n\n"
        "Example output:\n"
        '{"id": "AzKfsMHsdfgmfsDKGgfsKdf"}\n'
        '{"id": "not-found"}'
    )

    response = model.invoke([HumanMessage(content=prompt)])

    if response.id == "not-found":
        raise ValueError(
            f"No verification email found for website '{website_name}' "
            f"in the provided email list."
        )

    return response.id


def extract_verification_code(
    llm_name: str,
    email_content: str,
) -> str:
    """
    Extracts a verification code from raw email content.

    Args:
        llm_name:      Name of the LLM model to use (passed to init_chat_model).
        email_content: Raw text/HTML content of the email.

    Returns:
        The verification code as a string.

    Raises:
        ValueError: If no code is found in the email (code == "not-found").
        Exception:  Any LLM invocation error is propagated to the caller.
    """
    model = init_chat_model(llm_name).with_structured_output(VerificationCode)

    prompt = (
        "Find the verification code in this email.\n"
        "Return the verification code in a JSON format without any other text or explanation.\n\n"
        "Example output:\n"
        '{"code": "123654"}\n'
        '{"code": "not-found"}\n\n'
        f"# EMAIL CONTENT\n\n{email_content}"
    )

    response = model.invoke([HumanMessage(content=prompt)])

    if response.code == "not-found":
        raise ValueError("No verification code found in the email content.")

    return response.code

def extract_verification_url(    
    llm_name: str,
    email_content: str,
) -> str:
    """
    Extracts an email verification URL from raw email content.

    Args:
        llm_name:      Name of the LLM model to use (passed to init_chat_model).
        email_content: Raw text/HTML content of the email.

    Returns:
        The verification email URL as a string.

    Raises:
        ValueError: If no verification URL is found in the email (URL == "not-found").
        Exception:  Any LLM invocation error is propagated to the caller.
    """
    model = init_chat_model(llm_name).with_structured_output(VerificationURL)

    prompt = (
        "Find the email verification URL in this email.\n"
        "Return the verification URL in a JSON format without any other text or explanation.\n\n"
        "Example output:\n"
        '{"url": "https://www.mysite.com/verifyURL?code=8F2R8AAD9R28"}\n'
        '{"url": "not-found"}\n\n'
        f"# EMAIL CONTENT\n\n{email_content}"
    )

    response = model.invoke([HumanMessage(content=prompt)])

    if response.code == "not-found":
        raise ValueError("No verification code found in the email content.")

    return response.code
