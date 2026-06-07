# MMAcademy Publishing Pipeline

## Step 1 — Module Brief
- Clinton provides a 1–2 paragraph brief describing the SMC concept to be taught
- Brief includes: module number, title, key terms, practical exercise idea

## Step 2 — AI Draft
- ChatGPT generates the full module draft following the module template
- Output: complete module with all template fields

## Step 3 — Triple AI Review
- Claude, Gemini, and Groq each review the draft independently
- Each flags terminology violations, tone violations, structure violations, boundary violations
- If any flags, draft is returned to Step 2 for revision
- If all three approve, draft proceeds

## Step 4 — Human Proofread
- Clinton (or designated editor) reads the final draft
- Uses content_validation_checklist.md to verify every item
- Stamps "Approved for Publication" with date and version number

## Step 5 — Chart Verification
- Confirm the referenced chart file exists in /static/assets/learn/charts/
- Confirm annotations follow chart_annotation_rules.md

## Step 6 — Publish
- Module is added to the live Academy
- Version number and date are recorded
- Previous version archived if this is an update

## Post‑Publish
- Blog auto‑posting system may generate a 2‑sentence excerpt for social media
- Weekly "Learning Corner" snippet may link to the module
