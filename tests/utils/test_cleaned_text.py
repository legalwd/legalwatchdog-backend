from app.api.utils.cleaned_text import (
    cleaned_html,
    normalize_text,
)


def test_normalize_text():
    """
    Test that `normalize_text` correctly normalizes whitespace, newlines, and non-breaking spaces.
    """
    assert normalize_text("hello   world") == "hello world"
    assert normalize_text("a\n\nb") == "a b"
    assert normalize_text("\xa0test\xa0") == "test"


def test_cleaned_html_basic():
    """
    Test that `cleaned_html` extracts visible text while
    removing all HTML tags.
    """
    html = b"""
        <html>
            <body>
                <h1>Hello</h1>
                <p>World!</p>
            </body>
        </html>
    """

    result = cleaned_html(html)
    assert "Hello" in result
    assert "World" in result
    assert "<" not in result


def test_cleaned_html_removes_junk():
    """
    Test that `cleaned_html` removes scripts, styles, and junk elements.
    """
    html = b"""
        <html>
            <script>var x = 1</script>
            <style>.x { color: red }</style>
            <div id="cookie-banner">Accept Cookies</div>
            <p>Useful data</p>
        </html>
    """

    result = cleaned_html(html)

    assert "Useful data" in result
    assert "cookie" not in result.lower()
    assert "script" not in result.lower()
