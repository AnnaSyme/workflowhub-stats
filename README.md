# workflowhub-stats

A command-line tool for querying statistics from the [WorkflowHub](https://workflowhub.eu) API.

Built by [Anna Syme](https://github.com/annasyme) with [Claude](https://claude.ai) (Anthropic).


## What it does

WorkflowHub is a registry for scientific workflows. This tool lets you query it from the command line to answer questions like:

- Which workflows in a project have the most views and downloads?
- Which workflows are most popular across the entire site?
- What workflow types (Galaxy, Nextflow, Snakemake, etc.) are most common?
- Which spaces/projects have the most workflows?
- Who are the top contributors by number of workflows?

Results are printed to the terminal and saved as a CSV file.


## Requirements

Python 3.



## Installation

Download `workflowhub.py` to your computer. 



## Usage

Open a terminal, navigate to the folder where you saved the script, and run one of the following commands.

### `galaxy` — workflows for a project

Fetches workflow metadata and view/download counts for a WorkflowHub project.

```bash
python3 workflowhub.py galaxy
```

Defaults to the Galaxy Australia project (ID 54). To query a different project:

```bash
python3 workflowhub.py galaxy --project-id 12
```

| Option | Description | Default |
|---|---|---|
| `--project-id ID` | WorkflowHub project ID | `54` (Galaxy Australia) |
| `--output FILE` | CSV file to save results to | `workflowhub_galaxy.csv` |

---

### `topworkflows` — most viewed/downloaded workflows site-wide

Fetches view and download counts for workflows across the entire site and ranks them.

```bash
python3 workflowhub.py topworkflows
```

> **Note:** This command needs to fetch each workflow's HTML page to get view/download counts, which takes time. By default it checks the first 200 workflows. Use `--max-workflows 0` to check all of them (slow).

| Option | Description | Default |
|---|---|---|
| `--top N` | How many workflows to display | `50` |
| `--sort-by views\|downloads` | Stat to rank by | `views` |
| `--max-workflows N` | Maximum workflows to check (`0` = all) | `200` |
| `--output FILE` | CSV file to save results to | `workflowhub_topworkflows.csv` |

Example — top 20 by downloads:

```bash
python3 workflowhub.py topworkflows --top 20 --sort-by downloads
```

---

### `types` — workflow count by type

Shows how many workflows exist for each type (Galaxy, Nextflow, Snakemake, CWL, etc.).

```bash
python3 workflowhub.py types
```

| Option | Description | Default |
|---|---|---|
| `--output FILE` | CSV file to save results to | `workflowhub_types.csv` |

---

### `orgs` — space/project leaderboard

Ranks all WorkflowHub spaces/projects by number of workflows.

```bash
python3 workflowhub.py orgs
```

| Option | Description | Default |
|---|---|---|
| `--top N` | How many spaces to display | `50` |
| `--output FILE` | CSV file to save results to | `workflowhub_orgs.csv` |

---

### `leaderboard` — contributor leaderboard

Ranks all WorkflowHub contributors by number of workflows.

```bash
python3 workflowhub.py leaderboard
```

| Option | Description | Default |
|---|---|---|
| `--top N` | How many top contributors to display | `50` |
| `--highlight NAME` | Highlight a contributor whose name contains this text (case-insensitive) | none |
| `--output FILE` | CSV file to save results to | `workflowhub_leaderboard.csv` |

Example — show top 100 and highlight a specific person:

```bash
python3 workflowhub.py leaderboard --top 100 --highlight "Smith"
```

---

## Help

Built-in help is available for all commands:

```bash
python3 workflowhub.py --help
python3 workflowhub.py galaxy --help
python3 workflowhub.py topworkflows --help
python3 workflowhub.py types --help
python3 workflowhub.py orgs --help
python3 workflowhub.py leaderboard --help
```

---

## License

MIT — see [LICENSE](LICENSE).
