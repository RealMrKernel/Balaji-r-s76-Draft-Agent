# 🤖 LinkedIn AI Agent - Features Handout

Welcome to the **LinkedIn AI Agent**! This powerful CLI-based tool helps you plan, draft, schedule, analyze, and optimize your LinkedIn content using advanced AI (Google Gemini) and data-driven insights.

Here is a comprehensive guide to the different features available in the system:

---

## 📅 1. Weekly Content Planner (`plan`)
Generate data-driven weekly content schedules automatically.
- **Smart Scheduling**: Recommends optimal posting windows based on your historical engagement data.
- **Now-Next-Later Strategy**: Balances immediate high-priority topics with medium-term ideas and experimental content.
- **Performance Suggestions**: Analyzes past performance to suggest timing and topic improvements.

## ✍️ 2. AI-Powered Post Drafter (`draft` & `enhance`)
Create compelling LinkedIn posts using Google's Gemini AI or built-in templates.
- **Context-Aware Formatting**: Supports multiple post formats including `story`, `short`, and `carousel`.
- **RAG Integration**: Finds your similar previous posts to maintain your unique voice and provide context.
- **Content Enhancement**: Boost engagement on existing drafts by applying AI optimizations targeting specific engagement rates.

## 🎣 3. Hook Generator for A/B Testing (`hooks`)
First impressions matter. The Hook Generator gives you multiple starting lines for the same topic.
- **Variations**: Instantly generate 3-5 different hook variations for A/B testing.
- **Psychological Triggers**: AI crafts hooks designed to capture attention immediately.

## ⏰ 4. Smart Scheduler & Queuing (`queue` & `post`)
Never miss the perfect time to post.
- **Optimal Queuing**: Assigns your drafts to the best performing time slots automatically.
- **Schedule Management**: Preview your upcoming queue and resolve any scheduling conflicts.
- **Ready-to-Post Output**: Easily output the final content when it's time to publish.

## 📊 5. Metrics Ingester & Analytics (`metrics` & `export`)
Turn your LinkedIn data into actionable insights.
- **Data Import**: Ingest post analytics directly from CSV exports.
- **Deep Analysis**: Track performance trends across different time periods (7d, 30d, etc.).
- **Data Export**: Export your generated posts and metrics into clean formats (CSV/JSON) for external reporting and analysis.

## 🕸️ 6. Live Content Scraper (`scrape`)
Bridge the gap between live LinkedIn data and your local workflow.
- **Analytics Scraping**: Extract real-time analytics and post content directly from LinkedIn URLs or input files.
- **Automated Data Cleaning**: Scraped post data is automatically cleaned (removing boilerplate headers, footers, hashtags, and formatting newlines into single lines).
- **History Tracking**: Metrics are tracked historically (`data/history/`) every time a scrape is run, avoiding data overwrites and allowing trend analysis over time.
- **Integration**: Feeds scraped insights directly into the content planner and drafter.
- **Headless Mode**: Run seamless data extraction without interrupting your workflow.

## 💬 7. Comment Coach (`replies`)
Drive engagement beyond the original post.
- **Smart Suggestions**: Get AI-suggested replies for top-performing threads to build relationships.
- **Engagement Opportunities**: Identify the best comments to interact with.

---
**Tip:** Run `python li.py help` in your terminal to see the exact usage and available parameters for the CLI commands!

## 🖥️ Graphical Interface (GUI)
Prefer a visual interface over the command line? The system includes a Streamlit web app with dedicated tools (like the visual Content Scraper manager).
Launch it by running:
```bash
streamlit run gui.py
```
