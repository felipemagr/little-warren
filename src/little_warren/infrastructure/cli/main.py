"""little-warren CLI."""

from datetime import date, timedelta

import typer

from little_warren import __version__
from little_warren.config import get_settings
from little_warren.config.logging import configure_logging
from little_warren.infrastructure.data import YFinanceProvider

app = typer.Typer(help="Rules-based stock analysis: picks with stops and confidence.")


@app.callback()
def setup() -> None:
    """Configure logging before any command runs."""
    configure_logging()


@app.command()
def version() -> None:
    """Print the installed version."""
    typer.echo(f"little-warren {__version__}")


@app.command()
def fetch(
    ticker: str,
    days: int = typer.Option(None, help="Lookback window in days (defaults to settings)"),
    interval: str = typer.Option(None, help="Bar interval, e.g. 1d, 1wk"),
) -> None:
    """Fetch OHLCV data for a ticker and print the latest bars (data-source smoke test)."""
    settings = get_settings()
    lookback = days or settings.default_lookback_days
    end = date.today()
    start = end - timedelta(days=lookback)
    bar_interval = interval or settings.default_interval
    frame = YFinanceProvider().fetch_ohlcv(ticker, start=start, end=end, interval=bar_interval)
    typer.echo(frame.tail(10).to_string())
    typer.echo(f"\n{len(frame)} bars fetched for {ticker}")


if __name__ == "__main__":
    app()
