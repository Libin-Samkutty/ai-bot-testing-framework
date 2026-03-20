"""
GeminiConnector — generic Vertex AI / Gemini bot connector.

Subclass this to connect any Gemini model running on Vertex AI.
For HPV-specific usage see India_MSD/connectors/india_msd_hpv_gemini_connector.py.

Auth setup (one of):
  Option A - Service account JSON file:
    Set service_account_path in constructor, or:
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

  Option B - Application Default Credentials:
    gcloud auth application-default login

Install dependencies:
    pip install google-cloud-aiplatform google-auth
"""

import os
import logging
from pathlib import Path

from connectors.bot_connector import BotConnector

logger = logging.getLogger(__name__)


class GeminiConnector(BotConnector):
    """
    Generic connector for Gemini models running on Vertex AI.

    Parameters
    ----------
    project_id : str
        GCP project ID. Falls back to GCP_PROJECT_ID env var.
    location : str
        Vertex AI region. Falls back to GCP_LOCATION env var (default: us-central1).
    model_name : str
        Gemini model identifier (e.g. "gemini-2.5-flash", "gemini-1.5-pro").
        Default: gemini-2.5-flash
    system_prompt : str or None
        System instruction string passed to Gemini on every call.
        Mutually exclusive with prompt_path — provide one or neither.
    prompt_path : str or Path or None
        Path to a .txt file whose contents become the system prompt.
        Loaded once at construction time. Use this to keep prompts out of code
        and to get automatic cache invalidation when the file changes.
    temperature : float
        Sampling temperature (0.0-1.0). Default: 0.2
    top_p : float
        Nucleus sampling threshold. Default: 0.8
    top_k : int
        Top-k sampling. Default: 40
    max_output_tokens : int
        Maximum tokens in Gemini's response. Default: 8000
    service_account_path : str or None
        Path to a GCP service account JSON file.
        Falls back to GOOGLE_APPLICATION_CREDENTIALS env var.
    """

    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(
        self,
        project_id=None,
        location=None,
        model_name=None,
        system_prompt=None,
        prompt_path=None,
        temperature=0.2,
        top_p=0.8,
        top_k=40,
        max_output_tokens=8000,
        service_account_path=None,
    ):
        if system_prompt and prompt_path:
            raise ValueError(
                "Provide either system_prompt or prompt_path, not both."
            )

        self.project_id = project_id or os.environ.get("GCP_PROJECT_ID")
        self.location = location or os.environ.get("GCP_LOCATION", "us-central1")
        self.model_name = model_name or self.DEFAULT_MODEL
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.max_output_tokens = max_output_tokens
        self.service_account_path = (
            service_account_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        )

        if not self.project_id:
            raise ValueError(
                "GCP project_id is required. Set gcp.project_id in config.yaml "
                "or the GCP_PROJECT_ID environment variable."
            )

        # Resolve system prompt
        if prompt_path:
            prompt_path = Path(prompt_path)
            if not prompt_path.exists():
                raise FileNotFoundError(
                    f"System prompt file not found: {prompt_path}"
                )
            self.system_prompt = prompt_path.read_text(encoding="utf-8")
        else:
            self.system_prompt = system_prompt  # may be None (no system instruction)

        self._initialized = False

    def _init_vertexai(self):
        """Lazy-initialise Vertex AI SDK. Runs once before the first API call."""
        if self._initialized:
            return
        try:
            import vertexai
        except ImportError:
            raise ImportError(
                "google-cloud-aiplatform is not installed.\n"
                "Run: pip install google-cloud-aiplatform google-auth"
            )

        kwargs = {"project": self.project_id, "location": self.location}
        if self.service_account_path:
            from google.oauth2 import service_account
            credentials = service_account.Credentials.from_service_account_file(
                self.service_account_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
            kwargs["credentials"] = credentials

        vertexai.init(**kwargs)
        logger.info(
            "Vertex AI initialised — project=%s  location=%s  model=%s",
            self.project_id, self.location, self.model_name,
        )
        self._initialized = True

    def get_response(self, user_input: str, context: str = "") -> str:
        """
        Send user_input to Gemini and return the raw response text.

        Parameters
        ----------
        user_input : str
            The user's message / prompt.
        context : str
            Optional additional context. Appended to user_input when non-empty.

        Returns
        -------
        str
            Raw response text from Gemini (markdown fences stripped).
        """
        from vertexai.generative_models import GenerativeModel, GenerationConfig

        self._init_vertexai()

        gen_config = GenerationConfig(
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            max_output_tokens=self.max_output_tokens,
        )

        model_kwargs = {}
        if self.system_prompt:
            model_kwargs["system_instruction"] = self.system_prompt

        model = GenerativeModel(self.model_name, **model_kwargs)

        prompt = f"{user_input}\n\n{context}".strip() if context else user_input

        try:
            response = model.generate_content(prompt, generation_config=gen_config)
            raw = response.text.strip()

            # Strip markdown code fences that Gemini occasionally wraps around JSON
            if raw.startswith("```"):
                lines = raw.splitlines()
                raw = "\n".join(
                    line for line in lines if not line.strip().startswith("```")
                ).strip()

            return raw

        except Exception as exc:
            logger.error("Gemini API error for input %r: %s", user_input[:80], exc)
            raise RuntimeError(f"Gemini API error: {exc}") from exc
