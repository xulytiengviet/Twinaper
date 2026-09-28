# Twinaper – system architecture

## Honest scope (September 2026)
Twinaper is a **research workbench / literature-to-draft agent**, not a demonstrated autonomous discovery system. The 86 external ScientistTwo publications under \`data/scientisttwo-reference.json\` belong to ScientistTwo, not Twinaper. This repository does not copy the original PDFs or claim affiliation.

### Browser path (GitHub Pages only)
\`\`\`
Question + one of 8 GIS domains
  -> OpenAlex API (live search + metadata + DOI candidates)
  -> evidence JSON / local Markdown outline
  -> optional user-supplied OpenRouter key (in-memory only)
     -> Hypothesis Agent
     -> Methods Designer
     -> Skeptical Review Agent (AI simulation, NOT external peer review)
     -> Scientific Writer
  -> downloaded manuscript.md + audit.json
  -> human verification before sharing or publishing
\`\`\`

No backend credentials are baked into the site. Browser-to-OpenRouter calls depend on provider CORS support, model availability and user credits. The CLI offers an alternative when browser calls are unavailable.

### Command-line path (optionally measured experiments)
\`\`\`
python researcher.py --topic "How can spatial blocked validation improve flood prediction?" --domain geoai
\`\`\`
Reads \`OPENROUTER_API_KEY\` from the environment if present; otherwise generates real-literature evidence and an outline. Files in output directory:
- \`evidence.json\`: traceable OpenAlex metadata + abstracts, original IDs and DOI candidates.
- \`paper.md\`: always marked draft / not peer reviewed.
- \`audit.json\`: explicit flags for metadata, DOI checks, experiment status and human review.
- \`agent_log.json\`: agent roles, token usage reported by provider and flagged citations.

Add \`--experiment-csv data.csv --target flood_depth --features rainfall,elevation,slope --lat lat --lon lon\` for a **real** numerical regression baseline. \`experiments/spatial_benchmark.py\` tests DummyRegressor vs RandomForest with spatial group K-fold, stores sample sizes, errors, seed, package versions and input checksum. It only processes datasets supplied by the researcher.

Install experimental dependencies with:
\`\`\`bash
pip install -r requirements-experiments.txt
\`\`\`

Important: spatial grid cells in lat/lon degrees are not equal-area; the script warns about this. It has no built-in GIS dataset, makes no assertions about accuracy, and does not claim original scientific discovery.

## Research-integrity gates
1. Evidence: no unlisted OpenAlex IDs; DOI metadata origin preserved. External DOI resolution and full-text verification are **not** claimed.
2. Hypotheses: must be falsifiable; relevance and novelty checked by human experts.
3. Code: runs only on approved datasets with explicit local input and deterministic seed.
4. Spatial validation: no same-cell overlap; still inspect temporal leakage, spatial autocorrelation and site effects.
5. Papers: model citations/DOIs that do not belong to source allowlist cause the CLI AI stage to stop and retain only the safe outline.
6. Publication: no automated conference submission, no fake journal badges, no fabricated acceptance rates or benchmark claims.

## Technical stack
- Static responsive HTML + vanilla JavaScript + CSS, hosted from GitHub Pages; Leaflet + OpenStreetMap tiles for the illustrative geospatial map.
- OpenAlex public search API for current literature.
- OpenRouter's compatible chat completions endpoint, optionally supplied **per user**.
- Python 3.11+ standard-library CLI; optional \`numpy\`, \`pandas\` and \`scikit-learn\` for spatial experiments.
- JSON gallery of 86 externally hosted ScientistTwo reference PDFs spanning 8 *AI* domains, separate from 8 Twinaper *geospatial* research areas.
- Node integrity tests for count, origin and site resources.

## Publish website
The repository's \`index.html\` is at the root and the site uses relative paths for GitHub's /Twinaper/ subpath. In GitHub **Settings → Pages → Build and deployment**, choose **Deploy from a branch**, branch **main**, folder **/(root)**. GitHub controls the Pages publishing process; pushing the repository by itself does not prove a live Pages deployment.
