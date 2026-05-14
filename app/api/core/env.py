"""Environment setup and cleanup utilities."""

import logging
import os

logger = logging.getLogger(__name__)


def cleanup_malformed_proxy_env():
    """Clean up malformed proxy environment variables.

    Removes proxy variables that contain placeholder strings like "port" or ":port"
    which can interfere with HTTP clients. This handles cases where environment
    variables are set to invalid values that prevent proper HTTP communication.

    Examples:
        >>> cleanup_malformed_proxy_env()
        # Removes HTTP_PROXY, HTTPS_PROXY, http_proxy, https_proxy if malformed
    """
    proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]

    for proxy_var in proxy_vars:
        if proxy_var in os.environ:
            proxy_value = os.environ.get(proxy_var)
            if proxy_value and ("port" in proxy_value or ":port" in proxy_value):
                logger.warning(
                    f"Removing malformed proxy variable {proxy_var}={proxy_value} from environment"
                )
                os.environ.pop(proxy_var, None)
