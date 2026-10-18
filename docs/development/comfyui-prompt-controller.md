# Sofía ComfyUI prompt controller

The owner's reviewed ComfyUI API workflow has prompt nodes 10 (positive) and 11 (negative), sampler node 12, and upscale node 24. The controller writes a **new** copy, never submits anything or changes the original. It keeps the checkpoint, ControlNet conditioning, uploaded pose filename, sampler and seed unmodified.

Example on Venus:

```powershell
git pull --ff-only
python -m pytest -q test/test_comfyui_prompt_controller.py
python -m sofia.creative.comfyui_prompt_controller --workflow "Main 2d image.json" --positive-file "positive.txt" --output "Sofia_review_01.json" --fix-upscale
```

Review the new API-format JSON before submitting through any trusted owner-approved service. No runtime conversational tool, gaming detection, workflow allowlist, private asset storage or host permission integration is claimed. Only the specific reviewed node IDs are supported; fail closed if the graph layout differs. This code is for locally prepared prompt revisions, **not autonomous GPU work**. Keep private anatomical workflows and generated outputs outside the public repo.
