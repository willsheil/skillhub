# Bundle-Based Registry Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor the Claude Code Skill Registry from a three-layer architecture (Organization → Collection → Skill) to a two-layer architecture (Bundle → Skill), enabling users to install skill bundles via `/plugin install bundle-name`.

**Architecture:** Flatten the directory structure from `plugins/{org}/{collection}/{skill}/{version}.zip` to `plugins/{bundle}/{skill}/{version}.zip`. Update all API endpoints to use two parameters (bundle, skill) instead of three (org, collection, skill). Add search functionality and update the frontend UI to display bundles.

**Tech Stack:** Python 3.x, FastAPI, Jinja2 templates, JavaScript (vanilla)

---

## Task 1: Modify `scan_plugins()` - Change from three-layer to two-layer scanning

**Files:**
- Modify: `main.py:69-114` (the `scan_plugins()` function)

**Step 1: Write the failing test**

Create `tests/test_main.py`:

```python
import json
import tempfile
import zipfile
from pathlib import Path
from main import scan_plugins, PLUGINS_DIR

def test_scan_plugins_two_layer_structure():
    """Test that scan_plugins correctly scans two-layer bundle/skill structure."""
    # Create test directory structure
    with tempfile.TemporaryDirectory() as tmpdir:
        test_plugins_dir = Path(tmpdir)

        # Create bundle/skill/version structure
        bundle_dir = test_plugins_dir / "security-tools"
        skill_dir = bundle_dir / "semgrep-creator"
        skill_dir.mkdir(parents=True)

        # Create a test ZIP file with plugin.json
        zip_path = skill_dir / "1.0.0.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            plugin_json = json.dumps({
                "name": "semgrep-creator",
                "version": "1.0.0",
                "description": "Create Semgrep rules"
            })
            zf.writestr(".claude-plugin/plugin.json", plugin_json)

        # Temporarily override PLUGINS_DIR
        original_dir = PLUGINS_DIR
        import main
        main.PLUGINS_DIR = test_plugins_dir

        try:
            plugins = scan_plugins()

            # Should return list with bundle field
            assert len(plugins) == 1
            assert plugins[0]["bundle"] == "security-tools"
            assert plugins[0]["name"] == "semgrep-creator"
            assert "organization" not in plugins[0]
            assert "collection" not in plugins[0]
        finally:
            main.PLUGINS_DIR = original_dir
```

Run: `pytest tests/test_main.py::test_scan_plugins_two_layer_structure -v`

Expected: FAIL (current code still uses three-layer structure with organization/collection)

**Step 2: Implement the two-layer scan logic**

Replace the `scan_plugins()` function in `main.py:69-114` with:

```python
def scan_plugins() -> List[dict]:
    """Scan plugins directory and return metadata list (two-layer: bundle/skill)."""
    plugins = []

    for bundle_dir in PLUGINS_DIR.iterdir():
        if not bundle_dir.is_dir():
            continue
        bundle = bundle_dir.name

        for plugin_dir in bundle_dir.iterdir():
            if not plugin_dir.is_dir():
                continue

            # Find all versions (zip files)
            versions = []
            for zip_file in sorted(plugin_dir.glob("*.zip")):
                version = zip_file.stem  # e.g., "1.0.0" from "1.0.0.zip"
                versions.append({
                    "version": version,
                    "filename": zip_file.name,
                    "size": zip_file.stat().st_size,
                    "updated_at": datetime.fromtimestamp(zip_file.stat().st_mtime).isoformat()
                })

            if not versions:
                continue

            # Get latest version metadata
            latest_zip = plugin_dir / versions[-1]["filename"]
            metadata = extract_metadata(bundle, plugin_dir.name, latest_zip)

            plugins.append({
                "name": plugin_dir.name,
                "bundle": bundle,
                "metadata": metadata,
                "versions": versions,
                "latest_version": versions[-1]["version"]
            })

    return sorted(plugins, key=lambda x: (x["bundle"], x["name"]))
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_scan_plugins_two_layer_structure -v`

Expected: PASS

**Step 4: Commit**

```bash
git add tests/test_main.py main.py
git commit -m "refactor: change scan_plugins from three-layer to two-layer structure

- Change directory scanning from plugins/{org}/{collection}/{skill}/ to plugins/{bundle}/{skill}/
- Remove organization and collection fields from plugin metadata
- Add bundle field to track skill bundle membership

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 2: Modify `extract_metadata()` - Remove organization/collection parameters

**Files:**
- Modify: `main.py:117-142` (the `extract_metadata()` function)

**Step 1: Update the function signature and implementation**

Replace the `extract_metadata()` function in `main.py:117-142` with:

```python
def extract_metadata(bundle: str, plugin_name: str, zip_path: Path) -> Optional[dict]:
    """Extract metadata from plugin.json inside zip."""
    import zipfile

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Try to find plugin.json
            for name in zf.namelist():
                if name.endswith('.claude-plugin/plugin.json'):
                    content = zf.read(name)
                    metadata = json.loads(content)
                    metadata["bundle"] = bundle
                    return metadata
    except Exception:
        pass

    # Fallback: return basic info
    return {
        "name": plugin_name,
        "bundle": bundle,
        "version": "unknown",
        "description": "No description available",
        "author": {"name": "Unknown"}
    }
```

**Step 2: Run tests to ensure nothing broke**

Run: `pytest tests/test_main.py -v`

Expected: PASS

**Step 3: Commit**

```bash
git add main.py
git commit -m "refactor: update extract_metadata to use bundle instead of org/collection

- Remove organization and collection parameters
- Add bundle parameter and metadata field
- Update fallback metadata structure

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 3: Modify `marketplace_json()` - Update JSON format

**Files:**
- Modify: `main.py:157-192` (the `marketplace_json()` endpoint)

**Step 1: Update the marketplace.json generation**

Replace the `marketplace_json()` function in `main.py:157-192` with:

```python
@app.get("/marketplace.json")
async def marketplace_json():
    """Claude Code marketplace index."""
    plugins = scan_plugins()

    marketplace = {
        "name": "private-registry",
        "owner": {
            "name": "Internal Registry",
            "email": "admin@company.local"
        },
        "metadata": {
            "version": "1.0.0",
            "description": "Internal Claude Code Skill Registry",
            "updated_at": datetime.now().isoformat()
        },
        "plugins": []
    }

    base_url = "/plugins"  # Relative URL

    for plugin in plugins:
        meta = plugin["metadata"]
        latest = plugin["versions"][-1]

        marketplace["plugins"].append({
            "name": meta.get("name", plugin["name"]),
            "bundle": plugin["bundle"],
            "version": latest["version"],
            "description": meta.get("description", "No description"),
            "author": meta.get("author", {"name": "Unknown"}),
            "source": f"{base_url}/{plugin['bundle']}/{plugin['name']}/{latest['filename']}"
        })

    return marketplace
```

**Step 2: Test the endpoint manually**

Run: `python main.py` (in background)

Run: `curl http://localhost:28000/marketplace.json | jq`

Expected: JSON with `bundle` field instead of `organization`/`collection`, and `source` URLs with two parameters

**Step 3: Stop the server and commit**

```bash
git add main.py
git commit -m "refactor: update marketplace.json to use bundle structure

- Replace organization/collection fields with bundle field
- Update source URLs to use two-parameter format: /plugins/{bundle}/{skill}/{version}.zip
- Remove deprecated three-layer path structure

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 4: Modify `download_plugin()` - Change from three to two parameters

**Files:**
- Modify: `main.py:195-207` (the `download_plugin()` endpoint)

**Step 1: Update the download endpoint**

Replace the `download_plugin()` function in `main.py:195-207` with:

```python
@app.get("/plugins/{bundle}/{plugin_name}/{filename}")
async def download_plugin(bundle: str, plugin_name: str, filename: str):
    """Download plugin ZIP file."""
    file_path = PLUGINS_DIR / bundle / plugin_name / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Plugin not found")

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/zip"
    )
```

**Step 2: Test the download endpoint**

Run: `python main.py` (in background)

Create a test plugin and try downloading:
```bash
curl -I http://localhost:28000/plugins/security-tools/test-skill/1.0.0.zip
```

Expected: HTTP 200 if file exists, 404 if not

**Step 3: Stop the server and commit**

```bash
git add main.py
git commit -m "refactor: update download_plugin endpoint to use bundle structure

- Change path parameters from {organization}/{collection}/{plugin_name} to {bundle}/{plugin_name}
- Update file path construction to use two-layer directory structure
- Maintain same error handling and response format

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 5: Delete old API endpoints

**Files:**
- Modify: `main.py` (remove endpoints at lines 210-500)

**Step 1: Remove deprecated endpoints**

Delete the following endpoints from `main.py`:
- `/api/skills` (lines 210-213)
- `/api/collections` (lines 459-480)
- `/api/collections/{organization}/{collection}` (lines 483-500)

**Step 2: Verify the app still starts**

Run: `python main.py`

Expected: Server starts without errors on port 28000

**Step 3: Commit**

```bash
git add main.py
git commit -m "refactor: remove deprecated three-layer API endpoints

- Remove /api/skills endpoint (no longer needed with bundle structure)
- Remove /api/collections endpoint (replaced by /api/bundles)
- Remove /api/collections/{org}/{collection} endpoint (replaced by /api/bundles/{bundle})

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 6: Add `/api/bundles` endpoint - List all bundles

**Files:**
- Modify: `main.py` (add new endpoint after line 210)

**Step 1: Write the failing test**

Add to `tests/test_main.py`:

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_api_bundles():
    """Test /api/bundles endpoint returns grouped bundles."""
    response = client.get("/api/bundles")
    assert response.status_code == 200

    data = response.json()
    assert "bundles" in data
    assert isinstance(data["bundles"], list)

    # Each bundle should have name, skills list, and skill_count
    if len(data["bundles"]) > 0:
        bundle = data["bundles"][0]
        assert "name" in bundle
        assert "skills" in bundle
        assert "skill_count" in bundle
```

Run: `pytest tests/test_main.py::test_api_bundles -v`

Expected: FAIL with 404 (endpoint doesn't exist yet)

**Step 2: Implement the endpoint**

Add this function to `main.py` after the deleted endpoints (around line 215):

```python
@app.get("/api/bundles")
async def list_bundles():
    """List all skill bundles."""
    plugins = scan_plugins()

    # Group plugins by bundle
    bundles_dict = {}
    for plugin in plugins:
        bundle_name = plugin["bundle"]
        if bundle_name not in bundles_dict:
            bundles_dict[bundle_name] = []
        bundles_dict[bundle_name].append(plugin)

    # Convert to list format
    bundles = []
    for bundle_name, skills in bundles_dict.items():
        bundles.append({
            "name": bundle_name,
            "skills": skills,
            "skill_count": len(skills)
        })

    return {"bundles": sorted(bundles, key=lambda x: x["name"])}
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_api_bundles -v`

Expected: PASS

**Step 4: Commit**

```bash
git add tests/test_main.py main.py
git commit -m "feat: add /api/bundles endpoint to list all skill bundles

- Group skills by bundle name
- Return bundle name, skills list, and skill count
- Sort bundles alphabetically by name

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 7: Add `/api/bundles/{bundle}` endpoint - Get bundle details

**Files:**
- Modify: `main.py` (add new endpoint)

**Step 1: Write the failing test**

Add to `tests/test_main.py`:

```python
def test_api_bundles_detail():
    """Test /api/bundles/{bundle} endpoint returns bundle details."""
    # First, create a test bundle
    with tempfile.TemporaryDirectory() as tmpdir:
        test_plugins_dir = Path(tmpdir)
        bundle_dir = test_plugins_dir / "test-bundle"
        skill_dir = bundle_dir / "test-skill"
        skill_dir.mkdir(parents=True)

        zip_path = skill_dir / "1.0.0.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            plugin_json = json.dumps({
                "name": "test-skill",
                "version": "1.0.0",
                "description": "Test skill"
            })
            zf.writestr(".claude-plugin/plugin.json", plugin_json)

        import main
        original_dir = main.PLUGINS_DIR
        main.PLUGINS_DIR = test_plugins_dir

        try:
            response = client.get("/api/bundles/test-bundle")
            assert response.status_code == 200

            data = response.json()
            assert data["name"] == "test-bundle"
            assert "skills" in data
            assert data["skill_count"] == 1
        finally:
            main.PLUGINS_DIR = original_dir
```

Run: `pytest tests/test_main.py::test_api_bundles_detail -v`

Expected: FAIL with 404

**Step 2: Implement the endpoint**

Add this function to `main.py` after `/api/bundles`:

```python
@app.get("/api/bundles/{bundle}")
async def get_bundle_skills(bundle: str):
    """Get all skills in a specific bundle."""
    plugins = scan_plugins()
    bundle_skills = [
        p for p in plugins
        if p["bundle"] == bundle
    ]

    if not bundle_skills:
        raise HTTPException(status_code=404, detail="Bundle not found")

    return {
        "name": bundle,
        "skills": bundle_skills,
        "skill_count": len(bundle_skills)
    }
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_api_bundles_detail -v`

Expected: PASS

**Step 4: Commit**

```bash
git add tests/test_main.py main.py
git commit -m "feat: add /api/bundles/{bundle} endpoint to get bundle details

- Return bundle name, skills list, and skill count
- Return 404 if bundle doesn't exist
- Filters scanned plugins by bundle name

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 8: Add `/api/search` endpoint - Search bundles and skills

**Files:**
- Modify: `main.py` (add new endpoint)

**Step 1: Write the failing test**

Add to `tests/test_main.py`:

```python
def test_api_search():
    """Test /api/search endpoint with query parameter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_plugins_dir = Path(tmpdir)

        # Create security-tools bundle with semgrep skill
        security_dir = test_plugins_dir / "security-tools"
        semgrep_dir = security_dir / "semgrep-creator"
        semgrep_dir.mkdir(parents=True)

        zip_path = semgrep_dir / "1.0.0.zip"
        with zipfile.ZipFile(zip_path, 'w') as zf:
            plugin_json = json.dumps({
                "name": "semgrep-creator",
                "version": "1.0.0",
                "description": "Create security-focused Semgrep rules"
            })
            zf.writestr(".claude-plugin/plugin.json", plugin_json)

        import main
        original_dir = main.PLUGINS_DIR
        main.PLUGINS_DIR = test_plugins_dir

        try:
            # Search for "security" should match bundle name
            response = client.get("/api/search?q=security")
            assert response.status_code == 200

            data = response.json()
            assert "bundles" in data
            assert "query" in data
            assert data["query"] == "security"
            assert len(data["bundles"]) > 0
            assert data["bundles"][0]["name"] == "security-tools"
        finally:
            main.PLUGINS_DIR = original_dir
```

Run: `pytest tests/test_main.py::test_api_search -v`

Expected: FAIL with 404

**Step 2: Implement the endpoint**

Add this function to `main.py` after `/api/bundles/{bundle}`:

```python
@app.get("/api/search")
async def search_skills(q: str = ""):
    """Search bundles and skills by name/description."""
    if not q:
        return {"bundles": [], "query": ""}

    plugins = scan_plugins()
    query = q.lower()

    bundles = {}  # {bundle_name: {skills: [], match_score: int}}

    for plugin in plugins:
        bundle = plugin["bundle"]
        skill_name = plugin["name"].lower()
        description = plugin.get("metadata", {}).get("description", "").lower()

        # Calculate match score
        score = 0
        if query in bundle.lower():
            score += 10  # Bundle name match has highest weight
        if query in skill_name:
            score += 5
        if query in description:
            score += 2

        if score > 0:
            if bundle not in bundles:
                bundles[bundle] = {"skills": [], "match_score": 0}
            bundles[bundle]["skills"].append(plugin)
            bundles[bundle]["match_score"] = max(bundles[bundle]["match_score"], score)

    # Sort by match score
    sorted_bundles = sorted(
        [{"name": k, "skills": v["skills"], "skill_count": len(v["skills"])}
         for k, v in bundles.items()],
        key=lambda x: x["match_score"],
        reverse=True
    )

    # Remove match_score from response (internal field)
    for bundle in sorted_bundles:
        del bundle["match_score"]

    return {"bundles": sorted_bundles, "query": q}
```

**Step 3: Run test to verify it passes**

Run: `pytest tests/test_main.py::test_api_search -v`

Expected: PASS

**Step 4: Commit**

```bash
git add tests/test_main.py main.py
git commit -m "feat: add /api/search endpoint for searching bundles and skills

- Search by bundle name (weight: 10), skill name (weight: 5), description (weight: 2)
- Return bundles sorted by match score
- Return empty results if no query provided

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 9: Modify `/admin/upload` endpoint - Change to bundle parameter

**Files:**
- Modify: `main.py:251-344` (the `process_skill_collection()` function)
- Modify: `main.py:346-423` (the `/admin/upload` endpoint)

**Step 1: Update `process_skill_collection()` function**

Replace the `process_skill_collection()` function in `main.py:251-344` with:

```python
def process_skill_collection(
    zip_path: Path,
    output_dir: Path,
    bundle: str
) -> List[dict]:
    """Process a skill collection ZIP and extract individual skills.

    Args:
        zip_path: Path to the uploaded ZIP file
        output_dir: Base output directory (PLUGINS_DIR)
        bundle: Bundle name

    Returns:
        List of processed skills with name and version
    """
    import zipfile
    import tempfile

    processed_skills = []
    temp_dir = tempfile.mkdtemp()

    try:
        # Extract ZIP to temp directory
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(temp_dir)

        # Look for skills in common locations
        skills_base_paths = [
            Path(temp_dir) / "skills" / "plugins",
            Path(temp_dir) / "plugins",
            Path(temp_dir),
        ]

        skills_found = False
        for skills_path in skills_base_paths:
            if not skills_path.exists():
                continue

            # Iterate through potential skill directories
            for item in skills_path.iterdir():
                if not item.is_dir():
                    continue

                # Check if this is a skill directory (has .claude-plugin/plugin.json)
                plugin_json = item / ".claude-plugin" / "plugin.json"
                if not plugin_json.exists():
                    # Try alternative location
                    plugin_json = item / "plugin.json"

                if plugin_json.exists():
                    try:
                        # Read skill metadata
                        with open(plugin_json, 'r', encoding='utf-8') as f:
                            metadata = json.load(f)

                        skill_name = metadata.get("name", item.name)
                        skill_version = metadata.get("version", "1.0.0")

                        # Create target directory
                        skill_dir = output_dir / bundle / skill_name
                        skill_dir.mkdir(parents=True, exist_ok=True)

                        # Create ZIP for this skill
                        target_zip = skill_dir / f"{skill_version}.zip"

                        with zipfile.ZipFile(target_zip, 'w', zipfile.ZIP_DEFLATED) as zf_out:
                            for file_path in item.rglob("*"):
                                if file_path.is_file():
                                    arcname = str(file_path.relative_to(item))
                                    zf_out.write(file_path, arcname)

                        processed_skills.append({
                            "name": skill_name,
                            "version": skill_version,
                            "path": str(target_zip)
                        })
                        skills_found = True

                    except Exception as e:
                        print(f"Error processing skill {item.name}: {e}")
                        continue

        # If no skills found in collection structure, treat as single skill
        if not skills_found:
            return []

        return processed_skills

    finally:
        # Cleanup temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)
```

**Step 2: Update `/admin/upload` endpoint**

Replace the `/admin/upload` endpoint in `main.py:346-423` with:

```python
@app.post("/admin/upload")
async def upload_plugin(
    request: Request,
    name: str = Form(""),
    version: str = Form(""),
    bundle: str = Form("default"),
    file: UploadFile = File(...),
    _: bool = Depends(require_auth)
):
    """Upload a new plugin or skill collection (requires auth)."""
    import zipfile
    import tempfile

    # Validate file extension
    if not file.filename.endswith('.zip'):
        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": None,
            "error": "Only ZIP files allowed"
        })

    # Save uploaded file to temp location
    temp_dir = tempfile.mkdtemp()
    temp_zip = Path(temp_dir) / "upload.zip"

    try:
        with open(temp_zip, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Try to process as skill collection first
        processed_skills = process_skill_collection(
            temp_zip, PLUGINS_DIR, bundle
        )

        if processed_skills:
            # Successfully processed as skill collection
            skill_names = ", ".join([s["name"] for s in processed_skills])
            return templates.TemplateResponse("admin_upload.html", {
                "request": request,
                "success": f"Successfully uploaded {len(processed_skills)} skills: {skill_names}",
                "error": None
            })

        # Treat as single skill upload
        if not name or not version:
            return templates.TemplateResponse("admin_upload.html", {
                "request": request,
                "success": None,
                "error": "For single skill upload, name and version are required"
            })

        # Create plugin directory
        plugin_dir = PLUGINS_DIR / bundle / name
        plugin_dir.mkdir(parents=True, exist_ok=True)

        # Save file
        target_path = plugin_dir / f"{version}.zip"

        shutil.copy(temp_zip, target_path)

        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": f"Successfully uploaded {bundle}/{name}@{version}",
            "error": None
        })

    except Exception as e:
        return templates.TemplateResponse("admin_upload.html", {
            "request": request,
            "success": None,
            "error": f"Upload failed: {str(e)}"
        })

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
```

**Step 3: Commit**

```bash
git add main.py
git commit -m "refactor: update /admin/upload to use bundle parameter

- Change process_skill_collection() to use bundle instead of organization/collection
- Update /admin/upload endpoint form parameters: organization/collection -> bundle
- Update success/error messages to show bundle path format
- Maintain backward compatibility with 'default' bundle name

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 10: Modify `delete_plugin()` - Change to three parameters

**Files:**
- Modify: `main.py:425-456` (the `delete_plugin()` endpoint)

**Step 1: Update the delete endpoint**

Replace the `delete_plugin()` function in `main.py:425-456` with:

```python
@app.delete("/admin/plugins/{bundle}/{plugin_name}/{version}")
async def delete_plugin(
    bundle: str,
    plugin_name: str,
    version: str,
    _: bool = Depends(require_auth)
):
    """Delete a plugin version (requires auth)."""
    file_path = PLUGINS_DIR / bundle / plugin_name / f"{version}.zip"

    if not file_path.exists():
        raise HTTPException(404, "Plugin version not found")

    file_path.unlink()

    # Remove empty plugin directory
    plugin_dir = PLUGINS_DIR / bundle / plugin_name
    if plugin_dir.exists() and not any(plugin_dir.iterdir()):
        plugin_dir.rmdir()

    # Remove empty bundle directory
    bundle_dir = PLUGINS_DIR / bundle
    if bundle_dir.exists() and not any(bundle_dir.iterdir()):
        bundle_dir.rmdir()

    return {"success": True, "message": f"Deleted {bundle}/{plugin_name}@{version}"}
```

**Step 2: Commit**

```bash
git add main.py
git commit -m "refactor: update delete_plugin endpoint to use bundle structure

- Change path parameters from {organization}/{collection}/{plugin_name} to {bundle}/{plugin_name}
- Update directory cleanup logic to handle two-layer structure
- Update success message to show bundle path format

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 11: Update `templates/admin_upload.html` - Change form fields

**Files:**
- Modify: `templates/admin_upload.html:135-144` (form fields)

**Step 1: Replace organization/collection fields with bundle field**

In `templates/admin_upload.html`, replace lines 135-144:

```html
<div class="form-row">
    <div class="form-group">
        <label for="organization">Organization *</label>
        <input type="text" id="organization" name="organization" value="default" required>
    </div>
    <div class="form-group">
        <label for="collection">Collection *</label>
        <input type="text" id="collection" name="collection" value="default" required>
    </div>
</div>
```

With:

```html
<div class="form-group">
    <label for="bundle">Bundle Name *</label>
    <input type="text" id="bundle" name="bundle" value="default" required>
    <small style="color: #999; font-size: 12px; margin-top: 4px; display: block;">
        例如: security-tools, productivity-boosters
    </small>
</div>
```

**Step 2: Update the info section**

Update the info text (around line 127-132) to:

```html
<div class="info">
    <strong>上传类型：</strong>
    <ul style="margin: 10px 0 0 20px;">
        <li><strong>Skill Bundle</strong>：包含多个技能的 ZIP 文件（系统会自动提取其中的每个技能）</li>
        <li><strong>单个 Skill</strong>：单个技能的 ZIP 文件（需要填写名称和版本）</li>
    </ul>
</div>
```

**Step 3: Commit**

```bash
git add templates/admin_upload.html
git commit -m "refactor: update admin upload form to use bundle field

- Replace organization/collection input fields with single bundle field
- Add helpful placeholder examples for bundle names
- Update info section text to reference bundles instead of collections

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 12: Create new `templates/index.html` - Add search and bundle layout

**Files:**
- Modify: `templates/index.html` (complete rewrite)

**Step 1: Create the new index.html with search and bundle layout**

Replace the entire `templates/index.html` file with:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ registry_name }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }

        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            margin-bottom: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }

        header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }

        header p {
            opacity: 0.9;
            font-size: 1.1em;
        }

        .stats {
            display: flex;
            gap: 20px;
            margin-top: 20px;
        }

        .stat-card {
            background: rgba(255,255,255,0.2);
            padding: 15px 25px;
            border-radius: 8px;
        }

        .stat-card .number {
            font-size: 2em;
            font-weight: bold;
        }

        .stat-card .label {
            font-size: 0.9em;
            opacity: 0.8;
        }

        .usage-info {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            border-left: 4px solid #667eea;
        }

        .usage-info h3 {
            margin-bottom: 10px;
            color: #667eea;
        }

        .usage-info code {
            background: #f4f4f4;
            padding: 12px 16px;
            border-radius: 4px;
            display: block;
            font-family: 'Consolas', 'Monaco', monospace;
            margin: 10px 0;
            color: #333;
        }

        /* Search section */
        .search-section {
            background: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .search-input {
            width: 100%;
            padding: 12px 16px;
            font-size: 16px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            outline: none;
            transition: border-color 0.3s;
        }

        .search-input:focus {
            border-color: #667eea;
        }

        /* Bundle card styles */
        .bundle-section {
            margin-bottom: 30px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .bundle-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 2px solid #e0e0e0;
        }

        .bundle-title {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .bundle-icon {
            font-size: 24px;
        }

        .bundle-name {
            font-size: 1.5em;
            font-weight: 600;
            color: #333;
        }

        .bundle-actions {
            display: flex;
            gap: 10px;
            align-items: center;
        }

        .skill-count {
            color: #666;
            font-size: 14px;
        }

        .install-bundle-btn {
            background: #667eea;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: background 0.2s;
        }

        .install-bundle-btn:hover {
            background: #5a6fd6;
        }

        .skills-table-container {
            overflow-x: auto;
        }

        .skills-table {
            width: 100%;
            border-collapse: collapse;
        }

        .skills-table thead {
            background: #f8f9fa;
        }

        .skills-table th {
            padding: 14px 20px;
            text-align: left;
            font-weight: 600;
            color: #555;
            border-bottom: 1px solid #e0e0e0;
        }

        .skills-table td {
            padding: 14px 20px;
            border-bottom: 1px solid #eee;
        }

        .skills-table tbody tr:hover {
            background: #f8f9fa;
        }

        .skill-name {
            font-weight: 600;
            color: #333;
        }

        .skill-version {
            background: #667eea;
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 500;
        }

        .skill-description {
            color: #666;
            max-width: 400px;
        }

        .skill-author {
            color: #666;
        }

        .install-btn {
            background: #4caf50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 500;
            transition: background 0.2s;
        }

        .install-btn:hover {
            background: #45a049;
        }

        .no-bundles {
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }

        footer {
            text-align: center;
            padding: 40px 20px;
            color: #999;
            margin-top: 40px;
        }

        @media (max-width: 768px) {
            header h1 {
                font-size: 1.8em;
            }

            .stats {
                flex-direction: column;
            }

            .bundle-header {
                flex-direction: column;
                gap: 10px;
                align-items: flex-start;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{{ registry_name }}</h1>
            <p>内部 Claude Code Skill Registry - 管理和发现团队技能插件</p>
            <div class="stats">
                <div class="stat-card">
                    <div class="number">{{ plugin_count }}</div>
                    <div class="label">可用技能</div>
                </div>
                <div class="stat-card">
                    <div class="number">{{ bundles_count | default(plugins | map(attribute='bundle') | unique | list | length) }}</div>
                    <div class="label">技能包</div>
                </div>
            </div>
        </header>

        <div class="usage-info">
            <h3>使用方法</h3>
            <p>在 Claude Code 中添加此 Registry：</p>
            <code>/plugins marketplace add {{ request.base_url }}marketplace.json</code>
            <p>安装技能：</p>
            <code>/plugin install &lt;bundle-name&gt;/&lt;skill-name&gt;</code>
            <p>或安装整个技能包：</p>
            <code>/plugin install &lt;bundle-name&gt;</code>
        </div>

        <!-- Search Section -->
        <div class="search-section">
            <input type="text"
                   id="searchInput"
                   class="search-input"
                   placeholder="搜索技能包或技能..."
                   oninput="handleSearch(this.value)">
        </div>

        <!-- Bundles -->
        {% if not plugins %}
        <div class="no-bundles">
            <h2>暂无技能插件</h2>
            <p>请使用 <a href="/admin/upload">上传页面</a> 添加技能插件</p>
        </div>
        {% else %}
        {% for bundle in bundles %}
        <div class="bundle-section" data-bundle="{{ bundle.name }}">
            <div class="bundle-header">
                <div class="bundle-title">
                    <span class="bundle-icon">📦</span>
                    <span class="bundle-name">{{ bundle.name }}</span>
                </div>
                <div class="bundle-actions">
                    <span class="skill-count">{{ bundle.skill_count }} 个技能</span>
                    <button class="install-bundle-btn"
                            onclick="installBundle('{{ bundle.name }}')">
                        安装整个 Bundle
                    </button>
                </div>
            </div>
            <div class="skills-table-container">
                <table class="skills-table">
                    <thead>
                        <tr>
                            <th>技能名称</th>
                            <th>版本</th>
                            <th>描述</th>
                            <th>作者</th>
                            <th>操作</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for skill in bundle.skills %}
                        <tr>
                            <td class="skill-name">{{ skill.metadata.name or skill.name }}</td>
                            <td><span class="skill-version">v{{ skill.latest_version }}</span></td>
                            <td class="skill-description">{{ skill.metadata.description or "暂无描述" }}</td>
                            <td class="skill-author">{{ skill.metadata.author.name or "未知" }}</td>
                            <td>
                                <button class="install-btn"
                                        onclick="installSkill('{{ bundle.name }}', '{{ skill.name }}')">
                                    安装
                                </button>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        {% endfor %}
        {% endif %}

        <footer>
            <p>Private Claude Code Skill Registry | Built with FastAPI</p>
        </footer>
    </div>

    <script>
        const allBundles = {{ bundles | tojson | safe }};

        function installBundle(bundleName) {
            const command = `/plugin install ${bundleName}`;
            copyToClipboard(command);
        }

        function installSkill(bundleName, skillName) {
            const command = `/plugin install ${bundleName}/${skillName}`;
            copyToClipboard(command);
        }

        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(() => {
                alert(`安装命令已复制到剪贴板：\n${text}`);
            }).catch(err => {
                console.error('复制失败:', err);
                alert(`请手动复制安装命令：\n${text}`);
            });
        }

        let searchTimeout;
        function handleSearch(query) {
            clearTimeout(searchTimeout);

            if (!query.trim()) {
                // Show all bundles
                document.querySelectorAll('.bundle-section').forEach(section => {
                    section.style.display = 'block';
                });
                return;
            }

            searchTimeout = setTimeout(() => {
                performSearch(query);
            }, 300);
        }

        async function performSearch(query) {
            try {
                const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
                const data = await response.json();

                // Hide all bundles first
                document.querySelectorAll('.bundle-section').forEach(section => {
                    section.style.display = 'none';
                });

                // Show only matching bundles
                data.bundles.forEach(bundle => {
                    const section = document.querySelector(`[data-bundle="${bundle.name}"]`);
                    if (section) {
                        section.style.display = 'block';
                    }
                });
            } catch (error) {
                console.error('搜索失败:', error);
            }
        }
    </script>
</body>
</html>
```

**Step 2: Update the index endpoint to pass bundles**

Update the `index()` function in `main.py:145-154`:

```python
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Web UI - Display all skills."""
    plugins = scan_plugins()

    # Group by bundle
    bundles_dict = {}
    for plugin in plugins:
        bundle_name = plugin["bundle"]
        if bundle_name not in bundles_dict:
            bundles_dict[bundle_name] = []
        bundles_dict[bundle_name].append(plugin)

    bundles = [
        {"name": name, "skills": skills, "skill_count": len(skills)}
        for name, skills in bundles_dict.items()
    ]
    bundles = sorted(bundles, key=lambda x: x["name"])

    return templates.TemplateResponse("index.html", {
        "request": request,
        "plugins": plugins,
        "bundles": bundles,
        "registry_name": "Private Skill Registry",
        "plugin_count": len(plugins),
        "bundles_count": len(bundles)
    })
```

**Step 3: Test the new UI**

Run: `python main.py`

Visit: `http://localhost:28000`

Expected:
- Search box at top
- Bundles displayed with skill count
- "安装整个 Bundle" button copies `/plugin install bundle-name`
- Individual skill install buttons copy `/plugin install bundle-name/skill-name`
- Search functionality works

**Step 4: Commit**

```bash
git add templates/index.html main.py
git commit -m "feat: implement new bundle-based UI with search functionality

- Add search box for filtering bundles and skills
- Display bundles as cards with skill lists
- Add 'Install Bundle' button for one-command installation
- Update install command format to /plugin install {bundle}/{skill}
- Implement real-time search using /api/search endpoint
- Update index endpoint to group plugins by bundle

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 13: Create validation script for marketplace.json compatibility

**Files:**
- Create: `scripts/validate_marketplace.py`

**Step 1: Create the validation script**

Create `scripts/validate_marketplace.py`:

```python
#!/usr/bin/env python3
"""
Validate marketplace.json format for Claude Code compatibility.

This script generates a test marketplace.json with the new bundle format
and provides instructions for testing with Claude Code.
"""

import json
from pathlib import Path
from datetime import datetime

def generate_test_marketplace():
    """Generate a test marketplace.json with bundle format."""
    test_marketplace = {
        "name": "test-registry",
        "owner": {
            "name": "Test Registry",
            "email": "test@example.com"
        },
        "metadata": {
            "version": "1.0.0",
            "description": "Test marketplace for bundle format validation",
            "updated_at": datetime.now().isoformat()
        },
        "plugins": [
            {
                "name": "test-skill-one",
                "bundle": "test-bundle",
                "version": "1.0.0",
                "description": "First test skill",
                "author": {"name": "Test Author"},
                "source": "/plugins/test-bundle/test-skill-one/1.0.0.zip"
            },
            {
                "name": "test-skill-two",
                "bundle": "test-bundle",
                "version": "1.0.0",
                "description": "Second test skill",
                "author": {"name": "Test Author"},
                "source": "/plugins/test-bundle/test-skill-two/1.0.0.zip"
            }
        ]
    }

    return test_marketplace

def main():
    """Generate test marketplace and print validation instructions."""
    marketplace = generate_test_marketplace()

    # Save test marketplace
    test_file = Path("test-marketplace.json")
    test_file.write_text(json.dumps(marketplace, indent=2))

    print("=" * 60)
    print("✅ Test marketplace.json generated")
    print("=" * 60)
    print()
    print("📋 Next steps to validate compatibility:")
    print()
    print("1. Start the registry server:")
    print("   python main.py")
    print()
    print("2. In Claude Code, add the test registry:")
    print("   /plugins marketplace add http://localhost:28000/test-marketplace.json")
    print()
    print("3. List available skills:")
    print("   /plugin menu")
    print("   Expected: Should show test-skill-one and test-skill-two")
    print()
    print("4. Install a single skill:")
    print("   /plugin install test-bundle/test-skill-one")
    print("   Expected: Should install successfully")
    print()
    print("5. Install entire bundle:")
    print("   /plugin install test-bundle")
    print("   Expected: Should install all skills in bundle (if supported)")
    print()
    print("6. Test with the actual marketplace.json:")
    print("   /plugins marketplace add http://localhost:28000/marketplace.json")
    print()
    print("=" * 60)
    print("📝 Validation Checklist:")
    print("=" * 60)
    print("[ ] Claude Code recognizes the marketplace.json")
    print("[ ] /plugin menu displays skills correctly")
    print("[ ] /plugin install {bundle}/{skill} works")
    print("[ ] /plugin install {bundle} works (if supported by CLI)")
    print()
    print("If all tests pass, the bundle format is compatible!")
    print("If any fail, we may need to keep organization/collection fields.")
    print()

if __name__ == "__main__":
    main()
```

**Step 2: Make script executable and test it**

Run:
```bash
chmod +x scripts/validate_marketplace.py
python scripts/validate_marketplace.py
```

Expected: Script generates `test-marketplace.json` and prints validation instructions

**Step 3: Serve test marketplace via main.py**

Add this endpoint to `main.py` (before the return statement in main):

```python
@app.get("/test-marketplace.json")
async def test_marketplace_json():
    """Test marketplace for validation."""
    return {
        "name": "test-registry",
        "owner": {
            "name": "Test Registry",
            "email": "test@example.com"
        },
        "metadata": {
            "version": "1.0.0",
            "description": "Test marketplace for bundle format validation",
            "updated_at": datetime.now().isoformat()
        },
        "plugins": [
            {
                "name": "test-skill-one",
                "bundle": "test-bundle",
                "version": "1.0.0",
                "description": "First test skill",
                "author": {"name": "Test Author"},
                "source": "/plugins/test-bundle/test-skill-one/1.0.0.zip"
            },
            {
                "name": "test-skill-two",
                "bundle": "test-bundle",
                "version": "1.0.0",
                "description": "Second test skill",
                "author": {"name": "Test Author"},
                "source": "/plugins/test-bundle/test-skill-two/1.0.0.zip"
            }
        ]
    }
```

**Step 4: Commit**

```bash
git add scripts/validate_marketplace.py main.py
git commit -m "feat: add marketplace.json validation script and test endpoint

- Create scripts/validate_marketplace.py for compatibility testing
- Add /test-marketplace.json endpoint for easy validation
- Provide step-by-step instructions for testing with Claude Code
- Include checklist for validating bundle format compatibility

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 14: Update README.md documentation

**Files:**
- Modify: `README.md`

**Step 1: Update directory structure section**

Replace the directory structure section (around line 105) with:

```
registry/
├── main.py                 # FastAPI 应用
├── requirements.txt        # Python 依赖
├── Dockerfile             # Docker 构建
├── docker-compose.yml     # Docker Compose 配置
├── templates/
│   └── index.html         # 前端页面
├── static/                # 静态文件
└── plugins/               # 插件存储目录
    ├── security-tools/       # Skill Bundle
    │   ├── semgrep-rule-creator/
    │   │   ├── 1.0.0.zip
    │   │   └── 1.1.0.zip
    │   └── yara-authoring/
    │       └── 1.0.0.zip
    └── productivity-boosters/ # 另一个 Bundle
        └── git-workflow-helper/
            └── 2.0.0.zip
```

**Step 2: Update API endpoints table**

Replace the API endpoints section (around line 134) with:

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 前端展示页面 |
| `/marketplace.json` | GET | Claude Code 市场索引 |
| `/plugins/{bundle}/{name}/{version}.zip` | GET | 下载插件 |
| `/api/bundles` | GET | 列出所有 Skill Bundles |
| `/api/bundles/{bundle}` | GET | 获取 Bundle 下的所有 skills |
| `/api/search` | GET | 搜索 Bundles 和 Skills |
| `/admin/upload` | POST | 上传新插件（参数：bundle, name, version） |
| `/admin/plugins/{bundle}/{name}/{version}` | DELETE | 删除插件版本 |

**Step 3: Update installation instructions**

Replace the installation section (around line 147) with:

```bash
# 安装整个 Bundle
/plugin install security-tools

# 安装 Bundle 中的单个 Skill
/plugin install security-tools/semgrep-rule-creator
```

**Step 4: Update upload instructions**

Replace the upload section (around line 40) with:

### 方法 1: 通过 Web 管理界面上传（推荐）

访问 `http://localhost:8000/admin/upload`，支持两种上传方式：

#### 上传 Skill Bundle（多个技能）

适用于包含多个技能的 ZIP 文件，系统会自动提取其中的每个技能。

- 填写 `bundle`（技能包名称）
- **留空** `name` 和 `version`
- 选择 ZIP 文件上传

#### 上传单个 Skill

- 填写 `bundle`（技能包名称）
- **填写** `name`（技能名称）和 `version`（版本）
- 选择 ZIP 文件上传

**Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update README for bundle-based architecture

- Update directory structure to show two-layer bundle/skill format
- Update API endpoints table to reflect new bundle endpoints
- Update installation commands to use bundle format
- Update upload instructions to reference bundles instead of collections

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Task 15: Run all tests and verify functionality

**Files:**
- Test: All modified files

**Step 1: Run all tests**

Run:
```bash
pytest tests/ -v
```

Expected: All tests pass

**Step 2: Manual smoke test**

1. Start the server:
```bash
python main.py
```

2. Test endpoints:
```bash
# Test marketplace.json
curl http://localhost:28000/marketplace.json | jq

# Test /api/bundles
curl http://localhost:28000/api/bundles | jq

# Test search
curl "http://localhost:28000/api/search?q=test" | jq
```

3. Visit UI:
   - Open `http://localhost:28000`
   - Test search functionality
   - Test install buttons

4. Test upload:
   - Visit `http://localhost:28000/admin/upload`
   - Upload a test skill ZIP

**Step 3: Fix any issues found**

If any tests fail or bugs are found, fix them and commit the fixes.

**Step 4: Final commit**

```bash
git add .
git commit -m "test: pass all tests and complete smoke testing

- All unit tests passing
- Manual smoke testing completed
- UI search functionality verified
- API endpoints responding correctly

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

## Deployment Instructions (After Implementation)

### Pre-deployment Validation

**Step 1: Run validation script**

```bash
python scripts/validate_marketplace.py
```

Follow the printed instructions to test with Claude Code.

**Step 2: Verify CLI compatibility**

Test the following in Claude Code:
- [ ] `/plugin menu` shows skills
- [ ] `/plugin install {bundle}/{skill}` works
- [ ] `/plugin install {bundle}` works

If compatibility issues are found, update `marketplace_json()` to include `organization` and `collection` fields (set them equal to `bundle`).

### Deployment

**Step 1: Backup existing data**

```bash
mv plugins plugins-backup-$(date +%Y%m%d)
```

**Step 2: Deploy new code**

```bash
git pull origin master
pip install -r requirements.txt
```

**Step 3: Start server**

```bash
python main.py
# or
docker-compose up -d
```

**Step 4: Re-upload skill bundles**

Visit `http://localhost:28000/admin/upload` and re-upload all skill bundles using the new bundle-based structure.

**Step 5: Verify deployment**

- Check homepage displays bundles correctly
- Test search functionality
- Install a skill via CLI
- Verify marketplace.json format

---

## Summary

This implementation plan refactors the Skill Registry from a three-layer to two-layer architecture:

- **15 tasks** covering backend, frontend, testing, and documentation
- Each task broken into bite-sized steps (2-5 minutes each)
- Test-driven approach where applicable
- Frequent commits for easy rollback
- Complete code snippets provided
- Validation and deployment instructions included

Total estimated time: 4-6 hours for implementation and testing.
