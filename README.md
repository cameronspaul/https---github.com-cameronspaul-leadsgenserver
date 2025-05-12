# YouTube Analyzer API

This API provides endpoints to search for and analyze YouTube channels, including filtering videos by date ranges.

## Deployment Options

This application can be deployed in several ways:

1. **Local Development**: Run the application locally for development and testing
2. **Docker**: Deploy using Docker for containerized environments
3. **Red Hat OpenShift**: Deploy on Red Hat OpenShift for enterprise-grade hosting

## Local Development Setup

1. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

2. Install Playwright browsers:
   ```
   playwright install
   ```

3. Set your YouTube API key as an environment variable:
   ```
   # Linux/macOS
   export YOUTUBE_API_KEY=your_api_key_here
   
   # Windows
   set YOUTUBE_API_KEY=your_api_key_here
   ```

4. Run the API server:
   ```
   python app.py
   ```

The API will be available at `http://localhost:8080`.

## Docker Deployment

1. Build the Docker image:
   ```
   docker build -t youtube-analyzer-api .
   ```

2. Run the container:
   ```
   docker run -p 8080:8080 -e YOUTUBE_API_KEY=your_api_key_here youtube-analyzer-api
   ```

The API will be available at `http://localhost:8080`.

## Red Hat OpenShift Deployment

For detailed instructions on deploying to Red Hat OpenShift, see [OPENSHIFT_DEPLOYMENT.md](OPENSHIFT_DEPLOYMENT.md).

## API Endpoints

### Health Check

```
GET /api/health
```

Returns a health check response with environment information.

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

## License

This project is licensed under the MIT License - see the LICENSE file for details.
