"""Prerequisite graph over courses.json: edge prereq -> course."""
import argparse
import json
from pathlib import Path

import networkx as nx

from src.engine.catalog import COURSES_PATH, PROCESSED, ROOT, RULES_PATH, load_catalog

GRAPH_JSON = PROCESSED / "prereq_graph.json"
GRAPH_PNG = ROOT / "supporting_files" / "A_collection" / "prereq_graph.png"
REPORT_JSON = ROOT / "supporting_files" / "B_engine" / "prereq_graph_report.json"


def build_graph(catalog):
    g = nx.DiGraph()
    for code in catalog.codes:
        c = catalog.course(code)
        g.add_node(code, title=c.get("title"), category=c.get("category"), level=c.get("level"),
                   in_catalog=True)
    for code in catalog.codes:
        c = catalog.course(code)
        hard = set(c.get("prerequisites") or [])
        rec = {p: g_["evidence"] for g_ in (c.get("recommended_background") or []) for p in g_["any_of"]}
        for p in sorted(hard | set(rec)):
            if p not in g:
                g.add_node(p, title=None, category=None, level=None, in_catalog=False)
            if p in hard:
                g.add_edge(p, code, type="hard", source=c.get("prereq_source"), evidence=c.get("prereq_evidence"))
            else:
                g.add_edge(p, code, type="recommended", source="course_plan", evidence=rec[p])
    return g


def edges_by_type(g):
    out = {}
    for _, _, d in g.edges(data=True):
        out[d["type"]] = out.get(d["type"], 0) + 1
    return dict(sorted(out.items()))


def missing_prereq_codes(g):
    """Prerequisite codes named by some course but absent from the catalog."""
    return sorted(n for n, d in g.nodes(data=True) if not d.get("in_catalog"))


def find_cycles(g):
    return sorted(sorted(c) for c in nx.simple_cycles(g))


def topological_order(g):
    """Stable topological order, or None if the graph has a cycle."""
    if not nx.is_directed_acyclic_graph(g):
        return None
    return list(nx.lexicographical_topological_sort(g))


def prereq_closure(g, code):
    """All direct and indirect prerequisites of a course."""
    return sorted(nx.ancestors(g, code)) if code in g else []


def export_json(g, path=GRAPH_JSON):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = nx.node_link_data(g, edges="links")
    data["nodes"] = sorted(data["nodes"], key=lambda n: n["id"])
    data["links"] = sorted(data["links"], key=lambda e: (e["source"], e["target"]))
    with open(path, "w") as f:
        json.dump(data, f, indent=1, sort_keys=True)


def plot(g, path=GRAPH_PNG):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    path.parent.mkdir(parents=True, exist_ok=True)
    linked = sorted({n for e in g.edges for n in e})
    sub = g.subgraph(linked) if linked else g
    colours = {"compulsory": "#d62728", "stream_core": "#ff7f0e", "basket": "#1f77b4",
               "open_elective": "#2ca02c", "requirement": "#7f7f7f", "ug_background": "#c5b0d5",
               None: "#ffffff"}
    fig, ax = plt.subplots(figsize=(12, 8))
    if sub.number_of_nodes():
        for layer, nodes in enumerate(nx.topological_generations(sub) if nx.is_directed_acyclic_graph(sub) else [list(sub)]):
            for n in nodes:
                sub.nodes[n]["layer"] = layer
        pos = nx.multipartite_layout(sub, subset_key="layer", align="horizontal") if nx.is_directed_acyclic_graph(sub) else nx.spring_layout(sub, seed=0)
        cols = [colours.get(sub.nodes[n].get("category"), "#cccccc") for n in sub]
        nx.draw_networkx_nodes(sub, pos, ax=ax, node_color=cols, edgecolors="black", node_size=1400)
        nx.draw_networkx_labels(sub, pos, ax=ax, font_size=7)
        for kind, style in (("hard", "solid"), ("recommended", "dashed")):
            es = [(u, v) for u, v, d in sub.edges(data=True) if d["type"] == kind]
            nx.draw_networkx_edges(sub, pos, edgelist=es, ax=ax, style=style, arrowsize=14, node_size=1400)
    ax.set_title(f"Prerequisite graph: {sub.number_of_nodes()} linked courses, edges {edges_by_type(g)} "
                 f"(solid = hard, dashed = recommended background, purple = UG background)\n"
                 f"({g.number_of_nodes() - sub.number_of_nodes()} courses without prerequisite links not shown)")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--courses", default=str(COURSES_PATH))
    ap.add_argument("--rules", default=str(RULES_PATH))
    args = ap.parse_args()
    catalog = load_catalog(args.courses, args.rules)
    g = build_graph(catalog)
    export_json(g)
    plot(g)
    report = {"courses_json": str(Path(args.courses).resolve().relative_to(ROOT)) if Path(args.courses).resolve().is_relative_to(ROOT) else args.courses,
              "nodes": g.number_of_nodes(), "edges": g.number_of_edges(), "edges_by_type": edges_by_type(g),
              "ug_background_nodes": sorted(n for n, d in g.nodes(data=True) if d.get("category") == "ug_background"),
              "missing_prereq_codes": missing_prereq_codes(g), "cycles": find_cycles(g),
              "topological_order": topological_order(g)}
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_JSON, "w") as f:
        json.dump(report, f, indent=1)
    print(f"nodes={report['nodes']} edges={report['edges_by_type']} missing={len(report['missing_prereq_codes'])} "
          f"cycles={len(report['cycles'])}")


if __name__ == "__main__":
    main()
