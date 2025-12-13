"""Entry point for running logview as a module."""

from logview.app import LogViewApp


def main() -> None:
    """Run the LogView application."""
    app = LogViewApp()
    app.run()


if __name__ == "__main__":
    main()
