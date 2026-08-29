"""
Typer and Rich CLI for Codebase Historian.
"""


import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from codebase_historian.service import HistorianService

app = typer.Typer(
    name="historian",
    help="Codebase Historian: Multi-agent GraphRAG platform for codebase intelligence.",
    add_completion=False,
)
console = Console()


def get_cli_service() -> HistorianService:
    return HistorianService()


@app.command(name="ingest")
def ingest(
    repo_path: str = typer.Argument(".", help="Path to repository to ingest (defaults to current directory)"),
):
    """Ingest git history, PR/issue data, and source AST into knowledge graph and index."""
    service = get_cli_service()
    with console.status("[bold green]Ingesting repository history and AST structure..."):
        result = service.ingest(repo_path)

    table = Table(title="Ingestion Summary", border_style="green")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column("Value", style="magenta")

    table.add_row("Repository Path", result.repo_path)
    table.add_row("Last Indexed Commit", (result.last_indexed_commit_sha or "")[:8])
    for k, v in result.stats.items():
        table.add_row(k.replace("_", " ").title(), str(v))

    console.print(table)


@app.command(name="explain")
def explain(
    target: str = typer.Argument(..., help="File path or symbol qualname to explain"),
):
    """Explain why a file or symbol exists, citing commits, PRs, and discussions."""
    service = get_cli_service()
    with console.status(f"[bold cyan]Querying historian agent for '{target}'..."):
        res = service.explain(target)

    console.print(Panel(res.answer, title=f"Historian Explanation: {target}", border_style="cyan"))

    if res.citations:
        table = Table(title="Citations & Grounding Evidence", border_style="dim")
        table.add_column("Commit SHA / PR", style="yellow")
        table.add_column("Excerpt", style="white")
        for c in res.citations:
            ref = f"Commit {c.commit_sha[:8]}" if c.commit_sha else (f"PR #{c.pr_number}" if c.pr_number else "Reference")
            table.add_row(ref, c.excerpt)
        console.print(table)

    rprint(f"[bold green]Confidence score:[/] {res.confidence * 100:.1f}%")


@app.command(name="impact")
def impact(
    change_description: str = typer.Argument(..., help="Diff or description of intended change"),
):
    """Predict blast radius and affected files for a proposed change."""
    service = get_cli_service()
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
):
    """Propose refactor under adversarial Critic review and mandatory human review gate."""
    service = get_cli_service()
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
def onboard():
    """Generate contributor onboarding guide with central files and reading order."""
    service = get_cli_service()
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
def health():
    """Display system status, graph node/edge counts, and index freshness."""
    service = get_cli_service()
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


if __name__ == "__main__":
    app()
