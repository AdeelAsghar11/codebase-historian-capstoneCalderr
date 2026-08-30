"""
Typer and Rich CLI for Codebase Historian.
"""


import os
import unicodedata
from pathlib import Path

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from codebase_historian.ingestion.github_resolver import (
    clone_github_repo,
    is_github_target,
    list_github_user_repos,
)
from codebase_historian.service import HistorianService

app = typer.Typer(
    name="historian",
    help="Codebase Historian: Multi-agent GraphRAG platform for codebase intelligence.",
    add_completion=False,
)
console = Console()


def safe_console_str(text: str) -> str:
    """Sanitize strings so they never crash cp1252 or legacy Windows terminals."""
    if not text:
        return ""
    replacements = {
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "--",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u2022": "*",
        "\u202f": " ",
        "\u00a0": " ",
        "\u200b": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")


def get_cli_service(repo_path: str = ".") -> HistorianService:
    return HistorianService(repo_path=repo_path)


@app.command(name="ingest")
def ingest(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Path or GitHub repo to ingest"),
):
    """Ingest git commits, PRs/issues, and parse AST into the knowledge graph."""
    service = get_cli_service(repo_path)
    with console.status(f"[bold green]Ingesting repository at '{repo_path}'..."):
        res = service.ingest(repo_path)

    rprint(
        f"[bold green]Ingestion complete![/] Processed [cyan]{res.commits_ingested}[/] commits, "
        f"[cyan]{res.prs_ingested}[/] PRs, [cyan]{res.files_parsed}[/] files, and generated [cyan]{res.chunks_indexed}[/] index chunks."
    )


@app.command(name="explain")
def explain(
    target: str = typer.Argument(..., help="File path or symbol name to explain"),
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Path to repository"),
):
    """Explain why a file or symbol exists, citing commits, PRs, and discussions."""
    service = get_cli_service(repo_path)
    with console.status(f"[bold cyan]Querying historian agent for '{target}'..."):
        res = service.explain(target)

    console.print(Panel(safe_console_str(res.answer), title=f"Historian Explanation: {target}", border_style="cyan"))

    if res.citations:
        table = Table(title="Citations & Grounding Evidence", border_style="dim")
        table.add_column("Commit SHA / PR", style="yellow")
        table.add_column("Excerpt", style="white")
        for c in res.citations:
            ref = f"Commit {c.commit_sha[:8]}" if c.commit_sha else (f"PR #{c.pr_number}" if c.pr_number else "Reference")
            table.add_row(ref, safe_console_str(c.excerpt))
        console.print(table)

    rprint(f"[bold green]Confidence score:[/] {res.confidence * 100:.1f}%")


@app.command(name="impact")
def impact(
    change_description: str = typer.Argument(..., help="Diff or description of intended change"),
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Path to repository to inspect"),
):
    """Predict blast radius and affected files for a proposed change."""
    service = get_cli_service(repo_path)
    with console.status("[bold yellow]Walking co-change and AST dependency graphs..."):
        res = service.impact(change_description)

    if not res.affected_files:
        rprint("[yellow]No downstream files predicted to be impacted.[/]")
        return

    table = Table(title="Predicted Blast Radius", border_style="yellow")
    table.add_column("Affected File", style="cyan")
    table.add_column("Evidence Category", style="magenta")
    table.add_column("Confidence", style="green")

    for f in res.affected_files:
        table.add_row(f, res.evidence, f"{res.confidence * 100:.1f}%")

    console.print(table)


@app.command(name="refactor")
def refactor(
    target: str = typer.Argument(..., help="File path or symbol to propose refactor for"),
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Path to repository to inspect"),
):
    """Propose refactor under adversarial Critic review and mandatory human review gate."""
    service = get_cli_service(repo_path)
    with console.status(f"[bold magenta]Running Proposer <-> Critic debate for '{target}'..."):
        res = service.suggest_refactor(target)

    console.print(Panel(res.proposal, title=f"Refactoring Proposal: {target}", border_style="magenta"))

    critic_style = "green" if not res.critic_verdict.refuted else "red"
    console.print(
        Panel(
            f"[bold]Refuted:[/] {res.critic_verdict.refuted}\n[bold]Notes:[/] {res.critic_verdict.notes}",
            title="Critic Adversarial Review",
            border_style=critic_style,
        )
    )

    rprint(f"[bold yellow]Current Status:[/] [italic]{res.status}[/]")

    if res.status == "pending_human_review":
        approved = typer.confirm("Do you approve this refactoring suggestion?", default=False)
        if approved:
            rprint("[bold green]Human approval granted. Suggestion accepted.[/]")
        else:
            rprint("[bold red]Human rejected suggestion. Proposal discarded.[/]")


@app.command(name="onboard")
def onboard(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Path to repository to inspect"),
):
    """Generate contributor onboarding guide with central files and reading order."""
    service = get_cli_service(repo_path)
    with console.status("[bold blue]Generating onboarding guide..."):
        guide = service.onboarding_guide()

    table = Table(title="Contributor Onboarding Guide", border_style="blue")
    table.add_column("#", style="dim", width=4)
    table.add_column("Central File", style="cyan")

    for idx, f in enumerate(guide.central_files, 1):
        table.add_row(str(idx), f)

    console.print(table)

    if guide.key_decisions:
        dec_panel = "\n".join([f"- {d}" for d in guide.key_decisions])
        console.print(Panel(dec_panel, title="Key Traced Decisions", border_style="cyan"))


@app.command(name="health")
def health(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Path to repository to inspect"),
):
    """Display system status, graph node/edge counts, and index freshness."""
    service = get_cli_service(repo_path)
    data = service.health()

    table = Table(title="System Health & Index Status", border_style="green")
    table.add_column("Component", style="cyan")
    table.add_column("Status / Value", style="white")

    table.add_row("Service Status", data["status"])
    table.add_row("Last Indexed Commit", (data["last_indexed_commit"] or "None")[:8])
    table.add_row("Knowledge Graph Nodes", str(data["graph_node_count"]))
    table.add_row("Knowledge Graph Edges", str(data["graph_edge_count"]))
    table.add_row("Indexed Documents", str(data["indexed_documents_count"]))
    table.add_row("Degraded", str(data["degraded"]))

    console.print(table)


@app.command(name="mcp")
def run_mcp(
    transport: str = typer.Option("stdio", "--transport", "-t", help="Transport mode ('stdio' or 'sse')"),
):
    """Start FastMCP server exposing tools for Claude Desktop, Cursor, and MCP clients."""
    from codebase_historian.mcp_server.server import run_stdio

    rprint(f"[bold cyan]Starting Codebase Historian MCP Server ({transport})...[/]")
    run_stdio()


@app.command(name="dashboard")
def run_dashboard(
    repo_path: str = typer.Option(".", "--repo-path", "-r", help="Path to repository to inspect"),
    port: int = typer.Option(8501, "--port", "-p", help="Port to run Streamlit dashboard on"),
):
    """Launch the interactive Streamlit graph-visualization dashboard."""
    import subprocess
    import sys

    dashboard_path = Path(__file__).parent.parent / "dashboard" / "app.py"
    rprint(f"[bold green]Launching Streamlit Dashboard on port {port}...[/]")
    env = os.environ.copy()
    if is_github_target(repo_path):
        env["HISTORIAN_REPO_PATH"] = repo_path
    else:
        env["HISTORIAN_REPO_PATH"] = str(Path(repo_path).resolve())

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(dashboard_path),
            "--server.port",
            str(port),
        ],
        env=env,
        check=False,
    )


# --- GitHub Online CLI Subcommands ---
github_app = typer.Typer(
    name="github",
    help="GitHub online integration: list user repositories, clone, and switch.",
)
app.add_typer(github_app, name="github")


@github_app.command(name="list")
def github_list(
    token: str = typer.Option(None, "--token", "-t", help="GitHub Personal Access Token"),
    username: str = typer.Option(None, "--username", "-u", help="GitHub username to inspect"),
    limit: int = typer.Option(30, "--limit", "-l", help="Max repositories to list"),
):
    """List accessible repositories from github.com (uses GitHub CLI auth, GITHUB_TOKEN, or username)."""
    with console.status("[bold cyan]Fetching repositories from github.com..."):
        repos = list_github_user_repos(token=token, username=username, limit=limit)

    if not repos:
        rprint("[yellow]No repositories found. Ensure you are logged into GitHub CLI (`gh auth login`) or provide `--token` / `--username`.[/]")
        return

    table = Table(title="GitHub Online Repositories", border_style="cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Repository (owner/name)", style="green")
    table.add_column("Visibility", style="magenta")
    table.add_column("Description", style="white")

    for idx, r in enumerate(repos, 1):
        vis = "🔒 Private" if r.get("private") else "🌍 Public"
        table.add_row(str(idx), r["full_name"], vis, (r.get("description") or "No description")[:60])

    console.print(table)


@github_app.command(name="clone")
def github_clone(
    target: str = typer.Argument(..., help="GitHub repository URL or 'owner/repo' shorthand"),
    dest: str = typer.Option(None, "--dest", "-d", help="Custom destination directory"),
):
    """Clone a GitHub repository into local repository cache using GitHub CLI or Git."""
    with console.status(f"[bold green]Cloning GitHub repository '{target}'..."):
        path, method = clone_github_repo(target, dest_dir=dest)

    rprint(f"[bold green]Successfully cloned[/] [cyan]{target}[/] to [yellow]{path}[/] (via {method}).")
    rprint(f"To inspect: [bold cyan]historian dashboard -r {path}[/]")


if __name__ == "__main__":
    app()
