import os

import httpx
import typer
from typer import Typer

app = Typer(help="CLI for ML Network Monitor")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


@app.command()
def monitor_start(
    session_id: str,
    token: str = typer.Option(..., envvar="MLNM_TOKEN"),
):
    api_request("POST", f"/api/monitoring/sessions/{session_id}/start", token)


@app.command()
def monitor_stop(
    session_id: str,
    token: str = typer.Option(..., envvar="MLNM_TOKEN"),
):
    api_request("POST", f"/api/monitoring/sessions/{session_id}/stop", token)


@app.command()
def model_train(token: str = typer.Option(..., envvar="MLNM_TOKEN")):
    api_request("POST", "/api/models/train", token)


@app.command()
def model_activate(
    model_id: str,
    token: str = typer.Option(..., envvar="MLNM_TOKEN"),
):
    api_request("POST", "/api/models/activate", token, json={"model_id": model_id})


def api_request(method: str, path: str, token: str, **kwargs):
    try:
        response = httpx.request(
            method,
            f"{API_BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
            **kwargs,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        typer.echo(f"API error {exc.response.status_code}: {exc.response.text}", err=True)
        raise typer.Exit(code=1) from exc
    except httpx.RequestError as exc:
        typer.echo(f"Unable to reach the API: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(response.text)


if __name__ == "__main__":
    app()
