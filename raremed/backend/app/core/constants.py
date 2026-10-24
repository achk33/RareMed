"""Version and safety copy shared by the API."""

APP_VERSION = "0.6.0"
API_VERSION = "v1"
SERVICE_NAME = "raremed-ai"
DEFAULT_CONVERSATION_TITLE = "New conversation"
SESSION_COOKIE = "raremed_session"
USER_ROLES = ("user", "clinician", "admin")
STAFF_ROLES = ("clinician", "admin")
MESSAGE_STATUSES = ("complete", "interrupted", "generating")

DECISION_SUPPORT_NOTICE = (
    "RareMed AI is clinical decision support. It is not a clinically validated "
    "diagnostic tool and does not replace professional medical judgment."
)

SUPPORTED_LOCALES = ("en", "fr", "ar", "ary")
