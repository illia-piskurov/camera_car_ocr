from app.config import Settings
from app.orchestrator import run


if __name__ == "__main__":
    run(Settings.from_env())
