from typer import Typer

app = Typer(help="CLI for ML Network Monitor")


@app.command()
def monitor_start(interface: str = "eth0", packet_size: int = 128):
    print(f"Starting monitoring on {interface} with packet size {packet_size}")


@app.command()
def monitor_stop():
    print("Stopping monitoring")


@app.command()
def model_train(version: str = "v0.1.0"):
    print(f"Training model version {version}")


@app.command()
def model_activate(version: str = "v0.1.0"):
    print(f"Activating model version {version}")


if __name__ == "__main__":
    app()
