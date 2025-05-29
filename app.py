from flask import Flask, request, jsonify
from flask_cors import CORS
import youtube_analyzer
import datetime
import traceback

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({
        "status": "ok",
        "timestamp": datetime.datetime.now().isoformat()
    })

@app.route('/api/channel', methods=['GET'])
def analyze_channel():
    """
    Analyze a YouTube channel and return the results as JSON

    Query parameters:
    - channel_id: YouTube channel ID
    - username: YouTube username
    - handle: YouTube handle (with or without @)
    - days: Only include videos from the last X days
    - start_date: Only include videos published after this date (format: YYYY-MM-DD)
    - end_date: Only include videos published before this date (format: YYYY-MM-DD)
    - extract_links: Whether to extract external links (default: false)
    """
    try:
        # Get query parameters
        channel_id = request.args.get('channel_id')
        username = request.args.get('username')
        handle = request.args.get('handle')

        # Check if at least one identifier is provided
        if not any([channel_id, username, handle]):
            return jsonify({
                "error": "You must provide either channel_id, username, or handle"
            }), 400

        # Get date filtering parameters
        days_ago = request.args.get('days')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Convert days_ago to integer if provided
        if days_ago:
            try:
                days_ago = int(days_ago)
            except ValueError:
                return jsonify({
                    "error": "days parameter must be an integer"
                }), 400

        # Validate date formats if provided
        if start_date:
            try:
                datetime.datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return jsonify({
                    "error": "start_date must be in YYYY-MM-DD format"
                }), 400

        if end_date:
            try:
                datetime.datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return jsonify({
                    "error": "end_date must be in YYYY-MM-DD format"
                }), 400

        # Get other parameters
        extract_links = request.args.get('extract_links', 'false').lower() == 'true'
        debug = request.args.get('debug', 'false').lower() == 'true'

        # Check if Playwright is available
        if extract_links and not youtube_analyzer.PLAYWRIGHT_AVAILABLE:
            return jsonify({
                "error": "Playwright is not available. Cannot extract external links.",
                "solution": "Install Playwright: pip install playwright and then run: playwright install"
            }), 500

        # Analyze the channel
        try:
            result = youtube_analyzer.analyze_youtube_channel(
                channel_id=channel_id,
                username=username,
                handle=handle,
                days_ago=days_ago,
                start_date=start_date,
                end_date=end_date,
                extract_links=extract_links,
                headless=True,  # Always run in headless mode for API
                verbose=debug   # Show debug info if requested
            )
        except Exception as e:
            print(f"Error in analyze_channel with extract_links={extract_links}: {str(e)}")
            print(traceback.format_exc())

            return jsonify({
                "error": f"Error extracting data: {str(e)}",
                "extract_links_enabled": extract_links
            }), 500

        if not result:
            return jsonify({
                "error": "Could not retrieve data for the specified channel"
            }), 404

        # Process external links to remove YouTube redirect URLs if present
        if 'metrics' in result and 'external_links' in result['metrics']:
            external_links = result['metrics']['external_links']
            for link in external_links:
                if 'url' in link and 'youtube.com/redirect' in link['url']:
                    # Extract the direct URL from YouTube redirect URLs
                    direct_url = youtube_analyzer.extract_direct_url(link['url'])
                    link['url'] = direct_url

        # Return the metrics as JSON
        return jsonify(result)

    except Exception as e:
        # Log the full exception for debugging
        print(f"Error in analyze_channel: {str(e)}")
        print(traceback.format_exc())

        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/search', methods=['GET'])
def search_channels():
    """
    Search for YouTube channels and return the results as JSON

    Query parameters:
    - query: Search query for YouTube channels
    - max_results: Maximum number of results to return (default: 5)
    """
    try:
        # Get query parameters
        query = request.args.get('query')

        if not query:
            return jsonify({
                "error": "query parameter is required"
            }), 400

        # Get max_results parameter
        max_results = request.args.get('max_results', '5')
        try:
            max_results = int(max_results)
            # Limit max_results to a reasonable range
            max_results = min(max(1, max_results), 50)
        except ValueError:
            return jsonify({
                "error": "max_results parameter must be an integer"
            }), 400

        # Search for channels
        channels = youtube_analyzer.search_youtube_channels(query, max_results=max_results)

        if not channels:
            return jsonify({
                "message": "No channels found matching your search query",
                "channels": []
            })

        # Return the search results as JSON
        return jsonify({
            "query": query,
            "count": len(channels),
            "channels": channels
        })

    except Exception as e:
        # Log the full exception for debugging
        print(f"Error in search_channels: {str(e)}")
        print(traceback.format_exc())

        return jsonify({
            "error": str(e)
        }), 500

@app.route('/api/analyze', methods=['GET'])
def analyze_search_results():
    """
    Search for YouTube channels, analyze them, and return the results as JSON

    Query parameters:
    - query: Search query for YouTube channels
    - max_results: Maximum number of results to analyze (default: 5)
    - days: Only include videos from the last X days
    - start_date: Only include videos published after this date (format: YYYY-MM-DD)
    - end_date: Only include videos published before this date (format: YYYY-MM-DD)
    - extract_links: Whether to extract external links (default: false)
    """
    try:
        # Get query parameters
        query = request.args.get('query')

        if not query:
            return jsonify({
                "error": "query parameter is required"
            }), 400

        # Get max_results parameter
        max_results = request.args.get('max_results', '5')
        try:
            max_results = int(max_results)
            # Limit max_results to a reasonable range
            max_results = min(max(1, max_results), 10)  # Lower limit for analysis
        except ValueError:
            return jsonify({
                "error": "max_results parameter must be an integer"
            }), 400

        # Get date filtering parameters
        days_ago = request.args.get('days')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        # Convert days_ago to integer if provided
        if days_ago:
            try:
                days_ago = int(days_ago)
            except ValueError:
                return jsonify({
                    "error": "days parameter must be an integer"
                }), 400

        # Validate date formats if provided
        if start_date:
            try:
                datetime.datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return jsonify({
                    "error": "start_date must be in YYYY-MM-DD format"
                }), 400

        if end_date:
            try:
                datetime.datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return jsonify({
                    "error": "end_date must be in YYYY-MM-DD format"
                }), 400

        # Get other parameters
        extract_links = request.args.get('extract_links', 'false').lower() == 'true'
        debug = request.args.get('debug', 'false').lower() == 'true'

        # Check if Playwright is available
        if extract_links and not youtube_analyzer.PLAYWRIGHT_AVAILABLE:
            return jsonify({
                "error": "Playwright is not available. Cannot extract external links.",
                "solution": "Install Playwright: pip install playwright and then run: playwright install"
            }), 500

        # Search for channels
        channels = youtube_analyzer.search_youtube_channels(query, max_results=max_results)

        if not channels:
            return jsonify({
                "message": "No channels found matching your search query",
                "channels": []
            })

        # Analyze the channels
        try:
            results = youtube_analyzer.analyze_search_results(
                channels,
                days_ago=days_ago,
                start_date=start_date,
                end_date=end_date,
                extract_links=extract_links,
                headless=True,  # Always run in headless mode for API
                verbose=debug   # Show debug info if requested
            )
        except Exception as e:
            print(f"Error in analyze_search_results with extract_links={extract_links}: {str(e)}")
            print(traceback.format_exc())

            return jsonify({
                "error": f"Error analyzing channels: {str(e)}",
                "extract_links_enabled": extract_links
            }), 500

        # Create a clean data structure for JSON export
        export_data = {
            "query": query,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "channels": {}
        }

        # Process each channel's data
        for channel_id, result in results.items():
            metrics = result.get('metrics', {})

            # Process external links to remove YouTube redirect URLs
            external_links = metrics.get('external_links', [])
            for link in external_links:
                if 'url' in link and 'youtube.com/redirect' in link['url']:
                    # Extract the direct URL from YouTube redirect URLs
                    direct_url = youtube_analyzer.extract_direct_url(link['url'])
                    link['url'] = direct_url

            # Add channel data to export
            export_data["channels"][metrics.get('channel_info', {}).get('title', channel_id)] = {
                "channel_info": metrics.get('channel_info', {}),
                "video_metrics": metrics.get('video_metrics', {}),
                "social_handles": metrics.get('social_handles', {}),
                "external_links": external_links,
                "recent_videos": metrics.get('recent_videos', [])
            }

        # Return the analysis results as JSON
        return jsonify(export_data)

    except Exception as e:
        # Log the full exception for debugging
        print(f"Error in analyze_search_results: {str(e)}")
        print(traceback.format_exc())

        return jsonify({
            "error": str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
