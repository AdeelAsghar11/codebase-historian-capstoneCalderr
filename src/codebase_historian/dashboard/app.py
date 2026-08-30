"""
Streamlit Dashboard for Codebase Historian.
Interactive GraphRAG exploration: Knowledge Graph visualization, Historian queries,
Blast Radius prediction, Refactor Proposer <-> Critic debate under human gate,
Contributor Onboarding guides, and SQLite structured audit logs.
"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from codebase_historian.dashboard.graph_view import generate_graph_html
from codebase_historian.ingestion.github_resolver import (
    clone_github_repo,
    get_active_github_token,
    is_github_target,
    list_github_user_repos,
)
from codebase_historian.service import HistorianService

st.set_page_config(
    page_title="Codebase Historian",
    page_icon="📜",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def get_historian_service(repo_path: str = ".") -> HistorianService:
    """Initialize and cache the core HistorianService for the specified repository."""
    if is_github_target(repo_path):
        clean_path, _ = clone_github_repo(repo_path)
        clean_path = str(clean_path)
    else:
        clean_path = str(Path(repo_path).resolve())

    service = HistorianService(repo_path=clean_path)
    # Ingest repo if graph is empty
    if service.knowledge_graph.g.number_of_nodes() == 0:
        service.ingest(clean_path)
    return service


def main():
    # --- Determine active repository ---
    default_repo = os.environ.get("HISTORIAN_REPO_PATH", ".")
    if "active_repo_path" not in st.session_state:
        st.session_state["active_repo_path"] = str(Path(default_repo).resolve())

    # --- Sidebar: Active Repository Switcher ---
    st.sidebar.image("https://img.shields.io/badge/Codebase-Historian-blue?style=for-the-badge&logo=git", use_container_width=True)
    st.sidebar.markdown("### 📁 Select Repository")

    repo_source = st.sidebar.radio(
        "Choose repository source:",
        ["📁 Local Folder", "🐙 GitHub Online (My Repos)", "🌐 GitHub (URL / Shorthand)"],
        index=0,
    )

    if repo_source == "📁 Local Folder":
        repo_input = st.sidebar.text_input(
            "Local repository path:",
            value=st.session_state["active_repo_path"],
            help="Enter an absolute or relative path to any local Git repository.",
        )

        col_s1, col_s2 = st.sidebar.columns(2)
        with col_s1:
            if st.sidebar.button("📂 Switch", use_container_width=True):
                resolved = str(Path(repo_input).resolve())
                if Path(resolved).exists():
                    st.session_state["active_repo_path"] = resolved
                    st.rerun()
                else:
                    st.sidebar.error(f"Path does not exist: {repo_input}")

        with col_s2:
            if st.sidebar.button("🔄 Ingest", use_container_width=True):
                resolved = str(Path(repo_input).resolve())
                if Path(resolved).exists():
                    with st.spinner(f"Ingesting {resolved}..."):
                        srv = HistorianService(repo_path=resolved)
                        srv.ingest(resolved)
                        st.session_state["active_repo_path"] = resolved
                        st.cache_resource.clear()
                        st.rerun()
                else:
                    st.sidebar.error(f"Path does not exist: {repo_input}")

    elif repo_source == "🐙 GitHub Online (My Repos)":
        detected_token = get_active_github_token()
        token_input = st.sidebar.text_input(
            "GitHub Token (PAT):",
            value=detected_token or "",
            type="password",
            help="Auto-detected from GitHub CLI (`gh auth token`) or GITHUB_TOKEN environment variable. You can also paste a Personal Access Token.",
        )
        username_opt = st.sidebar.text_input(
            "Or GitHub Username:",
            placeholder="e.g. AdeelAsghar11",
            help="Enter your GitHub username to fetch your public repositories if token is not configured.",
        )

        if st.sidebar.button("🔍 Fetch My Repositories", use_container_width=True):
            with st.spinner("Fetching repositories from github.com..."):
                repos = list_github_user_repos(token=token_input or None, username=username_opt or None, limit=60)
                if repos:
                    st.session_state["gh_repos_list"] = repos
                    st.sidebar.success(f"Found {len(repos)} repositories!")
                else:
                    st.sidebar.warning("No repositories found. Check token or username.")

        if st.session_state.get("gh_repos_list"):
            repo_options = [r["full_name"] for r in st.session_state["gh_repos_list"]]
            selected_gh = st.sidebar.selectbox("Select repository from your account:", repo_options)
            chosen_meta = next((r for r in st.session_state["gh_repos_list"] if r["full_name"] == selected_gh), None)
            if chosen_meta:
                badge = "🔒 Private" if chosen_meta.get("private") else "🌍 Public"
                desc = chosen_meta.get("description") or "No description"
                st.sidebar.caption(f"{badge} • ⭐ {chosen_meta.get('stars', 0)}\n\n_{desc[:80]}_")

            if st.sidebar.button("🚀 Clone & Switch", type="primary", use_container_width=True):
                with st.spinner(f"Cloning and ingesting `{selected_gh}` from github.com..."):
                    try:
                        cloned_dir, method = clone_github_repo(selected_gh, token=token_input or None)
                        st.session_state["active_repo_path"] = str(cloned_dir)
                        st.cache_resource.clear()
                        srv = HistorianService(repo_path=str(cloned_dir))
                        srv.ingest(str(cloned_dir))
                        st.session_state["active_repo_path"] = str(cloned_dir)
                        st.success(f"Loaded `{selected_gh}` successfully via {method}!")
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"Failed to clone: {e}")

    elif repo_source == "🌐 GitHub (URL / Shorthand)":
        gh_url_input = st.sidebar.text_input(
            "GitHub URL or owner/repo:",
            placeholder="e.g. pallets/flask or https://github.com/...",
            help="Enter any public GitHub repository URL or shorthand.",
        )
        if st.sidebar.button("🚀 Clone & Switch", type="primary", use_container_width=True):
            if gh_url_input.strip():
                with st.spinner(f"Cloning and ingesting `{gh_url_input}`..."):
                    try:
                        cloned_dir, method = clone_github_repo(gh_url_input.strip())
                        st.session_state["active_repo_path"] = str(cloned_dir)
                        st.cache_resource.clear()
                        srv = HistorianService(repo_path=str(cloned_dir))
                        srv.ingest(str(cloned_dir))
                        st.success(f"Loaded `{gh_url_input}` successfully via {method}!")
                        st.rerun()
                    except Exception as e:
                        st.sidebar.error(f"Failed to clone: {e}")

    active_repo = st.session_state["active_repo_path"]
    st.sidebar.caption(f"📍 Active: `{active_repo}`")
    st.sidebar.divider()

    service = get_historian_service(active_repo)
    health = service.health()

    # --- Top Banner & Metrics ---
    st.title("📜 Codebase Historian")
    st.caption(f"Multi-Agent GraphRAG Platform for Codebase Intelligence — Repository: `{active_repo}`")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Graph Nodes", health["graph_node_count"])
    with col2:
        st.metric("Graph Edges", health["graph_edge_count"])
    with col3:
        st.metric("Indexed Docs", health["indexed_documents_count"])
    with col4:
        last_commit = (health["last_indexed_commit"] or "None")[:8]
        st.metric("Last Commit", last_commit)

    st.divider()

    # --- Sidebar Navigation ---
    st.sidebar.title("Navigation")
    page = st.sidebar.radio(
        "Select Workspace View:",
        [
            "📊 Knowledge Graph Visualizer",
            "🔍 Historian (Explain Code)",
            "💥 Blast Radius & Impact",
            "⚖️ Refactor Debate & Human Gate",
            "🧭 Contributor Onboarding",
            "📋 Audit Logs & Health",
        ],
    )

    # Get list of file nodes in graph for convenient selection
    file_nodes = sorted(
        [
            d.get("path", n)
            for n, d in service.knowledge_graph.g.nodes(data=True)
            if d.get("type") == "File" and d.get("path")
        ]
    )

    # --- Page 1: Knowledge Graph Visualizer ---
    if page == "📊 Knowledge Graph Visualizer":
        st.subheader("Interactive Knowledge Graph")
        st.markdown(
            "Explore files, commits, authors, and relations. Nodes are sized by graph centrality. Drag, zoom, and pan."
        )

        col_opts1, col_opts2 = st.columns([3, 1])
        with col_opts2:
            st.markdown("### Node Legend")
            st.markdown("- 🔵 **File** (AST & Path)")
            st.markdown("- 🟠 **Commit** (Git History)")
            st.markdown("- 🟣 **Author** (Contributors)")
            st.markdown("- 🟢 **Pull Request**")
            st.markdown("### Edge Legend")
            st.markdown("- 🔴 `CO_CHANGES_WITH`")
            st.markdown("- 🟢 `DEPENDS_ON`")
            st.markdown("- 🟡 `AUTHORED_BY`")

            max_nodes = st.slider("Max Nodes to Render", 10, 150, 60)
            max_edges = st.slider("Max Edges to Render", 10, 250, 100)
            edge_types = st.multiselect(
                "Filter Edge Types:",
                ["CO_CHANGES_WITH", "DEPENDS_ON", "AUTHORED_BY", "MODIFIES"],
                default=["CO_CHANGES_WITH", "DEPENDS_ON", "AUTHORED_BY"],
            )

        with col_opts1:
            html_content = generate_graph_html(
                service.knowledge_graph,
                max_nodes=max_nodes,
                max_edges=max_edges,
                edge_types=edge_types,
            )
            components.html(html_content, height=540)

        # Centrality table
        st.markdown("### Top Central Files (PageRank)")
        central_data = service.knowledge_graph.get_central_files(top_n=10)
        if central_data:
            df_central = pd.DataFrame(central_data)
            st.dataframe(df_central, use_container_width=True)

    # --- Page 2: Historian (Explain Code) ---
    elif page == "🔍 Historian (Explain Code)":
        st.subheader("Historian: Grounded Rationale Explanation")
        st.markdown("Discover *why* code exists, citing verifiable commits and pull requests.")

        default_target = "src/codebase_historian/config.py"
        selected_file = st.selectbox(
            "Select target file or enter path below:",
            file_nodes if file_nodes else [default_target],
            index=file_nodes.index(default_target) if default_target in file_nodes else 0,
        )

        col_q1, col_q2 = st.columns([4, 1])
        with col_q1:
            custom_target = st.text_input("Custom file path or symbol:", value=selected_file)
        with col_q2:
            explain_btn = st.button("🔍 Explain Code", type="primary", use_container_width=True)

        if explain_btn or "last_explained" in st.session_state:
            target_to_use = custom_target or selected_file
            if explain_btn:
                st.session_state["last_explained"] = target_to_use

            with st.spinner(f"Analyzing history and citations for `{target_to_use}`..."):
                resp = service.explain(target_to_use)

            st.markdown("### Historical Explanation")
            st.markdown(resp.answer)

            st.markdown(f"**Confidence:** `{resp.confidence * 100:.1f}%`")
            st.progress(resp.confidence)

            if resp.citations:
                st.markdown("### Grounding Citations")
                for c in resp.citations:
                    ref_title = f"Commit `{c.commit_sha[:8]}`" if c.commit_sha else f"PR #{c.pr_number}"
                    with st.expander(ref_title, expanded=True):
                        st.write(c.excerpt)

    # --- Page 3: Blast Radius & Impact ---
    elif page == "💥 Blast Radius & Impact":
        st.subheader("Blast Radius & Change Impact Prediction")
        st.markdown("Predict ripple effects using historical co-change coupling and AST dependencies.")

        col_in1, col_in2 = st.columns([1, 1])
        with col_in1:
            target_file = st.selectbox("Target File to Modify:", file_nodes if file_nodes else ["src/core.py"])
        with col_in2:
            change_desc = st.text_input("Proposed Change Description:", value=f"Modify {target_file} API")

        if st.button("💥 Predict Blast Radius", type="primary"):
            with st.spinner("Walking co-change and AST dependency graphs..."):
                resp = service.impact(change_description=change_desc, target=target_file)

            col_r1, col_r2 = st.columns(2)
            with col_r1:
                st.metric("Primary Evidence Basis", resp.evidence.upper())
            with col_r2:
                st.metric("Average Confidence", f"{resp.confidence * 100:.1f}%")

            if resp.affected_files:
                st.markdown("### Downstream Affected Files")
                for idx, f in enumerate(resp.affected_files, 1):
                    st.markdown(f"{idx}. `{f}` — [Evidence: `{resp.evidence}`]")
            else:
                st.info("No downstream files predicted to be impacted.")

    # --- Page 4: Refactor Debate & Human Gate ---
    elif page == "⚖️ Refactor Debate & Human Gate":
        st.subheader("Refactor Proposer ↔ Critic Adversarial Debate")
        st.markdown(
            "The Proposer drafts an improvement grounded in history. The Critic independently tries to refute it. "
            "**Mandatory Safety Property:** No suggestion is approved without explicit human sign-off."
        )

        refactor_target = st.selectbox("Select file to refactor:", file_nodes if file_nodes else ["src/core.py"])

        if st.button("⚡ Generate & Critique Refactoring", type="primary"):
            with st.spinner(f"Running Proposer <-> Critic debate for `{refactor_target}`..."):
                refactor_resp = service.suggest_refactor(refactor_target)
                st.session_state["current_refactor"] = refactor_resp
                st.session_state["human_verdict"] = None

        if "current_refactor" in st.session_state:
            res = st.session_state["current_refactor"]

            st.markdown("### 💡 Concrete Refactoring Proposal")
            st.markdown(res.proposal)

            st.markdown("### 🧐 Critic Adversarial Scrutiny")
            critic_status = "⚠️ Refuted" if res.critic_verdict.refuted else "✅ Approved by Critic"
            st.markdown(f"**Verdict:** {critic_status}")
            st.info(f"**Critic Notes:** {res.critic_verdict.notes}")

            st.markdown("---")
            st.markdown("### 🛡️ Human Approval Gate")
            st.warning(f"Current System Status: **`{res.status}`** (No automated changes ship without human sign-off)")

            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                if st.button("✅ Approve Refactoring", use_container_width=True):
                    st.session_state["human_verdict"] = "approved"
            with col_btn2:
                if st.button("❌ Reject Refactoring", use_container_width=True):
                    st.session_state["human_verdict"] = "rejected"

            if st.session_state.get("human_verdict") == "approved":
                st.success("🎉 Human approval granted! Proposal accepted for development.")
            elif st.session_state.get("human_verdict") == "rejected":
                st.error("🚫 Human rejected suggestion. Proposal discarded.")

    # --- Page 5: Contributor Onboarding ---
    elif page == "🧭 Contributor Onboarding":
        st.subheader("Contributor Onboarding & Architecture Guide")
        st.markdown("Automated contributor guide based on graph centrality rankings and root decisions.")

        guide = service.onboarding_guide()

        st.markdown("### 📖 Recommended Reading Order (Core Architectural Foundations)")
        for idx, file in enumerate(guide.reading_order, 1):
            st.markdown(f"**Step {idx}:** `{file}`")

        if guide.key_decisions:
            st.markdown("### 🏛️ Traced Key Architectural Decisions")
            for d in guide.key_decisions:
                st.markdown(f"- {d}")

    # --- Page 6: Audit Logs & Health ---
    elif page == "📋 Audit Logs & Health":
        st.subheader("System Health & Structured Audit Logs")
        st.markdown("Audit logs recorded into SQLite capturing caller ID, tool name, endpoint, and latency.")

        st.markdown("### System Freshness")
        st.json(health)

        st.markdown("### Structured Audit Log Stream")
        logs = service.memory_store.list_audit_logs(limit=30)
        if logs:
            data = [
                {
                    "Timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "Caller": log.caller_id,
                    "Tool": log.tool_name,
                    "Endpoint": log.endpoint,
                    "Latency (ms)": log.latency_ms,
                    "Status": log.status_code,
                }
                for log in logs
            ]
            st.dataframe(pd.DataFrame(data), use_container_width=True)
        else:
            st.info("No audit entries recorded yet.")


if __name__ == "__main__":
    main()
