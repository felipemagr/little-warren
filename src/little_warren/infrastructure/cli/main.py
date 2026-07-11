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
def analyze(
    ticker: str,
    days: int = typer.Option(None, help="Lookback window in days (defaults to settings)"),
    interval: str = typer.Option(None, help="Bar interval, e.g. 1d, 1wk"),
    reversal: float = typer.Option(0.05, help="Swing detection reversal threshold (fraction)"),
) -> None:
    """Analyse a ticker with the rules engine and print the pick, if any."""
    from datetime import date

    from little_warren.application.analysis_service.service import AnalysisService

    settings = get_settings()
    service = AnalysisService(provider=YFinanceProvider(), reversal=reversal)
    pick = service.analyze(
        ticker,
        as_of=date.today(),
        lookback_days=days or settings.default_lookback_days,
        interval=interval or settings.default_interval,
    )
    if pick is None:
        typer.echo(f"{ticker}: no actionable signal right now (all conditions must hold, FND-25)")
        return
    typer.echo(f"{pick.ticker}  {pick.direction.value.upper()}")
    typer.echo(f"  entry      {pick.entry:.2f}")
    typer.echo(f"  stop       {pick.stop:.2f}   (risk/unit {pick.risk_per_unit:.2f})")
    typer.echo(f"  target     {pick.target:.2f}" if pick.target else "  target     -")
    typer.echo(f"  confidence {pick.confidence:.0%}")
    typer.echo(f"  rules      {', '.join(pick.rules_fired)}")
    typer.echo(f"  notes      {pick.notes}")


@app.command()
def backtest(
    ticker: str,
    days: int = typer.Option(1825, help="History window in days (default ~5y)"),
    interval: str = typer.Option("1d", help="Bar interval"),
    reversal: float = typer.Option(0.05, help="Swing detection reversal threshold (fraction)"),
) -> None:
    """Walk-forward backtest of the rules engine on one ticker."""
    from datetime import date, timedelta

    from little_warren.application.analysis_service.service import AnalysisService
    from little_warren.application.backtest_service.service import BacktestService

    end = date.today()
    frame = YFinanceProvider().fetch_ohlcv(ticker, start=end - timedelta(days=days), end=end, interval=interval)
    report = BacktestService(AnalysisService(provider=None, reversal=reversal)).run(frame, ticker=ticker)

    typer.echo(f"{ticker}: {report.bars} bars, {len(report.trades)} trades")
    for trade in report.trades:
        pick = trade.pick
        r = f"{trade.r_multiple:+.2f}R" if trade.r_multiple is not None else "open"
        typer.echo(
            f"  {pick.as_of}  {pick.direction.value:5}  entry {pick.entry:9.2f}  stop {pick.stop:9.2f}  "
            f"target {pick.target:9.2f}  conf {pick.confidence:.0%}  -> {trade.outcome.value:6} {r}"
        )
    if report.hit_rate is not None:
        pf = f"{report.profit_factor:.2f}" if report.profit_factor is not None else "inf"
        typer.echo(f"  hit rate {report.hit_rate:.0%}  profit factor {pf}  avg {report.avg_r:+.2f}R")


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
