"""
WorkflowHub Stats
=================
Query statistics from the WorkflowHub API.

Subcommands:
  galaxy        Show workflows for a WorkflowHub project (default: Galaxy Australia, ID 54)
  leaderboard   Show contributor leaderboard ranked by workflow count
  topworkflows  Show the most-viewed or most-downloaded workflows across the entire site
  types         Show a breakdown of workflow counts by type (Galaxy, Nextflow, Snakemake, etc.)
  orgs          Show a leaderboard of spaces/projects ranked by workflow count
  all           Run all of the above subcommands in sequence using default settings

Usage:
    python3 workflowhub.py galaxy [--project-id ID] [--output FILE]
    python3 workflowhub.py leaderboard [--top N] [--highlight NAME] [--output FILE]
    python3 workflowhub.py topworkflows [--top N] [--sort-by views|downloads] [--max-workflows N] [--output FILE]
    python3 workflowhub.py types [--output FILE]
    python3 workflowhub.py orgs [--top N] [--output FILE]
    python3 workflowhub.py all

Examples:
    python3 workflowhub.py galaxy
    python3 workflowhub.py galaxy --project-id 12 --output my_project.csv
    python3 workflowhub.py leaderboard --top 100 --highlight "Smith"
    python3 workflowhub.py topworkflows --top 20 --sort-by downloads
    python3 workflowhub.py topworkflows --max-workflows 0   # check all (slow)
    python3 workflowhub.py types
    python3 workflowhub.py orgs --top 25
    python3 workflowhub.py all
"""

import argparse
import urllib.request
import json
import time
import csv
import re
import sys
from collections import defaultdict

BASE_URL = "https://workflowhub.eu"
PAGE_SIZE = 100

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) WorkflowHub-Stats/1.0",
}

HTML_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) WorkflowHub-Stats/1.0",
    "Accept": "text/html,application/xhtml+xml",
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def fetch_json(url):
    """Fetch JSON from a URL with retries."""
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < 2:
                print(f"  Retry {attempt + 1} for {url} ({e})")
                time.sleep(3)
            else:
                raise


def fetch_html(url):
    """Fetch HTML from a URL with retries."""
    req = urllib.request.Request(url, headers=HTML_HEADERS)
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            if attempt < 2:
                print(f"  Retry {attempt + 1} ({e})")
                time.sleep(3)
            else:
                raise


def extract_stats_from_html(html):
    """Extract Views and Downloads counts from a workflow HTML page."""
    views_match = re.search(r'<strong>Views:</strong>\s*(\d[\d,]*)', html)
    downloads_match = re.search(r'<strong>Downloads:</strong>\s*(\d[\d,]*)', html)
    views = int(views_match.group(1).replace(",", "")) if views_match else 0
    downloads = int(downloads_match.group(1).replace(",", "")) if downloads_match else 0
    return views, downloads


def get_workflow_details(wf_id):
    """Fetch metadata from the API and view/download counts from the HTML page."""
    result = {
        "id": wf_id,
        "title": "",
        "creators": "",
        "views": 0,
        "downloads": 0,
        "doi": "",
        "created": "",
        "updated": "",
    }

    try:
        data = fetch_json(f"{BASE_URL}/workflows/{wf_id}.json")
        if isinstance(data, dict) and "data" in data:
            attrs = data["data"].get("attributes", {})
            result["title"] = attrs.get("title", "")
            result["created"] = attrs.get("created_at", "")[:10]
            result["updated"] = attrs.get("updated_at", "")[:10]
            result["doi"] = attrs.get("doi", "") or ""

            creators_data = attrs.get("creators", [])
            if creators_data:
                names = []
                for c in creators_data:
                    if isinstance(c, dict):
                        name = (c.get("given_name", "") + " " + c.get("family_name", "")).strip()
                        names.append(name)
                    elif isinstance(c, str):
                        names.append(c)
                result["creators"] = "; ".join(names)

            other = attrs.get("other_creators", "")
            if other and not result["creators"]:
                result["creators"] = other
    except Exception as e:
        print(f"    API error: {e}")

    try:
        html = fetch_html(f"{BASE_URL}/workflows/{wf_id}")
        result["views"], result["downloads"] = extract_stats_from_html(html)
    except Exception as e:
        print(f"    HTML error: {e}")

    return result


def paginate_all(endpoint, label="items"):
    """Paginate through all pages of a JSON-API endpoint and return raw item dicts."""
    items_all = []
    page = 1
    while True:
        url = f"{BASE_URL}/{endpoint}?page={page}&per_page={PAGE_SIZE}"
        print(f"Fetching {label} page {page}...")
        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"  Error: {e}")
            break

        if isinstance(data, dict):
            items = data.get("data", data.get("items", []))
        elif isinstance(data, list):
            items = data
        else:
            break

        if not items:
            break

        items_all.extend(items)
        page += 1
        time.sleep(0.5)

    return items_all


# ---------------------------------------------------------------------------
# galaxy subcommand
# ---------------------------------------------------------------------------

def get_project_workflows(project_id):
    """Return a list of workflow ID dicts for the given project."""
    workflows = []

    url = f"{BASE_URL}/projects/{project_id}.json"
    print(f"Fetching project {project_id} data...")
    try:
        data = fetch_json(url)
        if isinstance(data, dict) and "data" in data:
            rels = data["data"].get("relationships", {})
            wf_rel = rels.get("workflows", {}).get("data", [])
            for wf in wf_rel:
                workflows.append({"id": wf["id"]})
            print(f"  Found {len(workflows)} workflow IDs from project data")
            return workflows
    except Exception:
        pass

    # Fallback: paginate through the project's workflow list
    page = 1
    while True:
        url = f"{BASE_URL}/projects/{project_id}/workflows.json?page={page}&per_page=100"
        print(f"Fetching workflows page {page}...")
        try:
            data = fetch_json(url)
        except Exception as e:
            print(f"  Error: {e}")
            break

        if isinstance(data, dict):
            items = data.get("data", data.get("items", []))
        elif isinstance(data, list):
            items = data
        else:
            break

        if not items:
            break

        for item in items:
            if isinstance(item, dict):
                workflows.append({"id": str(item.get("id", ""))})
            else:
                workflows.append({"id": str(item)})

        page += 1
        time.sleep(0.5)

    return workflows


def run_galaxy(args):
    print("=" * 70)
    print(f"WorkflowHub - Project {args.project_id} Workflows")
    print("=" * 70)
    print()

    workflows = get_project_workflows(args.project_id)
    print(f"\nFound {len(workflows)} workflows. Fetching details + stats...\n")

    results = []
    for i, wf in enumerate(workflows):
        try:
            details = get_workflow_details(wf["id"])
            results.append(details)
            print(f"  [{i+1}/{len(workflows)}] {details['id']}: {details['title'][:45]}  "
                  f"(Views: {details['views']:,}, Downloads: {details['downloads']:,})")
        except Exception as e:
            print(f"  [{i+1}/{len(workflows)}] Error for workflow {wf['id']}: {e}")
            results.append({"id": wf["id"], "title": "?", "creators": "",
                            "views": 0, "downloads": 0, "doi": "", "created": "", "updated": ""})
        time.sleep(0.5)

    results.sort(key=lambda x: x["views"], reverse=True)

    total_views = sum(r["views"] for r in results)
    total_downloads = sum(r["downloads"] for r in results)

    print("\n" + "=" * 70)
    print(f"PROJECT {args.project_id} WORKFLOWS - SORTED BY VIEWS")
    print("=" * 70)
    print(f"{'ID':<8}{'Title':<45}{'Views':<12}{'Downloads':<12}{'Creators'}")
    print("-" * 110)
    for r in results:
        print(f"{r['id']:<8}{r['title'][:43]:<45}{r['views']:<12,}{r['downloads']:<12,}"
              f"{r['creators'][:40]}")
    print("-" * 110)
    print(f"{'TOTAL':<8}{f'{len(results)} workflows':<45}{total_views:<12,}{total_downloads:<12,}")

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "id", "title", "creators", "views", "downloads", "doi", "created", "updated"
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to {args.output}")


# ---------------------------------------------------------------------------
# leaderboard subcommand
# ---------------------------------------------------------------------------

def get_all_people():
    """Paginate through all people registered on WorkflowHub."""
    raw = paginate_all("people.json", label="people")
    people = []
    for item in raw:
        if isinstance(item, dict):
            people.append({
                "id": str(item.get("id", "")),
                "name": item.get("attributes", {}).get("title",
                         item.get("title", item.get("name", f"Person {item.get('id', '?')}"))),
            })
    return people


def count_person_workflows(person_id):
    """Return the number of workflows associated with a person."""
    data = fetch_json(f"{BASE_URL}/people/{person_id}.json")

    if isinstance(data, dict) and "data" in data:
        relationships = data["data"].get("relationships", {})
        for key in ["created_workflows", "workflows", "submitted_workflows"]:
            if key in relationships:
                wf_data = relationships[key].get("data", [])
                if isinstance(wf_data, list):
                    return len(wf_data)

    if isinstance(data, dict):
        for key in ["workflows", "created_workflows", "submitted_workflows"]:
            if key in data:
                val = data[key]
                if isinstance(val, list):
                    return len(val)
                elif isinstance(val, int):
                    return val

    return 0


def run_leaderboard(args):
    print("=" * 60)
    print("WorkflowHub Contributor Leaderboard")
    print("=" * 60)
    print()

    people = get_all_people()
    print(f"\nFound {len(people)} people. Now counting workflows per person...\n")

    results = []
    for i, person in enumerate(people):
        try:
            count = count_person_workflows(person["id"])
            results.append({"id": person["id"], "name": person["name"], "workflows": count})
            if count > 0:
                print(f"  [{i+1}/{len(people)}] {person['name']}: {count} workflows")
            elif (i + 1) % 50 == 0:
                print(f"  [{i+1}/{len(people)}] processing...")
        except Exception as e:
            print(f"  [{i+1}/{len(people)}] Error for {person['name']}: {e}")
            results.append({"id": person["id"], "name": person["name"], "workflows": -1})
        time.sleep(0.3)

    results.sort(key=lambda x: x["workflows"], reverse=True)

    highlight = args.highlight.lower() if args.highlight else None

    print("\n" + "=" * 60)
    print(f"TOP {args.top} CONTRIBUTORS BY NUMBER OF WORKFLOWS")
    print("=" * 60)
    print(f"{'Rank':<6}{'Name':<40}{'Workflows':<10}")
    print("-" * 56)

    highlight_rank = None
    for rank, r in enumerate(results, 1):
        if r["workflows"] <= 0:
            break
        if highlight and highlight in r["name"].lower():
            highlight_rank = rank
        if rank <= args.top:
            marker = " <-- YOU" if highlight and highlight in r["name"].lower() else ""
            print(f"{rank:<6}{r['name'][:38]:<40}{r['workflows']:<10}{marker}")

    if highlight_rank and highlight_rank > args.top:
        r = results[highlight_rank - 1]
        print(f"...\n{highlight_rank:<6}{r['name'][:38]:<40}{r['workflows']:<10} <-- YOU")

    total_with_workflows = sum(1 for r in results if r["workflows"] > 0)
    print(f"\n{total_with_workflows} people have at least 1 workflow (out of {len(results)} registered)")
    if highlight_rank:
        r = results[highlight_rank - 1]
        print(f"{r['name']} ranks #{highlight_rank} out of {total_with_workflows} contributors with workflows")

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "name", "id", "workflows"])
        writer.writeheader()
        for rank, r in enumerate(results, 1):
            if r["workflows"] <= 0:
                break
            writer.writerow({"rank": rank, "name": r["name"], "id": r["id"], "workflows": r["workflows"]})

    print(f"\nFull results saved to {args.output}")


# ---------------------------------------------------------------------------
# topworkflows subcommand
# ---------------------------------------------------------------------------

def get_all_workflow_ids():
    """Paginate through all workflows on WorkflowHub and return basic metadata."""
    raw = paginate_all("workflows.json", label="workflows")
    workflows = []
    for item in raw:
        if isinstance(item, dict):
            attrs = item.get("attributes", {})
            workflows.append({
                "id": str(item.get("id", "")),
                "title": attrs.get("title", ""),
            })
    return workflows


def run_topworkflows(args):
    print("=" * 70)
    print("WorkflowHub - Top Workflows (Site-Wide)")
    print("=" * 70)
    print()

    all_workflows = get_all_workflow_ids()
    total_found = len(all_workflows)
    print(f"\nFound {total_found} workflows total.")

    if args.max_workflows and len(all_workflows) > args.max_workflows:
        print(f"Checking the first {args.max_workflows} (use --max-workflows 0 to check all — slow).")
        all_workflows = all_workflows[:args.max_workflows]
    else:
        print("Fetching view/download counts for each (this may take a while)...")

    print()

    results = []
    for i, wf in enumerate(all_workflows):
        try:
            details = get_workflow_details(wf["id"])
            results.append(details)
            print(f"  [{i+1}/{len(all_workflows)}] {details['id']}: {details['title'][:45]}  "
                  f"(Views: {details['views']:,}, Downloads: {details['downloads']:,})")
        except Exception as e:
            print(f"  [{i+1}/{len(all_workflows)}] Error for workflow {wf['id']}: {e}")
        time.sleep(0.5)

    results.sort(key=lambda x: x[args.sort_by], reverse=True)

    label = args.sort_by.capitalize()
    print("\n" + "=" * 70)
    print(f"TOP {args.top} WORKFLOWS BY {label.upper()}")
    print("=" * 70)
    print(f"{'ID':<8}{'Title':<45}{'Views':<12}{'Downloads':<12}{'Creators'}")
    print("-" * 110)
    for r in results[:args.top]:
        print(f"{r['id']:<8}{r['title'][:43]:<45}{r['views']:<12,}{r['downloads']:<12,}"
              f"{r['creators'][:40]}")

    fieldnames = ["id", "title", "creators", "views", "downloads", "doi", "created", "updated"]
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nFull results ({len(results)} workflows) saved to {args.output}")


# ---------------------------------------------------------------------------
# types subcommand
# ---------------------------------------------------------------------------

def get_workflow_type(wf_id):
    """Fetch the workflow_class title for a single workflow."""
    data = fetch_json(f"{BASE_URL}/workflows/{wf_id}.json")
    if isinstance(data, dict) and "data" in data:
        wc = data["data"].get("attributes", {}).get("workflow_class", {})
        if isinstance(wc, dict):
            return wc.get("title", wc.get("key", "Unknown")) or "Unknown"
    return "Unknown"


def run_types(args):
    print("=" * 60)
    print("WorkflowHub - Workflows by Type")
    print("=" * 60)
    print()

    all_wfs = get_all_workflow_ids()
    total_found = len(all_wfs)
    print(f"\nFound {total_found} workflows total.")

    if args.max_workflows and len(all_wfs) > args.max_workflows:
        print(f"Checking the first {args.max_workflows} (use --max-workflows 0 to check all — slow).")
        all_wfs = all_wfs[:args.max_workflows]
    else:
        print("Fetching type for each workflow (this may take a while)...")
    print()

    workflows = []
    for i, wf in enumerate(all_wfs):
        try:
            wf_type = get_workflow_type(wf["id"])
            workflows.append({"id": wf["id"], "title": wf.get("title", ""), "type": wf_type})
            if (i + 1) % 50 == 0:
                print(f"  [{i+1}/{len(all_wfs)}] processed...")
        except Exception as e:
            print(f"  [{i+1}/{len(all_wfs)}] Error for workflow {wf['id']}: {e}")
            workflows.append({"id": wf["id"], "title": wf.get("title", ""), "type": "Unknown"})
        time.sleep(0.3)

    print(f"\nProcessed {len(workflows)} workflows.\n")

    counts = defaultdict(int)
    for wf in workflows:
        counts[wf["type"]] += 1

    ranked = sorted(counts.items(), key=lambda x: x[1], reverse=True)

    print(f"{'Type':<35}{'Count':<10}{'Share'}")
    print("-" * 55)
    for wf_type, count in ranked:
        share = count / len(workflows) * 100
        print(f"{wf_type:<35}{count:<10}{share:.1f}%")
    print("-" * 55)
    print(f"{'TOTAL':<35}{len(workflows):<10}")

    results = [{"type": t, "count": c, "share_pct": f"{c/len(workflows)*100:.1f}"}
               for t, c in ranked]

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["type", "count", "share_pct"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to {args.output}")


# ---------------------------------------------------------------------------
# orgs subcommand
# ---------------------------------------------------------------------------

def get_all_spaces():
    """Paginate through all spaces/projects on WorkflowHub."""
    raw = paginate_all("projects.json", label="spaces")
    spaces = []
    for item in raw:
        if isinstance(item, dict):
            attrs = item.get("attributes", {})
            spaces.append({
                "id": str(item.get("id", "")),
                "name": attrs.get("title", item.get("title", f"Space {item.get('id', '?')}")),
            })
    return spaces


def count_space_workflows(space_id):
    """Return the number of workflows in a space/project."""
    data = fetch_json(f"{BASE_URL}/projects/{space_id}.json")

    if isinstance(data, dict) and "data" in data:
        rels = data["data"].get("relationships", {})
        for key in ["workflows", "created_workflows"]:
            if key in rels:
                wf_data = rels[key].get("data", [])
                if isinstance(wf_data, list):
                    return len(wf_data)

    if isinstance(data, dict):
        for key in ["workflows", "created_workflows"]:
            if key in data:
                val = data[key]
                if isinstance(val, list):
                    return len(val)
                elif isinstance(val, int):
                    return val

    return 0


def run_orgs(args):
    print("=" * 60)
    print("WorkflowHub - Space/Project Leaderboard")
    print("=" * 60)
    print()

    spaces = get_all_spaces()
    print(f"\nFound {len(spaces)} spaces. Now counting workflows per space...\n")

    results = []
    for i, space in enumerate(spaces):
        try:
            count = count_space_workflows(space["id"])
            results.append({"id": space["id"], "name": space["name"], "workflows": count})
            if count > 0:
                print(f"  [{i+1}/{len(spaces)}] {space['name']}: {count} workflows")
            elif (i + 1) % 20 == 0:
                print(f"  [{i+1}/{len(spaces)}] processing...")
        except Exception as e:
            print(f"  [{i+1}/{len(spaces)}] Error for {space['name']}: {e}")
            results.append({"id": space["id"], "name": space["name"], "workflows": -1})
        time.sleep(0.3)

    results.sort(key=lambda x: x["workflows"], reverse=True)

    print("\n" + "=" * 60)
    print(f"TOP {args.top} SPACES BY NUMBER OF WORKFLOWS")
    print("=" * 60)
    print(f"{'Rank':<6}{'Space':<40}{'Workflows':<10}")
    print("-" * 56)

    for rank, r in enumerate(results, 1):
        if rank > args.top or r["workflows"] <= 0:
            break
        print(f"{rank:<6}{r['name'][:38]:<40}{r['workflows']:<10}")

    total_with_workflows = sum(1 for r in results if r["workflows"] > 0)
    print(f"\n{total_with_workflows} spaces have at least 1 workflow (out of {len(results)} total)")

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["rank", "name", "id", "workflows"])
        writer.writeheader()
        for rank, r in enumerate(results, 1):
            if r["workflows"] <= 0:
                break
            writer.writerow({"rank": rank, "name": r["name"], "id": r["id"], "workflows": r["workflows"]})

    print(f"\nFull results saved to {args.output}")


# ---------------------------------------------------------------------------
# all subcommand
# ---------------------------------------------------------------------------

def run_all(args):
    """Run all subcommands in sequence using their default settings."""
    import types as _types

    print("\n" + "#" * 70)
    print("# Running ALL subcommands")
    print("#" * 70 + "\n")

    galaxy_args = _types.SimpleNamespace(
        project_id=54,
        output="workflowhub_galaxy.csv",
    )
    run_galaxy(galaxy_args)

    print("\n" + "#" * 70 + "\n")

    types_args = _types.SimpleNamespace(
        max_workflows=200,
        output="workflowhub_types.csv",
    )
    run_types(types_args)

    print("\n" + "#" * 70 + "\n")

    tw_args = _types.SimpleNamespace(
        top=50,
        sort_by="views",
        max_workflows=200,
        output="workflowhub_topworkflows.csv",
    )
    run_topworkflows(tw_args)

    print("\n" + "#" * 70 + "\n")

    orgs_args = _types.SimpleNamespace(
        top=50,
        output="workflowhub_orgs.csv",
    )
    run_orgs(orgs_args)

    print("\n" + "#" * 70 + "\n")

    lb_args = _types.SimpleNamespace(
        top=50,
        highlight=None,
        output="workflowhub_leaderboard.csv",
    )
    run_leaderboard(lb_args)

    print("\n" + "#" * 70)
    print("# All done! Output files:")
    print("#   workflowhub_galaxy.csv")
    print("#   workflowhub_types.csv")
    print("#   workflowhub_topworkflows.csv")
    print("#   workflowhub_orgs.csv")
    print("#   workflowhub_leaderboard.csv")
    print("#" * 70 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Query statistics from the WorkflowHub API.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # --- galaxy ---
    galaxy_parser = subparsers.add_parser(
        "galaxy",
        help="Show workflows for a WorkflowHub project",
        description="Fetch workflow metadata and view/download counts for a project.",
    )
    galaxy_parser.add_argument(
        "--project-id", type=int, default=54, metavar="ID",
        help="WorkflowHub project ID (default: 54 = Galaxy Australia)",
    )
    galaxy_parser.add_argument(
        "--output", default="workflowhub_galaxy.csv", metavar="FILE",
        help="Output CSV filename (default: workflowhub_galaxy.csv)",
    )
    galaxy_parser.set_defaults(func=run_galaxy)

    # --- leaderboard ---
    lb_parser = subparsers.add_parser(
        "leaderboard",
        help="Show contributor leaderboard ranked by workflow count",
        description="Rank all WorkflowHub contributors by number of workflows.",
    )
    lb_parser.add_argument(
        "--top", type=int, default=50, metavar="N",
        help="Number of top contributors to display (default: 50)",
    )
    lb_parser.add_argument(
        "--highlight", default=None, metavar="NAME",
        help="Highlight a contributor whose name contains this string (case-insensitive)",
    )
    lb_parser.add_argument(
        "--output", default="workflowhub_leaderboard.csv", metavar="FILE",
        help="Output CSV filename (default: workflowhub_leaderboard.csv)",
    )
    lb_parser.set_defaults(func=run_leaderboard)

    # --- topworkflows ---
    tw_parser = subparsers.add_parser(
        "topworkflows",
        help="Show the most-viewed or most-downloaded workflows across the entire site",
        description="Fetch view/download counts for all (or the first N) workflows site-wide.",
    )
    tw_parser.add_argument(
        "--top", type=int, default=50, metavar="N",
        help="Number of top workflows to display (default: 50)",
    )
    tw_parser.add_argument(
        "--sort-by", choices=["views", "downloads"], default="views",
        help="Stat to rank by (default: views)",
    )
    tw_parser.add_argument(
        "--max-workflows", type=int, default=200, metavar="N",
        help="Maximum number of workflows to check (default: 200; use 0 for all — slow)",
    )
    tw_parser.add_argument(
        "--output", default="workflowhub_topworkflows.csv", metavar="FILE",
        help="Output CSV filename (default: workflowhub_topworkflows.csv)",
    )
    tw_parser.set_defaults(func=run_topworkflows)

    # --- types ---
    types_parser = subparsers.add_parser(
        "types",
        help="Show a breakdown of workflow counts by type",
        description="Count workflows by type (Galaxy, Nextflow, Snakemake, CWL, etc.).",
    )
    types_parser.add_argument(
        "--max-workflows", type=int, default=200, metavar="N",
        help="Maximum number of workflows to check (default: 200; use 0 for all — slow)",
    )
    types_parser.add_argument(
        "--output", default="workflowhub_types.csv", metavar="FILE",
        help="Output CSV filename (default: workflowhub_types.csv)",
    )
    types_parser.set_defaults(func=run_types)

    # --- orgs ---
    orgs_parser = subparsers.add_parser(
        "orgs",
        help="Show a leaderboard of spaces/projects ranked by workflow count",
        description="Rank all WorkflowHub spaces/projects by number of workflows.",
    )
    orgs_parser.add_argument(
        "--top", type=int, default=50, metavar="N",
        help="Number of top spaces to display (default: 50)",
    )
    orgs_parser.add_argument(
        "--output", default="workflowhub_orgs.csv", metavar="FILE",
        help="Output CSV filename (default: workflowhub_orgs.csv)",
    )
    orgs_parser.set_defaults(func=run_orgs)

    # --- all ---
    all_parser = subparsers.add_parser(
        "all",
        help="Run all subcommands in sequence using default settings",
        description="Run galaxy, types, topworkflows, orgs, and leaderboard in sequence.",
    )
    all_parser.set_defaults(func=run_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
