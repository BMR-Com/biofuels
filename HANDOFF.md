# Handoff notes

- Feeds can only be tested from GitHub Actions (the build sandbox cannot reach EPA, EIA, CARB, USDA or TradingView).
- TradingView: continuous RIN/LCFS symbols (RN41!, LCS1!) can stall on an old contract; prices.py also pulls named
  contracts and keeps the series with the newest bar.
- No free D5 price exists; D5 is shown through EMTS generation and the D6–D4 band. EPA's own RIN price page is a Qlik
  dashboard with no download.
- No free US canola oil cash price: canola = CBOT soybean oil + 4¢/lb (assumption, labeled on the page).
- UCO = USDA AMS yellow grease as the proxy; Bursa UCO futures (FUCO) shown for Asia.
- 45Z: North American feedstock only from 2026, so imported UCO earns none; CI values are typical pathway levels.
- Policy rows in data/manual/*.csv need a human update when EPA/Treasury/CARB publish; policy_watch flags page changes.
