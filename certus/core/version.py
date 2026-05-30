"""Central CERTUS application version."""

APP_VERSION = "26_05"
APP_DISPLAY_NAME = f"CERTUS 26_05"
APP_FULL_NAME = f"CERTUS Suite v{APP_VERSION}"


def get_app_version() -> str:
    return APP_VERSION


def get_app_display_name() -> str:
    return APP_DISPLAY_NAME


def get_app_full_name() -> str:
    return APP_FULL_NAME
