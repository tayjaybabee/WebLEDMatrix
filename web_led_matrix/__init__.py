from .app import MatrixControllerApp

__all__ = ["MatrixControllerApp", "run"]

def run() -> None:
    """Launch the Streamlit application."""
    MatrixControllerApp().run()


if __name__ == "__main__":
    run()
