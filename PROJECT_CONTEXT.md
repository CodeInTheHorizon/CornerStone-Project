# MarketPulse AI — Complete Project Context

## 1. Project Title

**MarketPulse AI**

### Tagline
**AI/ML-Driven Demand Forecasting and Marketplace Intelligence for Electronics Sellers**

---

## 2. Project Vision

MarketPulse AI is a focused full-stack AI/ML project designed to help sellers make better marketplace decisions using fresh e-commerce data.

The product is **not intended to solve every seller problem**. Its core purpose is to:

1. Collect fresh marketplace data from selected e-commerce platforms.
2. Transform the collected data into a structured training dataset.
3. Train custom machine-learning models.
4. Analyse product trends.
5. Predict marketplace opportunities for a selected electronics product/accessory.
6. Show results through a clear and interactive dashboard.

### Initial Target Domain

**Electronics / electronics accessories**

### Initial Marketplaces

- Amazon
- Flipkart
- Croma
- Alibaba

The architecture should remain modular so marketplaces can be added or removed later without redesigning the complete application.

---

## 3. Core Problem

Offline sellers, small retailers, wholesalers, and new marketplace sellers often do not have their own historical datasets.

Because of that, they may struggle to answer questions such as:

- Which products are currently trending?
- Which marketplace currently has stronger opportunities for a product?
- What price range is common for the product?
- Is competition increasing or decreasing?
- How is the market changing over time?
- Which marketplace appears most suitable for the selected product/accessory?

MarketPulse AI addresses this problem by building a market-intelligence dataset from fresh marketplace observations and then using AI/ML models to generate useful predictions and analytics.

---

## 4. Important Product Constraint

MarketPulse AI should remain a **focused project**.

The first production/demo version should prioritize:

- Electronics only.
- A limited number of marketplaces.
- A limited set of scrapeable/publicly obtainable attributes.
- Reliable data collection.
- Dataset construction.
- Model training.
- Prediction.
- Trend analytics.
- Interactive visualization.

Features such as complete inventory management, order processing, seller accounting, advertising management, logistics management, or a full marketplace ERP are outside the initial scope.

---

## 5. Core Features

### 5.1 Predictive Analytics

The system should use trained ML models to generate predictions from marketplace data.

Possible outputs include:

- Best marketplace recommendation.
- Marketplace suitability score.
- Predicted product opportunity.
- Demand/trend classification.
- Expected price band.
- Competition level.

---

### 5.2 Trend Analysis

The platform should identify changes in marketplace data over time.

Examples:

- Price trend.
- Product availability trend.
- Discount trend.
- Rating/review growth.
- Marketplace listing growth.
- Brand/category movement.
- Product popularity proxy trend.

Trend analysis should be visualized using charts inside the authenticated dashboard.

---

### 5.3 Real-Time / Fresh Data Updates

The application should support fresh data ingestion from e-commerce platforms.

A realistic 10-day MVP may implement this as:

- On-demand scraping.
- Scheduled refresh jobs.
- Recent-data refresh before prediction.

The interface can label the latest collection timestamp so users know how fresh the data is.

> Production scraping should respect marketplace terms, robots rules, rate limits, applicable law, and available official APIs/partner feeds. The scraper layer should therefore be modular and replaceable.

---

### 5.4 Interactive Dashboard

After authentication, users enter the main MarketPulse AI dashboard.

The dashboard should allow a user to:

- View system/model status.
- Select a product/accessory.
- Select a marketplace or compare marketplaces.
- Trigger fresh data collection where supported.
- Train a model.
- Make a prediction.
- View prediction confidence.
- View trend charts.
- View recent predictions.
- View marketplace comparison results.

The provided dashboard image should be used as a **layout reference**, not copied blindly.

---

### 5.5 Custom Models

The application should allow model training using the prepared marketplace dataset.

The MVP should support one stable model pipeline first, with architecture ready for multiple models later.

Recommended first models:

- XGBoost / Random Forest for marketplace classification or scoring.
- Regression model for price/opportunity estimation if needed.

The dashboard can display:

- Model name.
- Last trained timestamp.
- Dataset size.
- Accuracy / F1 score.
- Training status.

---

## 6. Recommended Additional Feature

### Cross-Platform Opportunity Score

This should be the one additional feature beyond the requested feature set.

For the selected product/accessory, MarketPulse AI generates a **0–100 Opportunity Score for each marketplace** by combining measurable marketplace signals such as:

- Price attractiveness.
- Competition intensity.
- Discount activity.
- Rating/review momentum.
- Listing density.
- Product availability.
- Recent trend direction.

Example:

| Marketplace | Opportunity Score |
|---|---:|
| Amazon | 82 |
| Flipkart | 76 |
| Croma | 61 |
| Alibaba | 54 |

This makes the prediction easier to explain than simply saying "Amazon is best".

The score should also show its major contributing factors so the result is interpretable.

---

# 7. Landing Page / Home Page

The public website should contain the following main sections.

## Section 1 — Hero / Navigation

### Top-left
- MarketPulse AI logo.

### Center navigation
- Home
- About
- Features
- Contact

### Top-right
- Login / Register
- Contact button

### Hero content
At the center of the section:

- Project title.
- Short two-line description.
- Primary CTA such as **Explore Market Intelligence**.
- Secondary CTA such as **View Features**.

Suggested description:

> MarketPulse AI converts fresh e-commerce marketplace data into actionable trend insights and machine-learning predictions. Compare opportunities across major platforms and make data-driven product decisions.

---

## Section 2 — Why Choose MarketPulse AI?

Heading:

**Why Choose MarketPulse AI?**

Three interactive cards:

### AI-Powered
Front:
- AI-Powered

Hover/flip state:
- Machine-learning models transform marketplace data into predictions and opportunity insights.

### Real-Time Analytics
Front:
- Real-Time Analytics

Hover/flip state:
- Fresh marketplace observations are collected and analysed to detect current trends and changing opportunities.

### Precision & Accuracy
Front:
- Precision & Accuracy

Hover/flip state:
- Model performance is measured and predictions include confidence/score information instead of unexplained outputs.

### Interaction
The cards should swap/flip on hover with subtle animation.

Avoid excessive 3D effects or animation that makes the landing page feel like a gaming launcher built during a caffeine emergency.

---

## Section 3 — Meet the Developer

Heading:

**Meet the Developer**

Content:

- Developer photo/avatar.
- Name.
- Short introduction.
- Role.
- Skills / project focus.
- Social links with icons.

Suggested links:

- GitHub
- LinkedIn
- Email
- Portfolio

Keep the section clean and professional.

---

## Section 4 — Features

Heading:

**Features**

Feature cards/grid:

1. Predictive Analytics
2. Trend Analysis
3. Real-Time Updates
4. Interactive Dashboard
5. Custom Models
6. Cross-Platform Opportunity Score

Each item should have:

- Icon.
- Feature title.
- One-line description.

---

## Section 5 — Get in Touch

Heading:

**Get in Touch**

Four input fields:

1. Name
2. Email
3. Phone / Contact
4. Message

CTA:

**Send Message**

On click:

- Validate fields.
- Build a formatted WhatsApp message.
- Redirect/open WhatsApp using the configured developer/business WhatsApp number.

Do not expose secrets in frontend code.

---

# 8. Authentication

Users should be able to:

- Register.
- Login.
- Logout.

Suggested MVP:

- Email + password.
- Password hashing.
- JWT/session authentication.
- Protected dashboard routes.

After successful login/register:

`/dashboard`

---

# 9. Main Dashboard

The dashboard should be inspired by the supplied reference image.

## Sidebar

Recommended items:

- Dashboard
- Marketplace Data
- ML Predictor
- Train Model
- Trend Analysis
- Analytics
- Model Status
- Logout

---

## Dashboard Header

Example:

**MarketPulse AI — Platform Predictor Dashboard**

Hero card:

> Predict marketplace opportunities for electronics products using fresh cross-platform data and machine learning.

Buttons:

- New Prediction
- Refresh Marketplace Data

---

## Summary Cards

### Total Predictions
- Number of predictions made.

### Model Accuracy
- Latest validation score.

### Data Freshness
- Last marketplace data refresh timestamp.

### Platforms
- Amazon
- Flipkart
- Croma
- Alibaba

---

## Main Actions

### Train Model

Flow:

1. Select dataset/latest collected dataset.
2. Choose model configuration.
3. Trigger training.
4. Display progress/status.
5. Store metrics/model file.
6. Update model status.

### Select Accessory / Product

Example fields:

- Product category.
- Product/accessory name.
- Brand.
- Price range.
- Optional target marketplace.

### Make Prediction

Result:

- Recommended marketplace.
- Cross-Platform Opportunity Scores.
- Confidence.
- Key reasons.
- Related trend graph.

---

# 10. Marketplace Data Collection

## Objective

Create the dataset required by the ML pipeline from fresh marketplace observations.

## Scraper / Data Connector Inputs

For each marketplace:

- Search keyword/product.
- Category.
- Maximum pages/items.
- Collection timestamp.

## Suggested Fields

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

Optional fields where legally and technically accessible:

```text
shipping_info
delivery_time
badge
sponsored
specifications
stock_status
```

---

## Data Collection Pipeline

```text
Marketplace
    ↓
Scraper / Official API / Data Connector
    ↓
Raw Data
    ↓
Validation
    ↓
Cleaning
    ↓
Normalization
    ↓
Feature Engineering
    ↓
Dataset Storage
    ↓
ML Training
```

---

# 11. Dataset Strategy

Because offline sellers may not have historical datasets, MarketPulse AI builds its own market-observation dataset.

Each periodic collection becomes a snapshot.

Example:

```text
Product A — Amazon — 10 Sep — ₹999 — 4.2 rating — 1200 reviews
Product A — Amazon — 11 Sep — ₹949 — 4.2 rating — 1235 reviews
Product A — Amazon — 12 Sep — ₹899 — 4.3 rating — 1288 reviews
```

With repeated observations, the system creates a time-series style dataset.

This allows trend features such as:

```text
price_change_1d
price_change_7d
review_growth
rating_change
discount_change
listing_growth
availability_change
```

Important limitation:

Scraped marketplace pages generally do **not** expose true unit sales or demand directly. MarketPulse AI should therefore distinguish between:

- **Observed marketplace signals**, and
- **Actual sales demand**.

The MVP can predict an **opportunity/demand proxy** unless a verified sales dataset or seller data is available.

---

# 12. ML Pipeline

## MVP Pipeline

```text
Collected Data
   ↓
Clean Dataset
   ↓
Feature Engineering
   ↓
Train / Validation Split
   ↓
Model Training
   ↓
Evaluation
   ↓
Save Model
   ↓
Prediction API
   ↓
Dashboard
```

## Candidate Features

```text
platform
category
brand
price
discount_percentage
rating
review_count
availability
price_change
review_growth
listing_density
trend_score
competition_score
```

## Candidate Targets

For the MVP, choose **one primary prediction target**.

Recommended:

**Best marketplace / marketplace opportunity class**

or

**Opportunity score**

Do not attempt five unrelated ML targets in the first ten days. Humans invented scope creep long before AI could help them automate it.

---

# 13. Suggested Tech Stack

## Frontend
- React
- Vite
- TypeScript
- Tailwind CSS
- React Router
- Recharts / Chart.js

## Backend
- FastAPI or Node.js/Express

Recommended for this project:

**FastAPI**, because the ML pipeline will already use Python.

## ML
- Python
- pandas
- NumPy
- scikit-learn
- XGBoost

## Scraping / Data Collection
- requests/httpx
- BeautifulSoup
- Playwright only when needed
- Official marketplace APIs where available

## Database
MVP:
- SQLite

Better:
- PostgreSQL

## Authentication
- JWT
- bcrypt/passlib

## Deployment
- Frontend: Vercel
- Backend: Render
- Database: Render PostgreSQL / Supabase / Neon, depending available free tier

---

# 14. Suggested Project Structure

```text
MarketPulse-AI/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   │   ├── HomePage.tsx
│   │   │   ├── LoginPage.tsx
│   │   │   ├── RegisterPage.tsx
│   │   │   ├── DashboardPage.tsx
│   │   │   ├── PredictorPage.tsx
│   │   │   ├── TrainModelPage.tsx
│   │   │   └── TrendsPage.tsx
│   │   ├── services/
│   │   ├── hooks/
│   │   └── types/
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── database/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── scrapers/
│   │   │   ├── amazon.py
│   │   │   ├── flipkart.py
│   │   │   ├── croma.py
│   │   │   └── alibaba.py
│   │   ├── services/
│   │   ├── ml/
│   │   │   ├── preprocessing.py
│   │   │   ├── features.py
│   │   │   ├── train.py
│   │   │   ├── predict.py
│   │   │   └── artifacts/
│   │   └── main.py
│   └── requirements.txt
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── demo/
│
├── notebooks/
├── docs/
├── tests/
├── .env.example
├── README.md
├── CLAUDE.md
└── PROJECT_CONTEXT.md
```

---

# 15. API Outline

## Auth

```http
POST /auth/register
POST /auth/login
GET  /auth/me
```

## Marketplace Data

```http
POST /data/collect
GET  /data/latest
GET  /data/history
GET  /data/status
```

## ML

```http
POST /ml/train
GET  /ml/status
GET  /ml/metrics
POST /ml/predict
```

## Analytics

```http
GET /analytics/trends
GET /analytics/platform-comparison
GET /analytics/opportunity-score
```

---

# 16. 10-Day Development Roadmap

## Day 1 — Freeze Scope + Project Foundation

### Goals
- Finalize MVP requirements.
- Create directory structure.
- Set up frontend/backend.
- Add environment config.
- Prepare database schema.
- Create project documentation.

### Deliverable
Working React + FastAPI skeleton.

### Claude Code Prompt

```text
Read PROJECT_CONTEXT.md before making changes.

Phase 1: Project Foundation.

Build only the foundation for MarketPulse AI.

Tasks:
1. Inspect the repository first.
2. Create/repair a React + Vite + TypeScript frontend and FastAPI backend.
3. Add environment-variable handling and .env.example.
4. Configure CORS.
5. Add backend /health endpoint.
6. Add database connection and minimal models for User, MarketplaceSnapshot, Prediction, and ModelMetadata.
7. Create a clean folder structure matching PROJECT_CONTEXT.md.
8. Do not implement scraping or ML yet.
9. Run available checks and report changed files and commands.

Keep implementation minimal and production-friendly.
```

---

## Day 2 — Landing Page

### Goals
Implement:

- Navbar.
- Hero.
- Why Choose MarketPulse AI.
- Meet the Developer.
- Features.
- Get in Touch.
- WhatsApp redirect.
- Responsive design.

### Claude Code Prompt

```text
Read PROJECT_CONTEXT.md.

Phase 2: Public Landing Page.

Implement the MarketPulse AI homepage only.

Required sections:
1. Navbar with logo left, Home/About/Features/Contact center, Login/Register and Contact right.
2. Hero with a concise two-line MarketPulse AI description and CTA buttons.
3. "Why Choose MarketPulse AI?" with three hover-flip cards:
   AI-Powered, Real-Time Analytics, Precision & Accuracy.
4. "Meet the Developer" section with developer intro and reusable GitHub, LinkedIn, email and portfolio icon links.
5. Features grid for Predictive Analytics, Trend Analysis, Real-Time Updates, Interactive Dashboard, Custom Models, and Cross-Platform Opportunity Score.
6. Get in Touch form with Name, Email, Phone and Message. Submit should open WhatsApp with an encoded formatted message.
7. Responsive layout, dark modern visual style, subtle motion only.

Do not build dashboard/backend logic in this phase.
Reuse components and keep content/config data separate where reasonable.
Run frontend checks before finishing.
```

---

## Day 3 — Authentication + Protected Dashboard Shell

### Goals
- Register.
- Login.
- JWT auth.
- Protected routes.
- Dashboard shell inspired by supplied screenshot.

### Claude Code Prompt

```text
Read PROJECT_CONTEXT.md.

Phase 3: Authentication and Dashboard Shell.

Implement:
1. Register, login, logout.
2. Secure password hashing.
3. JWT authentication.
4. GET /auth/me.
5. Protected frontend dashboard route.
6. Dashboard layout inspired by the supplied reference:
   sidebar, top header, summary cards, Train Model action, Make Prediction action.
7. Sidebar items:
   Dashboard, Marketplace Data, ML Predictor, Train Model, Trend Analysis, Analytics.
8. Use placeholder values where real ML/data is not implemented yet.

Do not implement scraper or model training in this phase.
Add validation/error handling and run backend/frontend checks.
```

---

## Day 4 — Marketplace Data Collection Layer

### Goals
- Implement one marketplace adapter completely.
- Add common scraper interface.
- Store normalized data.
- Prepare adapters for remaining platforms.

### Claude Code Prompt

```text
Read PROJECT_CONTEXT.md.

Phase 4: Marketplace Data Collection.

Create a modular marketplace data-ingestion system.

Requirements:
1. Create a common adapter/interface for marketplace collectors.
2. Fully implement ONE stable marketplace collector first using permitted public data/API access.
3. Add adapter stubs for Amazon, Flipkart, Croma and Alibaba.
4. Normalize collected records into:
   platform, product_name, brand, category, subcategory, price,
   original_price, discount_percentage, rating, review_count,
   availability, seller_name, listing_url, collection_timestamp.
5. Add validation, deduplication and error handling.
6. Persist snapshots to the database.
7. Add:
   POST /data/collect
   GET /data/latest
   GET /data/history
   GET /data/status
8. Never bypass CAPTCHAs, authentication, anti-bot protections, or platform restrictions.
9. If a source cannot be reliably collected, return a clear unsupported/unavailable status instead of fake data.

Keep this phase focused on data ingestion, not ML.
```

---

## Day 5 — Complete Data Pipeline + Feature Engineering

### Goals
- Clean snapshots.
- Generate trainable dataset.
- Add historical features.
- Add demo/fallback dataset.

### Claude Code Prompt

```text
Read PROJECT_CONTEXT.md.

Phase 5: Dataset Builder and Feature Engineering.

Build a deterministic pipeline that transforms stored MarketplaceSnapshot records into an ML-ready dataset.

Implement:
1. Cleaning and null handling.
2. Platform/category normalization.
3. Duplicate removal.
4. Time-based ordering.
5. Feature engineering for:
   price change,
   discount percentage,
   review growth,
   rating change,
   listing density,
   availability signal,
   competition score,
   trend score.
6. Save processed datasets under data/processed or expose them through a service.
7. Add a small demo dataset so the ML pipeline remains testable when live collection is temporarily unavailable.
8. Clearly mark live vs demo records.
9. Add tests for the transformation logic.

Do not train the final model yet.
```

---

## Day 6 — Model Training

### Goals
- Train XGBoost/RandomForest.
- Evaluate.
- Save model.
- Expose status/metrics.

### Claude Code Prompt

```text
Read PROJECT_CONTEXT.md.

Phase 6: ML Training.

Implement the first stable MarketPulse AI model.

Primary goal:
Predict a marketplace opportunity class/score for an electronics product using the processed marketplace dataset.

Requirements:
1. Build preprocessing pipeline.
2. Create train/validation split that avoids obvious leakage.
3. Train a baseline RandomForest and XGBoost model if XGBoost is available.
4. Compare metrics and save the better model.
5. Persist:
   model name,
   training timestamp,
   dataset row count,
   feature names,
   evaluation metrics,
   model artifact path/version.
6. Add:
   POST /ml/train
   GET /ml/status
   GET /ml/metrics
7. Handle insufficient-data conditions clearly.
8. Add tests for training service with a small fixture dataset.

Do not invent high accuracy. Report actual validation metrics.
```

---

## Day 7 — Prediction + Opportunity Score

### Goals
- Product input.
- Predict.
- Rank marketplaces.
- Explain output.

### Claude Code Prompt

```text
Read PROJECT_CONTEXT.md.

Phase 7: Prediction and Cross-Platform Opportunity Score.

Implement:
1. POST /ml/predict.
2. Input fields for electronics product/accessory attributes.
3. Run the saved model.
4. Return ranked marketplace results.
5. Compute a 0-100 Cross-Platform Opportunity Score for each supported marketplace using normalized measurable signals.
6. Return:
   recommended_marketplace,
   opportunity_scores,
   confidence,
   key_factors,
   model_version,
   data_freshness.
7. Add the ML Predictor page in the frontend.
8. Present the result using score cards and a comparison chart.
9. Handle missing/untrained model states gracefully.

Keep explanations tied to actual features used by the system.
```

---

## Day 8 — Trend Analytics + Real-Time Dashboard Integration

### Goals
- Connect dashboard to actual API data.
- Charts.
- Refresh button.
- Freshness indicators.

### Claude Code Prompt

```text
Read PROJECT_CONTEXT.md.

Phase 8: Trend Analytics and Live Dashboard Integration.

Implement:
1. Trend analytics API using stored marketplace snapshots.
2. Price trend.
3. Discount trend.
4. Review/rating momentum.
5. Listing/competition trend where data supports it.
6. Platform comparison.
7. Dashboard cards using real backend values:
   total predictions,
   model accuracy,
   latest data refresh,
   supported platforms.
8. Add a "Refresh Marketplace Data" action with loading/error/success states.
9. Add latest collection timestamp and clearly show data freshness.
10. Build interactive charts on Trend Analysis / Analytics pages.

Do not add unrelated seller-management modules.
```

---

## Day 9 — Testing + UI Polish + Security

### Goals
- Fix bugs.
- Responsive UI.
- API errors.
- Security.
- Loading states.
- Empty states.

### Claude Code Prompt

```text
Read PROJECT_CONTEXT.md.

Phase 9: Stabilization and UI Polish.

Audit the existing MarketPulse AI implementation rather than rewriting it.

Tasks:
1. Find broken frontend/backend flows.
2. Test auth, collection, training, prediction and analytics.
3. Add missing loading, empty, error and success states.
4. Validate request inputs.
5. Protect authenticated endpoints.
6. Remove hardcoded secrets.
7. Improve responsive behavior.
8. Improve dashboard visual consistency.
9. Add subtle hover/transitions only.
10. Fix accessibility basics: labels, keyboard focus, contrast, button states.
11. Run tests/builds and report unresolved issues.

Do not add new features in this phase.
```

---

## Day 10 — Deployment + Demo Readiness

### Goals
- Vercel frontend.
- Render backend.
- Production env.
- README.
- Demo seed.
- Final validation.

### Claude Code Prompt

```text
Read PROJECT_CONTEXT.md.

Phase 10: Production Deployment Preparation.

Prepare MarketPulse AI for:
- Frontend: Vercel
- Backend: Render

Tasks:
1. Audit environment variables.
2. Configure production API base URL.
3. Add/verify Render start command and health endpoint.
4. Add/verify Vercel configuration if needed.
5. Configure production CORS safely.
6. Ensure model artifact/data paths work in deployment.
7. Avoid depending on local-only filesystem state for critical persistent data.
8. Add demo-mode fallback if live marketplace collection is unavailable during presentation.
9. Update README with:
   setup,
   env variables,
   local run,
   architecture,
   ML flow,
   deployment,
   limitations.
10. Run final frontend build and backend tests.
11. Produce a short final deployment checklist and known limitations.

Do not claim deployment succeeded unless it has actually been verified.
```

---

# 17. Development Priority

If time becomes limited, use this order:

```text
1. Working landing page
2. Authentication
3. Dashboard
4. One working live/fresh data collector
5. Normalized dataset
6. ML training
7. Prediction
8. Opportunity Score
9. Trend charts
10. Remaining marketplace adapters
11. Deployment polish
```

A project with one reliable ingestion source and one honest model is much stronger than four decorative "real-time" scrapers that quietly return nonsense.

---

# 18. MVP Acceptance Criteria

The 10-day version is considered complete when:

- [ ] Landing page matches the defined sections.
- [ ] Register/login/logout works.
- [ ] Dashboard is protected.
- [ ] At least one marketplace data connector works reliably.
- [ ] Data is normalized and stored.
- [ ] Dataset builder works.
- [ ] Model can be trained from the processed dataset.
- [ ] Model metrics are shown.
- [ ] User can choose an electronics product/accessory.
- [ ] Prediction API works.
- [ ] Marketplace recommendation is shown.
- [ ] Cross-Platform Opportunity Scores are shown.
- [ ] Trend charts use collected historical snapshots.
- [ ] Dashboard shows latest data freshness.
- [ ] Frontend builds successfully.
- [ ] Backend tests pass.
- [ ] Deployment configuration exists.
- [ ] README documents limitations honestly.

---

# 19. Non-Goals for the 10-Day MVP

Do not implement:

- Complete seller ERP.
- Order placement.
- Automated purchasing.
- Inventory warehouse management.
- Ad campaign management.
- Payment gateway.
- Full logistics integration.
- Dozens of categories.
- Deep-learning models without sufficient data.
- Fake real-time metrics.
- Scraping techniques that bypass protections.

---

# 20. Final Product Flow

```text
Visitor
   ↓
MarketPulse AI Landing Page
   ↓
Register / Login
   ↓
Authenticated Dashboard
   ↓
Choose Electronics Product / Accessory
   ↓
Refresh / Use Latest Marketplace Data
   ↓
Dataset + Feature Pipeline
   ↓
Train / Load Model
   ↓
Prediction
   ↓
Marketplace Ranking
   ↓
Cross-Platform Opportunity Score
   ↓
Trend Analysis + Interactive Dashboard
```

---

# 21. Claude Code Working Rules

Claude Code should follow these rules during development:

1. Always read `PROJECT_CONTEXT.md` before implementation.
2. Work on only the requested phase.
3. Inspect existing files before creating replacements.
4. Preserve working code from previous phases.
5. Do not redesign architecture unless necessary.
6. Prefer reusable modules.
7. Keep ML claims tied to actual data.
8. Never fabricate scraper results.
9. Never fabricate evaluation metrics.
10. Run available tests/builds after each phase.
11. Report:
   - files changed,
   - tests run,
   - unresolved issues,
   - next recommended phase.
12. Keep token usage controlled by avoiding unnecessary rewrites and large generated documentation unless requested.

---

# 22. Current Reference Dashboard

The supplied dashboard image is a visual reference for the authenticated dashboard.

Important visual ideas to retain:

- Dark theme.
- Left sidebar.
- Strong top header.
- Summary metric cards.
- Clear Train Model action.
- Clear Make Prediction action.
- Model status indicator.
- Four-platform summary.

The final MarketPulse AI dashboard should extend this design with:

- Data freshness.
- Product/accessory selection.
- Marketplace comparison.
- Opportunity Scores.
- Trend charts.
- Recent predictions.

