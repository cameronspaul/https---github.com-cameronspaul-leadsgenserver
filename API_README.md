# YouTube Analyzer API

This API provides endpoints to search for and analyze YouTube channels, including filtering videos by date ranges.

## Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Install Playwright browsers:
   ```
   playwright install
   ```

3. Run the API server:
   ```
   python api.py
   ```

The API will be available at `http://localhost:5000`.

## API Endpoints

### Health Check

```
GET /api/health
```

Returns a simple health check response to verify the API is running.

### Search for YouTube Channels

```
GET /api/search?query=SEARCH_TERM&max_results=5
```

Parameters:
- `query` (required): Search term for YouTube channels
- `max_results` (optional): Maximum number of results to return (default: 5, max: 50)

Returns a list of YouTube channels matching the search query.

### Analyze a Specific YouTube Channel

```
GET /api/channel?channel_id=CHANNEL_ID&days=3
```

Parameters (one of the following is required):
- `channel_id`: YouTube channel ID
- `username`: YouTube username
- `handle`: YouTube handle (with or without @)

Date filtering parameters (optional):
- `days`: Only include videos from the last X days
- `start_date`: Only include videos published after this date (format: YYYY-MM-DD)
- `end_date`: Only include videos published before this date (format: YYYY-MM-DD)

Other parameters:
- `extract_links` (optional): Whether to extract external links from the channel's about page (default: false)
- `debug` (optional): Whether to show detailed debug information in the server logs (default: false)

Returns detailed metrics and information about the specified YouTube channel, including video URLs and thumbnail links.

### Search and Analyze YouTube Channels

```
GET /api/analyze?query=SEARCH_TERM&max_results=5&days=3
```

Parameters:
- `query` (required): Search term for YouTube channels
- `max_results` (optional): Maximum number of results to analyze (default: 5, max: 10)

Date filtering parameters (optional):
- `days`: Only include videos from the last X days
- `start_date`: Only include videos published after this date (format: YYYY-MM-DD)
- `end_date`: Only include videos published before this date (format: YYYY-MM-DD)

Other parameters:
- `extract_links` (optional): Whether to extract external links from the channel's about page (default: false)
- `debug` (optional): Whether to show detailed debug information in the server logs (default: false)

Returns detailed metrics and information about multiple YouTube channels matching the search query, including video URLs and thumbnail links.

## Examples

### Get videos from a channel published in the last 3 days

```
GET /api/channel?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw&days=3
```

### Get videos from a channel published between specific dates

```
GET /api/channel?channel_id=UC_x5XG1OV2P6uZZ5FSM9Ttw&start_date=2023-01-01&end_date=2023-12-31
```

### Search for tech channels and analyze their videos from the last week

```
GET /api/analyze?query=tech%20news&max_results=3&days=7
```

## Response Data

### Video Information

For each video, the API returns the following information:

- `title`: The title of the video
- `published_at`: The date and time when the video was published
- `views`: The number of views
- `likes`: The number of likes
- `comments`: The number of comments
- `video_id`: The YouTube video ID
- `video_url`: The direct URL to the video (e.g., https://www.youtube.com/watch?v=VIDEO_ID)
- `thumbnail_url`: The URL to the video thumbnail image

### Channel Information

For each channel, the API returns:

- Basic channel details (title, ID, subscriber count, etc.)
- Video metrics (average views, likes, comments, etc.)
- Recent videos with the information listed above
- External links (if requested with the `extract_links` parameter)

## Notes

- The API uses the YouTube Data API, which has rate limits. If you encounter rate limit errors, wait and try again later.
- The `extract_links` parameter uses Playwright to scrape the channel's about page, which can be slower than API-only requests.
- Date filtering is applied to the videos retrieved from the channel, not to the channel itself.

## Troubleshooting

### External Links Not Working

If the external links extraction is not working:

1. Make sure Playwright is installed:
   ```
   pip install playwright
   playwright install
   ```

2. Use the `debug=true` parameter to see detailed logs:
   ```
   GET /api/channel?channel_id=CHANNEL_ID&extract_links=true&debug=true
   ```

3. Check the server logs for any errors related to Playwright.

4. Some YouTube channels may have anti-scraping measures or different page layouts that make it difficult to extract links. Try with a different channel to see if the issue is specific to one channel.
