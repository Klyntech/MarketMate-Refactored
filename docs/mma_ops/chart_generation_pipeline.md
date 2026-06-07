# MMAcademy Chart Generation Pipeline

## Source
- All educational charts are generated from the real candles database (MongoDB `candles` collection)
- Never AI‑generated or manually drawn

## Tool
- chart_renderer.py (MarketMate's existing chart renderer)
- Annotation rules: see chart_annotation_rules.md

## Process
1. Identify the historical candle range needed for the module
2. Configure chart_renderer.py with the correct date range and concept markup
3. Render PNG
4. Save to website/static/assets/learn/charts/ with the filename: {module_id}_{concept}.png
5. Verify annotations against chart_annotation_rules.md
6. Module text references the exact filename

## Restrictions
- No TP/SL lines on educational charts
- No price labels on annotation lines
- No watermarks on chart images
- The MarketMate logo only appears in the page header, not on the chart
