import config
from guest import GuestUploadLimiter
from mailbox import DoveadmMailbox
from oauth import create_oauth_registry

oauth = create_oauth_registry()
mailbox = DoveadmMailbox(config.DOVEADM_URL, config.DOVEADM_PASSWORD)
guest_upload_limiter = GuestUploadLimiter(
    config.GUEST_UPLOADS_PER_WINDOW,
    config.GUEST_GLOBAL_UPLOADS_PER_WINDOW,
    config.GUEST_UPLOAD_WINDOW_SECONDS,
    config.GUEST_CONCURRENT_UPLOADS,
)
