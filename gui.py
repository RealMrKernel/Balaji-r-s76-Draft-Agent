import streamlit as st
import os
import json
import uuid
import pandas as pd
from datetime import datetime, timedelta
import sys

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from li import load_config, get_optimal_windows, generate_content, ENHANCED_MODE, load_all_metrics, load_all_posts

try:
    from core.prompting import ContentGenerator # type: ignore
except ImportError:
    ContentGenerator = None

# Set up page configuration
st.set_page_config(
    page_title="LinkedIn AI Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State variables for saving
if 'current_draft' not in st.session_state:
    st.session_state.current_draft = None
if 'current_plan' not in st.session_state:
    st.session_state.current_plan = None

# Sidebar Navigation
st.sidebar.title("🤖 LinkedIn AI Agent")
st.sidebar.write(f"**Gemini AI Status:** {'✅ Enabled' if ENHANCED_MODE else '⚠️ Disabled'}")

page = st.sidebar.radio("Navigation", ["✍️ Post Drafter", "📅 Weekly Planner", "📊 Analytics & Metrics", "🕸️ Content Scraper"])

# Ensure data directories exist
for directory in ['data/posts', 'data/metrics', 'data/schedules']:
    os.makedirs(directory, exist_ok=True)

# ----------------- POST DRAFTER -----------------
if page == "✍️ Post Drafter":
    st.title("✍️ Create a LinkedIn Post")
    st.write("Generate high-quality LinkedIn posts using AI and your past performance data.")
    
    with st.form("draft_form"):
        topic = st.text_input("Post Topic", placeholder="e.g., Lessons from building an MVP")
        format_type = st.selectbox("Content Format", ["story", "short", "carousel"])
        use_gemini = st.checkbox("Use Gemini AI (Enhanced Generation)", value=ENHANCED_MODE, disabled=not ENHANCED_MODE)
        
        submitted = st.form_submit_button("🚀 Generate Draft")
        
    if submitted and topic:
        with st.spinner("Generating draft..."):
            if use_gemini and ContentGenerator:
                generator = ContentGenerator(use_gemini=True)
                post_data = generator.generate_post(topic, format_type, enhance_with_ai=True)
            else:
                post_data = generate_content(topic, format_type)
            
            st.session_state.current_draft = post_data
            st.success("Draft generated successfully!")

    # Display the draft if it exists in session state
    if st.session_state.current_draft:
        post = st.session_state.current_draft
        st.subheader("Draft Preview")
        
        st.info(f"**Target Window:** {post.get('target_window', {}).get('day', 'TBD')} at {post.get('target_window', {}).get('hour', 'TBD')}:00")
        
        # Display body
        st.markdown(f"```text\n{post.get('body', '')}\n```")
        
        st.write(f"**Tags:** {', '.join(post.get('tags', []))}")
        st.write(f"**Call to Action:** {post.get('cta', '')}")
        
        # Save Button
        if st.button("💾 Save Draft to Workspace"):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            # Collect safe characters manually with an explicit length limit
            topic_str = str(topic)
            safe_topic_chars = []
            for c in topic_str:
                if (c.isalnum() or c in (' ', '-', '_')) and len(safe_topic_chars) < 30:
                    safe_topic_chars.append(c)
            safe_topic = "".join(safe_topic_chars).rstrip()
            output_file = f"data/posts/draft_{safe_topic.replace(' ', '_')}_{timestamp}.json"
            
            with open(output_file, 'w') as f:
                json.dump(post, f, indent=2)
            st.success(f"Draft saved successfully to `{output_file}`!")

# ----------------- WEEKLY PLANNER -----------------
elif page == "📅 Weekly Planner":
    st.title("📅 Weekly Content Planner")
    st.write("Automatically schedule your content using the Now-Next-Later framework.")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Week Starting Date")
        
    if st.button("🔄 Generate Weekly Plan"):
        with st.spinner("Analyzing past engagement to find optimal windows..."):
            week_of = start_date.strftime('%Y-%m-%d')
            config = load_config()
            topics = config.get('topics', ['product', 'engineering', 'founder'])
            windows = get_optimal_windows()
            
            # Generate plan structure
            plan_data = {
                "week_of": week_of,
                "now": [
                    {"topic": f"Latest insights on {topics[0]}", "priority": "high", "target_window": {"day": windows[0].day, "hour": windows[0].hour}} if len(windows) > 0 else {},
                    {"topic": f"Key lessons from {topics[1] if len(topics) > 1 else topics[0]}", "priority": "high", "target_window": {"day": windows[1].day if len(windows) > 1 else windows[0].day, "hour": windows[1].hour if len(windows) > 1 else windows[0].hour + 1}} if len(windows) > 0 else {}
                ],
                "next": [
                    {"topic": f"Deep dive into {topics[1] if len(topics) > 1 else topics[0]} best practices", "priority": "medium", "target_window": {"day": windows[2].day if len(windows) > 2 else windows[0].day, "hour": windows[2].hour if len(windows) > 2 else windows[0].hour + 2}} if len(windows) > 0 else {}
                ],
                "later": [
                    {"topic": f"Personal story about {topic} journey", "priority": "low", "experiment": f"Test ±{config.get('experiment_spread_hours', 2)}h from optimal window"} for topic in topics
                ],
                "recommended_windows": [w.to_dict() for w in windows[:5]] if windows else [],
                "generated_at": datetime.now().isoformat()
            }
            
            st.session_state.current_plan = plan_data
            
    if st.session_state.current_plan:
        plan = st.session_state.current_plan
        st.success(f"Plan generated for week of {plan['week_of']}")
        
        st.subheader("🔥 NOW (High Priority)")
        for item in plan.get('now', []):
            if item:
                st.write(f"- **{item.get('topic')}** (Target: {item.get('target_window',{}).get('day')} @ {item.get('target_window',{}).get('hour')}:00)")
                
        st.subheader("⏭️ NEXT (Medium Priority)")
        for item in plan.get('next', []):
            if item:
                st.write(f"- **{item.get('topic')}** (Target: {item.get('target_window',{}).get('day')} @ {item.get('target_window',{}).get('hour')}:00)")

        st.subheader("🔮 LATER (Experimental/Backlog)")
        for item in plan.get('later', []):
            st.write(f"- **{item.get('topic')}** ({item.get('experiment', 'No experiment defined')})")
            
        if st.button("💾 Save Weekly Plan"):
            output_file = f"data/schedules/plan_{plan['week_of']}.json"
            with open(output_file, 'w') as f:
                json.dump(plan, f, indent=2)
            st.success(f"Plan saved successfully to `{output_file}`!")

# ----------------- ANALYTICS & METRICS -----------------
elif page == "📊 Analytics & Metrics":
    st.title("📊 Performance Analytics")
    st.write("View historical performance of your content.")
    
    metrics = load_all_metrics()
    posts = load_all_posts()
    
    if not metrics and not posts:
        st.warning("No data found! Use `python li.py init` to generate sample data, or `python li.py scrape` to get real data.")
    else:
        # Display high level stats
        total_posts = len(posts)
        total_metrics = len(metrics)
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Drafts/Posts", total_posts)
        col2.metric("Recorded Metrics", total_metrics)
        
        if metrics:
            df = pd.DataFrame(metrics)
            
            # --- FEATURE 1: DATA FILTERING ---
            st.subheader("🔍 Filter Data")
            col_f1, col_f2 = st.columns(2)
            
            min_impressions = 0
            if 'impressions' in df.columns and not df.empty:
                min_impressions = int(df['impressions'].min())
                max_impressions = int(df['impressions'].max())
                
                # Protect slider against empty or single-value ranges
                if max_impressions > min_impressions:
                    with col_f1:
                        target_impressions = st.slider("Minimum Impressions", min_impressions, max_impressions, min_impressions)
                        df = df[df['impressions'] >= target_impressions]
            
            # Additional text filter (e.g., search by post_id or source)
            with col_f2:
                search_query = st.text_input("Search (Post ID)", "")
                if search_query:
                    df = df[df['post_id'].str.contains(search_query, case=False, na=False)]
                    
            if 'impressions' in df.columns:
                col3.metric("Filtered Impressions", f"{df['impressions'].sum():,}")
                
            # --- FEATURE 2: DATA DELETION ---
            st.subheader("Metrics Data (Select rows to delete)")
            
            # We use an interactive dataframe with a checkbox column to allow selection
            df.insert(0, "Select", False)
            edited_df = st.data_editor(
                df,
                hide_index=True,
                column_config={"Select": st.column_config.CheckboxColumn(required=True)},
                disabled=[col for col in df.columns if col != "Select"],
                use_container_width=True,
                key="metrics_editor"
            )
            
            selected_rows = edited_df[edited_df["Select"]]
            if not selected_rows.empty:
                if st.button("🗑️ Delete Selected Records", type="primary"):
                    post_ids_to_delete = set(selected_rows["post_id"].tolist())
                    deleted_count = 0
                    
                    import os
                    base_dir = os.path.dirname(__file__) # type: ignore
                    for folder, id_key in [('metrics', 'post_id'), ('posts', 'id')]:
                        folder_path = os.path.join(base_dir, 'data', str(folder)) # type: ignore
                        if not os.path.exists(folder_path): continue # type: ignore
                            
                        for filename in os.listdir(folder_path): # type: ignore
                            if not str(filename).endswith('.json'): continue
                            filepath = os.path.join(folder_path, str(filename)) # type: ignore
                            
                            try:
                                with open(filepath, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                    
                                if isinstance(data, list):
                                    original_len = len(data)
                                    # Handle both `id` and `post_id` since posts and metrics use different keys sometimes
                                    new_data = [d for d in data if str(d.get(id_key, d.get('post_id'))) not in post_ids_to_delete]
                                    if len(new_data) < original_len:
                                        if len(new_data) == 0:
                                            os.remove(filepath) # type: ignore
                                        else:
                                            with open(filepath, 'w', encoding='utf-8') as f:
                                                json.dump(new_data, f, indent=2, ensure_ascii=False)
                                            
                                elif isinstance(data, dict):
                                    if str(data.get(id_key, data.get('post_id'))) in post_ids_to_delete:
                                        os.remove(filepath) # type: ignore
                            except Exception as e:
                                pass # Ignore bad JSON files during rotation
                                
                    st.success(f"Successfully deleted {len(post_ids_to_delete)} record(s)! Please refresh the page.")
                    st.stop()
            
            # Simple bar chart based on the FILTERED dataframe
            if 'published_at' in edited_df.columns and 'impressions' in edited_df.columns and not edited_df.empty:
                st.subheader("Impressions Over Time")
                # Safely parse dates, mapping Italian months if necessary
                def parse_scraped_date(d_str):
                    if not isinstance(d_str, str): return pd.NaT
                    import re
                    # Replace Italian abbreviations
                    it_to_en = {"gen":"jan", "feb":"feb", "mar":"mar", "apr":"apr", "mag":"may", "giu":"jun", "lug":"jul", "ago":"aug", "set":"sep", "ott":"oct", "nov":"nov", "dic":"dec"}
                    clean_str = d_str.lower()
                    for it, en in it_to_en.items():
                        clean_str = re.sub(r'\b' + it + r'\b', en, clean_str)
                    try:
                        from dateutil import parser
                        return parser.parse(clean_str, dayfirst=True)
                    except:
                        return pd.NaT

                temp_dates = edited_df['published_at'].apply(parse_scraped_date)
                temp_dates = pd.to_datetime(temp_dates, errors='coerce') # Ensure it's a pandas datetime series
                valid_mask = temp_dates.notna()
                if valid_mask.any():
                    df_chart = edited_df.loc[valid_mask].copy()
                    df_chart['Date'] = temp_dates[valid_mask].dt.date
                    impressions_by_date = df_chart.groupby('Date')['impressions'].sum().reset_index()
                    st.bar_chart(impressions_by_date.set_index('Date'))
                else:
                    st.info("No valid dates found in the filtered metrics data to display a timeline chart.")
        
        if posts:
            with st.expander("View Saved Post Drafts"):
                for p in posts:
                    st.write(f"**{p.get('title', 'Untitled')}** ({p.get('format', 'unknown')})")
                    st.caption(f"Generated at: {p.get('generated_at', 'Unknown')}")

# ----------------- CONTENT SCRAPER -----------------
elif page == "🕸️ Content Scraper":
    st.title("🕸️ Live Content Scraper")
    st.write("Extract analytics and post content directly from live LinkedIn URLs.")
    
    # --- File Upload Integration ---
    uploaded_file = st.file_uploader("Upload LinkedIn Export (.xlsx) to auto-extract URLs", type=["xlsx", "xls", "csv"])
    extracted_urls = ""
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_upload = pd.read_csv(uploaded_file)
            else:
                # LinkedIn exports usually have URLs in the 3rd sheet ('Contenuti principali'), starting on row 2
                xls = pd.ExcelFile(uploaded_file)
                if len(xls.sheet_names) >= 3:
                    df_upload = pd.read_excel(xls, sheet_name=2, skiprows=1)
                else:
                    df_upload = pd.read_excel(xls) # fallback
            
            # Find the URL column robustly
            url_col = None
            for col in df_upload.columns:
                if any(kw in str(col).lower() for kw in ("url", "link", "post", "href")):
                    url_col = col
                    break
            
            # Fallback for LinkedIn's exact italian formatting: sometimes row 0 is headers
            if not url_col and not df_upload.empty:
                # Try setting first row as header manually
                df_upload.columns = df_upload.iloc[0]
                df_upload = df_upload[1:]
                for col in df_upload.columns:
                    if any(kw in str(col).lower() for kw in ("url", "link", "post", "href")):
                        url_col = col
                        break
                        
            if url_col:
                # Handle cases where multiple columns might have the exact same name returning a DataFrame instead of a Series
                target_col = df_upload[url_col]
                if isinstance(target_col, pd.DataFrame):
                    target_col = target_col.iloc[:, 0]
                    
                valid_urls = target_col.dropna().astype(str).str.strip().tolist()
                valid_urls = [u for u in valid_urls if u.startswith("http")]
                if valid_urls:
                    extracted_urls = "\n".join(valid_urls)
                    st.success(f"✅ Automatically extracted {len(valid_urls)} URLs from the file!")
                else:
                    st.warning("Found a URL column, but no valid HTTP links were inside it.")
            else:
                st.warning("Could not automatically detect a 'URL' or 'Link' column in this file.")
                
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
            
    # Default text area, prepopulated with extracted URLs if available
    urls_input = st.text_area("LinkedIn URLs", value=extracted_urls, placeholder="https://www.linkedin.com/posts/...\n(Enter one URL per line)", height=150)
    headless = st.checkbox("Run in Background (Headless Mode)", value=False, help="Runs the browser hidden. Uncheck this if you need to manually log in first.")
    
    if st.button("🔍 Scrape Data"):
        urls = [u.strip() for u in urls_input.splitlines() if u.strip().startswith('http')]
        
        if not urls:
            st.warning("Please enter at least one valid HTTP URL.")
        else:
            with st.spinner(f"Scraping {len(urls)} URLs... Please wait (this could take a minute)."):
                try:
                    # FIX FOR WINDOWS: Playwright sync API under Streamlit throws NotImplementedError 
                    # in asyncio subprocess execution without the correct EventLoopPolicy.
                    if sys.platform == 'win32':
                        import asyncio
                        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                        
                    from core.scraper import LinkedInScraper
                    scraper = LinkedInScraper(headless=headless)
                    records = scraper.scrape_urls(urls)
                    
                    if not records:
                        st.error("⚠️ No data was extracted.")
                    else:
                        success_count = 0
                        
                        def safe_int(val) -> int:
                            if not val: return 0
                            clean = str(val).replace(",", "").replace(".", "").strip()
                            return int(clean) if clean.isdigit() else 0
                            
                        # Process records into standard JSON schemas
                        for idx, record in enumerate(records):
                            if record.get("error"):
                                st.error(f"Failed to scrape {record['post_url'][:50]}...: {record['error']}")
                                continue
                                
                            # Extract the true LinkedIn Activity URN from the analytics URL or post URL
                            from core.scraper import get_post_id_from_url, clean_scraped_post_data
                            post_id = get_post_id_from_url(record.get("analytics_url", ""), record.get("post_url", ""), idx)
                            
                            # 1. Save to data/posts
                            post_text = record.get("post_text", "").strip()
                            pub_date = record.get("post_date", "")
                            pub_time = record.get("post_time", "")
                            published_at = f"{pub_date} {pub_time}".strip()
                            
                            post_data = {
                                "id": post_id,
                                "title": f"Scraped Post: {published_at}",
                                "body": post_text,
                                "generated_at": datetime.now().isoformat(),
                                "format": "scraped",
                                "tags": [],
                                "source": record["post_url"]
                            }
                            
                            # Apply data cleaning
                            post_data = clean_scraped_post_data(post_data)
                            
                            with open(f"data/posts/post_{post_id}.json", 'w', encoding='utf-8') as f:
                                json.dump(post_data, f, indent=2, ensure_ascii=False)
                    
                            # 2. Save to data/metrics
                            metrics_data = {
                                "post_id": post_id,
                                "impressions": safe_int(record.get("impressions")),
                                "reactions": safe_int(record.get("reactions")),
                                "comments": safe_int(record.get("comments")),
                                "shares": safe_int(record.get("reposts")),
                                "clicks": 0, 
                                "extracted_at": datetime.now().isoformat(),
                                "published_at": published_at
                            }
                            
                            # Include engagement rate
                            if int(metrics_data["impressions"]) > 0:
                                eng_rate = (int(metrics_data["reactions"]) + int(metrics_data["comments"]) + int(metrics_data["shares"])) / float(metrics_data["impressions"])
                                metrics_data["engagement_rate"] = float(round(eng_rate, 4)) # type: ignore
                                
                            with open(f"data/metrics/metrics_{post_id}.json", 'w', encoding='utf-8') as f:
                                json.dump(metrics_data, f, indent=2, ensure_ascii=False)
                                
                            # 3. Save to data/history
                            history_dir = "data/history"
                            os.makedirs(history_dir, exist_ok=True)
                            history_file = f"{history_dir}/history_{post_id}.json"
                            
                            history_data = []
                            if os.path.exists(history_file):
                                try:
                                    with open(history_file, 'r', encoding='utf-8') as f:
                                        history_data = json.load(f)
                                except Exception:
                                    history_data = []
                                    
                            history_data.append(metrics_data)
                            with open(history_file, 'w', encoding='utf-8') as f:
                                json.dump(history_data, f, indent=2, ensure_ascii=False)
                                
                            success_count += 1
                            
                        if success_count > 0:
                            st.success(f"✅ Successfully scraped and saved {success_count}/{len(urls)} posts and metrics to your workspace!")
                        else:
                            st.warning("⚠️ Scraper ran, but no valid data was extracted. Ensure the URLs are valid public or logged-in LinkedIn posts.")
                            
                except Exception as e:
                    import traceback
                    st.error(f"❌ Error during scraping: {str(e)}")
                    st.code(traceback.format_exc(), language="text")
                    st.info("💡 Ensure you have run: pip install playwright pandas openpyxl && playwright install chromium")
