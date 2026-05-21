from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

    def ready(self):
        from django.conf import settings
        if settings.EMAIL_BACKEND == 'django.core.mail.backends.console.EmailBackend':
            # Prevent quoted-printable line-wrapping that breaks long URLs in
            # console output. Done here rather than in settings to avoid
            # mutating global email.charset state at import time.
            import email.charset as _ec
            _ec.add_charset('utf-8', _ec.SHORTEST, None, 'utf-8')
