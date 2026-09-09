# MarketPulse AI — Claude Code Chat Reference

## Date
10 September 2026

## Purpose

This file captures the current agreed direction for MarketPulse AI so Claude Code can continue development without relying on unrelated previous conversations.

---

## User's Current Project Direction

The project should **not target everything**.

MarketPulse AI should focus on:

- E-commerce marketplace data collection.
- Electronics / electronics accessories.
- Fresh/real-time marketplace observations.
- Building a dataset from marketplace data.
- Training ML models.
- Predictive analytics.
- Trend analysis.
- Real-time/fresh updates.
- Interactive dashboard.
- Custom models.

Initial marketplace targets:

- Amazon
- Flipkart
- Croma
- Alibaba

---

## Public Landing Page Requirements

### Section 1 — Hero / Navigation

Top-left:
- MarketPulse AI logo.

Center:
- Home
- About
- Features
- Contact

Top-right:
- Login/Register.
- Contact button.

Center hero:
- Project title.
- About two lines describing MarketPulse AI.

---

### Section 2 — Why Choose MarketPulse AI?

Heading:

**Why Choose MarketPulse AI?**

Three card-style elements:

1. AI-Powered
2. Real-Time Analytics
3. Precision & Accuracy

Each card should reveal/swap to its description on hover.

---

### Section 3 — Meet the Developer

Must include:

- Developer introduction.
- Social/contact links.
- Relevant logos/icons.

Examples:

- GitHub
- LinkedIn
- Email
- Portfolio

---

### Section 4 — Features

Required project features:

1. Predictive Analytics
2. Trend Analysis
3. Real-Time Updates
4. Interactive Dashboard
5. Custom Models

One additional agreed feature:

**Cross-Platform Opportunity Score**

This ranks/scores marketplaces for a selected product based on measurable marketplace signals.

---

### Section 5 — Get in Touch

Four fields:

1. Name
2. Email
3. Phone/contact
4. Message

Button:

**Send Message**

The action should open WhatsApp with a pre-filled formatted message.

---

## Authentication Flow

User should be able to:

- Register.
- Login.
- Logout.

After login/register:

```text
/dashboard
```

---

## Main Dashboard Requirements

The user provided a dark dashboard screenshot as the visual/layout reference.

The current screenshot contains:

- Left sidebar.
- Dashboard.
- ML Predictor.
- Train Model.
- Analytics.
- Model status.
- Welcome panel.
- Total predictions.
- Model accuracy.
- Available categories.
- Platforms.
- Train Model action.
- Platform Prediction action.

MarketPulse AI's final dashboard should retain this style while adding:

- Marketplace data refresh.
- Data freshness timestamp.
- Electronics product/accessory selection.
- Prediction results.
- Cross-platform scores.
- Trend charts.
- Recent prediction history.

---

## Core Data/ML Concept

Offline/new sellers may not already possess historical datasets.

Therefore, MarketPulse AI should construct its own market-observation dataset using repeated marketplace collection.

Concept:

```text
Amazon / Flipkart / Croma / Alibaba
        ↓
Marketplace data collection
        ↓
Raw snapshots
        ↓
Cleaning + normalization
        ↓
Feature engineering
        ↓
Training dataset
        ↓
ML model
        ↓
Prediction + analytics
```

Suggested collected fields:

```text
platform
product_name
brand
category
subcategory
price
original_price
discount_percentage
rating
review_count
availability
seller_name
listing_url
collection_timestamp
```

Repeated snapshots can generate trend features such as:

```text
price_change
discount_change
review_growth
rating_change
availability_change
listing_density
competition_score
trend_score
```

---

## Important ML/Product Limitation

Marketplace pages usually do not expose true unit sales directly.

Therefore, unless verified seller/sales data is available, the system must avoid claiming it predicts exact real-world demand.

For the MVP, the safer target is:

- Marketplace opportunity.
- Demand proxy.
- Marketplace suitability.
- Opportunity score.

Model outputs should be tied to observable signals.

---

## New Extra Feature

### Cross-Platform Opportunity Score

For each selected product/accessory, calculate a 0–100 score for each marketplace.

Possible factors:

- Price attractiveness.
- Competition.
- Discount activity.
- Rating/review momentum.
- Availability.
- Listing density.
- Recent trend direction.

Example:

```text
Amazon    82
Flipkart  76
Croma     61
Alibaba   54
```

The top-scoring platform becomes the recommended marketplace.

---

## 10-Day Build Plan

### Day 1
Project foundation:
- React/Vite frontend.
- FastAPI backend.
- Database.
- Environment config.
- Health endpoint.

### Day 2
Landing page:
- Hero.
- Why choose.
- Developer.
- Features.
- WhatsApp form.

### Day 3
Authentication + protected dashboard shell.

### Day 4
Marketplace data collection architecture + one working adapter.

### Day 5
Dataset cleaning + feature engineering.

### Day 6
ML training pipeline.

### Day 7
Prediction + Opportunity Score.

### Day 8
Trend analytics + real dashboard integration.

### Day 9
Testing, security, responsive UI polish.

### Day 10
Vercel/Render deployment preparation and final demo validation.

---

## Claude Code Development Rules

Claude Code should:

1. Read `PROJECT_CONTEXT.md` first.
2. Work phase by phase.
3. Inspect before editing.
4. Preserve previous working functionality.
5. Avoid unnecessary rewrites.
6. Keep frontend, backend, scraper and ML layers modular.
7. Never fabricate marketplace data.
8. Never fabricate ML accuracy.
9. Add clear error states when live data is unavailable.
10. Run available tests/builds after every phase.
11. Report changed files, test results and unresolved issues.
12. Keep token usage efficient.

---

## Current MVP Definition

The project is successful when it can:

```text
User opens landing page
→ registers/logs in
→ enters dashboard
→ selects electronics product/accessory
→ collects or loads latest marketplace data
→ trains/loads ML model
→ makes prediction
→ compares marketplaces
→ sees opportunity score
→ views market trends
```

---

## Scope Guard

Do not add unrelated modules such as:

- Order management.
- Payment systems.
- Full inventory ERP.
- Logistics management.
- Advertising automation.
- Multi-industry support.
- Unnecessary deep learning.

Focus on making the marketplace-data-to-prediction pipeline genuinely work.

