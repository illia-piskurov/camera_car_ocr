from app.openvino_bootstrap import configure_openvino_environment

configure_openvino_environment()

from app.orchestrator import run


if __name__ == "__main__":
    run()
