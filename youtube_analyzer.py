import json
import datetime
import time
import argparse
from urllib.parse import urlparse, parse_qs, unquote
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os


API_KEY = os.environ.get('YOUTUBE_API_KEY') 

# Import Playwright for scraping channel links
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    print("Warning: Playwright not installed. Channel links extraction will not be available.")
    print("To install: pip install playwright")
    print("Then: playwright install")
    PLAYWRIGHT_AVAILABLE = False


def retrieve_youtube_data(channel_id=None, username=None, handle=None, days_ago=None, start_date=None, end_date=None, verbose=True):
    """
    Retrieve YouTube channel data using the YouTube Data API

    Args:
        channel_id (str, optional): The YouTube channel ID
        username (str, optional): The YouTube username
        handle (str, optional): The YouTube handle (with or without @)
        days_ago (int, optional): Only include videos from the last X days
        start_date (str, optional): Only include videos published after this date (format: YYYY-MM-DD)
        end_date (str, optional): Only include videos published before this date (format: YYYY-MM-DD)
        verbose (bool, optional): Whether to print status messages. Defaults to True.

    Returns:
        dict: The channel data response
    """
    # You'll need to set up a YouTube API key
    # Get it from https://console.developers.google.com/
    api_key = API_KEY

    try:
        # Initialize the YouTube API client
        youtube = build('youtube', 'v3', developerKey=api_key)

        # Determine which parameter to use for the API call
        if channel_id:
            request = youtube.channels().list(
                part="snippet,contentDetails,statistics",
                id=channel_id
            )
        elif username:
            request = youtube.channels().list(
                part="snippet,contentDetails,statistics",
                forUsername=username
            )
        elif handle:
            # Remove @ if it exists
            if handle.startswith('@'):
                handle = handle[1:]
            request = youtube.channels().list(
                part="snippet,contentDetails,statistics",
                forHandle=handle
            )
        else:
            if verbose:
                print("Error: You must provide either a channel_id, username, or handle.")
            return None

        # Execute the request
        response = request.execute()

        # Check if any channels were found
        if not response.get('items'):
            if verbose:
                print("No channel found with the provided identifier.")
            return None

        # Get the uploads playlist ID
        channel = response['items'][0]
        uploads_playlist_id = channel['contentDetails']['relatedPlaylists']['uploads']

        # Get the channel's videos
        videos_request = youtube.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=uploads_playlist_id,
            maxResults=50  # Maximum allowed by the API
        )
        videos_response = videos_request.execute()

        # Filter videos by date
        if days_ago is not None or start_date is not None or end_date is not None:
            filtered_items = []

            # Calculate cutoff date if days_ago is specified
            cutoff_date_str = None
            if days_ago is not None:
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
                cutoff_date_str = cutoff_date.isoformat() + 'Z'

            # Convert start_date and end_date to ISO format if provided
            start_date_str = None
            if start_date is not None:
                try:
                    start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                    start_date_str = start_date_obj.isoformat() + 'Z'
                except ValueError:
                    print(f"Warning: Invalid start_date format. Expected YYYY-MM-DD, got {start_date}")

            end_date_str = None
            if end_date is not None:
                try:
                    # Set end_date to the end of the day (23:59:59)
                    end_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d")
                    end_date_obj = end_date_obj.replace(hour=23, minute=59, second=59)
                    end_date_str = end_date_obj.isoformat() + 'Z'
                except ValueError:
                    print(f"Warning: Invalid end_date format. Expected YYYY-MM-DD, got {end_date}")

            # Filter videos based on the date criteria
            for item in videos_response.get('items', []):
                published_at = item['snippet']['publishedAt']

                # Check if the video meets all the specified date criteria
                meets_criteria = True

                if cutoff_date_str is not None and published_at < cutoff_date_str:
                    meets_criteria = False

                if start_date_str is not None and published_at < start_date_str:
                    meets_criteria = False

                if end_date_str is not None and published_at > end_date_str:
                    meets_criteria = False

                if meets_criteria:
                    filtered_items.append(item)

            videos_response['items'] = filtered_items

        # Get detailed stats for each video
        video_ids = [item['contentDetails']['videoId'] for item in videos_response.get('items', [])]

        if video_ids:
            # Split into chunks of 50 (API limit)
            video_id_chunks = [video_ids[i:i+50] for i in range(0, len(video_ids), 50)]

            all_video_stats = []
            for chunk in video_id_chunks:
                video_stats_request = youtube.videos().list(
                    part="statistics,contentDetails,snippet",
                    id=','.join(chunk)
                )
                video_stats_response = video_stats_request.execute()
                all_video_stats.extend(video_stats_response.get('items', []))

            # Add video stats to the response
            response['video_stats'] = {'items': all_video_stats}
        else:
            response['video_stats'] = {'items': []}

        return response

    except HttpError as e:
        if verbose:
            print(f"YouTube API Error: {e}")
        return None
    except Exception as e:
        if verbose:
            print(f"Error retrieving YouTube data: {e}")
        return None


def extract_direct_url(youtube_redirect_url):
    """
    Extract the actual direct URL from a YouTube redirect URL

    Args:
        youtube_redirect_url (str): YouTube redirect URL

    Returns:
        str: The actual direct URL or the original URL if not a redirect
    """
    # Check if it's a YouTube redirect URL
    if 'youtube.com/redirect' in youtube_redirect_url:
        try:
            # Parse the URL and extract the 'q' parameter which contains the actual URL
            parsed_url = urlparse(youtube_redirect_url)
            query_params = parse_qs(parsed_url.query)

            if 'q' in query_params:
                # URL decode the 'q' parameter to get the actual URL
                direct_url = unquote(query_params['q'][0])
                return direct_url
        except Exception as e:
            print(f"Error extracting direct URL: {e}")

    # If not a redirect or if there was an error, return the original URL
    return youtube_redirect_url


def get_channel_links(url, headless=True, verbose=True):
    """
    Get all external links from a YouTube channel's about page

    Args:
        url (str): YouTube channel URL
        headless (bool): Whether to run browser in headless mode
        verbose (bool, optional): Whether to print status messages. Defaults to True.

    Returns:
        dict: Dictionary containing channel info and links
    """
    # Make sure the URL is a YouTube channel
    if 'youtube.com' not in url:
        raise ValueError("URL must be a YouTube channel URL")

    # Ensure the URL points to the about page
    if not url.endswith('/about'):
        if url.endswith('/'):
            url = url + 'about'
        else:
            url = url + '/about'

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = context.new_page()

        # Navigate to the about page
        if verbose:
            print(f"Navigating to {url}")
        try:
            # Use a shorter timeout and don't wait for network to be idle
            page.goto(url, wait_until="domcontentloaded", timeout=15000)
            if verbose:
                print("Page loaded")

            # Accept cookies if the dialog appears
            try:
                # Look for common cookie consent buttons
                cookie_selectors = [
                    "button[aria-label='Accept all']",
                    "button[aria-label='Accept cookies']",
                    "button:has-text('Accept all')",
                    "button:has-text('Accept cookies')",
                    "button:has-text('I agree')"
                ]

                for selector in cookie_selectors:
                    if page.is_visible(selector, timeout=1000):
                        if verbose:
                            print(f"Accepting cookies with selector: {selector}")
                        page.click(selector)
                        break

                # Immediately look for the links section after cookie acceptance
                if verbose:
                    print("Looking for links section...")
                link_selectors = ["#links-section", "#link-list-container", "a[href^='https://www.youtube.com/redirect']"]

                for selector in link_selectors:
                    try:
                        # Use a short timeout since links appear quickly
                        page.wait_for_selector(selector, timeout=2000)
                        if verbose:
                            print(f"Found links section with selector: {selector}")
                        # No need to wait further once we find the links
                        break
                    except Exception as e:
                        if verbose:
                            print(f"Link selector {selector} not found, trying next...")

            except Exception as e:
                if verbose:
                    print(f"Warning during page load: {e}")
                    print("Continuing anyway...")

        except Exception as e:
            if verbose:
                print(f"Error loading page: {e}")
            browser.close()
            raise

        # Extract channel name
        try:
            # Try different selectors for the channel name
            channel_name_selectors = [
                "#channel-name",
                "#channel-header-container h1",
                "ytd-channel-name #text"
            ]

            channel_name = "Unknown"
            for selector in channel_name_selectors:
                if page.is_visible(selector, timeout=500):
                    channel_name = page.text_content(selector).strip()
                    break
        except Exception as e:
            if verbose:
                print(f"Warning: Could not get channel name: {e}")
            channel_name = "Unknown"

        # Extract channel ID
        channel_id = "Unknown"
        try:
            # Extract from URL
            parsed_url = urlparse(url)
            path_parts = parsed_url.path.strip('/').split('/')

            if 'channel' in path_parts:
                # URL format: youtube.com/channel/CHANNEL_ID/about
                idx = path_parts.index('channel')
                if idx + 1 < len(path_parts):
                    channel_id = path_parts[idx + 1]
            elif '@' in path_parts[0]:
                # URL format: youtube.com/@USERNAME/about
                # We'll use the handle as the ID
                channel_id = path_parts[0]
        except Exception as e:
            if verbose:
                print(f"Warning: Could not extract channel ID from URL: {e}")

        # Extract subscriber count
        try:
            # Try different selectors for the subscriber count
            subscriber_selectors = [
                "#subscriber-count",
                "yt-formatted-string.ytd-c4-tabbed-header-renderer",
                "#meta-contents #metadata-line"
            ]

            subscriber_count = "Unknown"
            for selector in subscriber_selectors:
                if page.is_visible(selector, timeout=500):
                    subscriber_text = page.text_content(selector).strip()
                    # Extract just the subscriber count
                    if 'subscribers' in subscriber_text.lower():
                        subscriber_count = subscriber_text
                    break
        except Exception as e:
            if verbose:
                print(f"Warning: Could not get subscriber count: {e}")
            subscriber_count = "Unknown"

        # Get links section - try multiple selectors for different YouTube layouts
        # No need to wait, extract links immediately
        if verbose:
            print("Extracting links...")
        links = page.evaluate('''
            () => {
                // Try different selectors for the links section
                const linkSelectors = [
                    '#link-list-container', // Older layout
                    '#links-section',       // Newer layout
                    'ytd-channel-about-metadata-renderer #links-container' // Another possible layout
                ];

                let links = [];

                // Try each selector
                for (const selector of linkSelectors) {
                    const linksSection = document.querySelector(selector);
                    if (linksSection) {
                        console.log('Found links section with selector: ' + selector);

                        // Try different selectors for the actual links
                        const linkElementSelectors = [
                            'a.yt-simple-endpoint',
                            'a[href]',
                            'ytd-channel-about-metadata-renderer a[href]'
                        ];

                        for (const linkSelector of linkElementSelectors) {
                            const linkElements = linksSection.querySelectorAll(linkSelector);
                            if (linkElements && linkElements.length > 0) {
                                console.log('Found ' + linkElements.length + ' links with selector: ' + linkSelector);

                                links = Array.from(linkElements)
                                    .filter(link => {
                                        // Filter out YouTube internal links
                                        const href = link.href;
                                        return href &&
                                               (href.includes('youtube.com/redirect') ||
                                                (!href.includes('youtube.com/') &&
                                                 !href.startsWith('javascript:') &&
                                                 href !== '#'));
                                    })
                                    .map(link => {
                                        return {
                                            text: link.textContent.trim() || 'Link',
                                            url: link.href
                                        };
                                    });

                                if (links.length > 0) {
                                    break; // Found links, no need to try other selectors
                                }
                            }
                        }

                        if (links.length > 0) {
                            break; // Found links, no need to try other sections
                        }
                    }
                }

                // If no links found with the above selectors, try a more general approach
                if (links.length === 0) {
                    console.log('Trying general approach to find links...');
                    // Look for any links in the about section
                    const aboutSection = document.querySelector('ytd-channel-about-metadata-renderer');
                    if (aboutSection) {
                        const allLinks = aboutSection.querySelectorAll('a[href]');
                        links = Array.from(allLinks)
                            .filter(link => {
                                // Filter out YouTube internal links
                                const href = link.href;
                                return href &&
                                       !href.includes('youtube.com/') &&
                                       !href.startsWith('javascript:') &&
                                       href !== '#';
                            })
                            .map(link => {
                                return {
                                    text: link.textContent.trim() || 'Link',
                                    url: link.href
                                };
                            });
                    }
                }

                return links;
            }
        ''')

        if verbose:
            print(f"Found {len(links)} links")

        # Extract channel description
        try:
            # Try different selectors for the description
            description_selectors = [
                "#description",
                "ytd-channel-about-metadata-renderer #description",
                "#meta-contents #description"
            ]

            description = ""
            # Try to find any of the selectors with a short timeout
            for selector in description_selectors:
                if page.is_visible(selector, timeout=500):
                    # Found a selector, now extract the text
                    description = page.evaluate(f'''
                        () => {{
                            const descElement = document.querySelector('{selector}');
                            return descElement ? descElement.textContent.trim() : '';
                        }}
                    ''')
                    if description:
                        break
            else:
                # No selectors found or no text in them
                description = ""
        except Exception as e:
            if verbose:
                print(f"Warning: Could not get description: {e}")
            description = ""

        # Close the browser
        browser.close()

        # Create result object
        result = {
            'channel_name': channel_name,
            'channel_id': channel_id,
            'subscriber_count': subscriber_count,
            'description': description,
            'links': links
        }

        return result


def get_channel_links_playwright(channel_id=None, username=None, handle=None, headless=True, verbose=True):
    """
    Get all external links from a YouTube channel's about page using Playwright

    Args:
        channel_id (str, optional): The YouTube channel ID
        username (str, optional): The YouTube username
        handle (str, optional): The YouTube handle (with or without @)
        headless (bool): Whether to run browser in headless mode
        verbose (bool, optional): Whether to print status messages. Defaults to True.

    Returns:
        dict: Dictionary containing channel info and links
    """
    if not PLAYWRIGHT_AVAILABLE:
        if verbose:
            print("Playwright is not available. Cannot extract channel links.")
            print("To install: pip install playwright")
            print("Then run: playwright install")
        return {
            'channel_name': 'Unknown',
            'channel_id': channel_id or 'Unknown',
            'subscriber_count': 'Unknown',
            'description': '',
            'links': []
        }

    # Construct the URL based on the provided parameters
    if channel_id:
        url = f"https://www.youtube.com/channel/{channel_id}/about"
    elif username:
        url = f"https://www.youtube.com/user/{username}/about"
    elif handle:
        # Remove @ if it exists
        if handle.startswith('@'):
            handle = handle[1:]
        url = f"https://www.youtube.com/@{handle}/about"
    else:
        if verbose:
            print("Error: You must provide either a channel_id, username, or handle.")
        return None

    try:
        # Use the get_channel_links function to extract links
        return get_channel_links(url, headless=headless, verbose=verbose)
    except Exception as e:
        if verbose:
            print(f"Error in get_channel_links_playwright: {e}")
            import traceback
            print(traceback.format_exc())
        # Return empty result on error
        return {
            'channel_name': 'Unknown',
            'channel_id': channel_id or username or handle or 'Unknown',
            'subscriber_count': 'Unknown',
            'description': '',
            'links': [],
            'error': str(e)
        }


def extract_account_metrics(data):
    """
    Extract metrics from YouTube channel data

    Args:
        data (dict): The YouTube API response data

    Returns:
        dict: Dictionary of metrics
    """
    metrics = {}

    if not data or 'items' not in data or not data['items']:
        return metrics

    channel = data['items'][0]
    snippet = channel.get('snippet', {})
    statistics = channel.get('statistics', {})

    # Extract channel info
    # Get thumbnail URLs (different sizes available)
    thumbnails = snippet.get('thumbnails', {})
    profile_picture_url = thumbnails.get('high', {}).get('url',
                         thumbnails.get('medium', {}).get('url',
                         thumbnails.get('default', {}).get('url', 'Unknown')))

    metrics['channel_info'] = {
        'id': channel.get('id', 'Unknown'),
        'title': snippet.get('title', 'Unknown'),
        'custom_url': snippet.get('customUrl', 'Unknown'),
        'country': snippet.get('country', 'N/A'),
        'published_at': snippet.get('publishedAt', 'Unknown'),
        'subscriber_count': int(statistics.get('subscriberCount', 0)),
        'video_count': int(statistics.get('videoCount', 0)),
        'total_views': int(statistics.get('viewCount', 0)),
        'profile_picture_url': profile_picture_url
    }

    # Extract video metrics if available
    if 'video_stats' in data and 'items' in data['video_stats']:
        videos = data['video_stats']['items']

        if videos:
            # Calculate video metrics
            total_views = sum(int(video.get('statistics', {}).get('viewCount', 0)) for video in videos)
            total_likes = sum(int(video.get('statistics', {}).get('likeCount', 0)) for video in videos)
            total_comments = sum(int(video.get('statistics', {}).get('commentCount', 0)) for video in videos)

            # Calculate averages
            avg_views = total_views / len(videos) if videos else 0
            avg_likes = total_likes / len(videos) if videos else 0
            avg_comments = total_comments / len(videos) if videos else 0

            # Calculate engagement rate (likes + comments) / views
            engagement_rate = (total_likes + total_comments) / total_views if total_views > 0 else 0

            # Find max and min views
            max_views = max(int(video.get('statistics', {}).get('viewCount', 0)) for video in videos) if videos else 0
            min_views = min(int(video.get('statistics', {}).get('viewCount', 0)) for video in videos) if videos else 0

            # Store metrics
            metrics['video_metrics'] = {
                'analyzed_videos_count': len(videos),
                'avg_views': avg_views,
                'max_views': max_views,
                'min_views': min_views,
                'total_views': total_views,
                'avg_likes': avg_likes,
                'avg_comments': avg_comments,
                'engagement_rate': engagement_rate
            }

            # Extract recent videos
            recent_videos = []
            for video in videos:
                snippet = video.get('snippet', {})
                statistics = video.get('statistics', {})
                video_id = video.get('id', 'Unknown')

                # Create video URL from video ID
                video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id != 'Unknown' else 'Unknown'

                # Get thumbnail URLs (different sizes available)
                thumbnails = snippet.get('thumbnails', {})
                thumbnail_url = thumbnails.get('high', {}).get('url',
                               thumbnails.get('medium', {}).get('url',
                               thumbnails.get('default', {}).get('url', 'Unknown')))

                recent_videos.append({
                    'title': snippet.get('title', 'Unknown'),
                    'published_at': snippet.get('publishedAt', 'Unknown'),
                    'views': int(statistics.get('viewCount', 0)),
                    'likes': int(statistics.get('likeCount', 0)),
                    'comments': int(statistics.get('commentCount', 0)),
                    'video_id': video_id,
                    'video_url': video_url,
                    'thumbnail_url': thumbnail_url
                })

            # Sort by published date (newest first)
            recent_videos.sort(key=lambda x: x['published_at'], reverse=True)
            metrics['recent_videos'] = recent_videos



    return metrics



def format_metrics(metrics):
    """
    Format metrics for display

    Args:
        metrics (dict): Dictionary of metrics

    Returns:
        str: Formatted metrics string
    """
    if not metrics:
        return "No metrics available"

    formatted = "\n=== CHANNEL METRICS ===\n"

    # Channel info
    channel_info = metrics.get('channel_info', {})
    formatted += f"Channel: {channel_info.get('title', 'Unknown')}\n"
    formatted += f"Channel ID: {channel_info.get('id', 'Unknown')}\n"
    formatted += f"Custom URL: {channel_info.get('custom_url', 'None')}\n"
    formatted += f"Country: {channel_info.get('country', 'N/A')}\n"
    formatted += f"Created: {channel_info.get('published_at', 'Unknown')}\n"
    formatted += f"Subscribers: {channel_info.get('subscriber_count', 0):,}\n"
    formatted += f"Total Videos: {channel_info.get('video_count', 0):,}\n"
    formatted += f"Total Views: {channel_info.get('total_views', 0):,}\n"

    # Video metrics
    video_metrics = metrics.get('video_metrics', {})
    if video_metrics:
        formatted += "\n=== VIDEO METRICS ===\n"
        formatted += f"Analyzed Videos: {video_metrics.get('analyzed_videos_count', 0)}\n"
        formatted += f"Average Views: {video_metrics.get('avg_views', 0):,.1f}\n"
        formatted += f"Maximum Views: {video_metrics.get('max_views', 0):,}\n"
        formatted += f"Minimum Views: {video_metrics.get('min_views', 0):,}\n"
        formatted += f"Average Likes: {video_metrics.get('avg_likes', 0):,.1f}\n"
        formatted += f"Average Comments: {video_metrics.get('avg_comments', 0):,.1f}\n"
        formatted += f"Engagement Rate: {video_metrics.get('engagement_rate', 0):.2%}\n"

    # Detailed video averages
    video_averages = metrics.get('video_averages', {})
    if video_averages:
        formatted += "\n=== DETAILED VIDEO AVERAGES ===\n"
        formatted += f"Videos Analyzed: {video_averages.get('count', 0)}\n"
        formatted += f"Average Views: {video_averages.get('avg_views', 0):,.1f}\n"
        formatted += f"Average Likes: {video_averages.get('avg_likes', 0):,.1f}\n"
        formatted += f"Average Comments: {video_averages.get('avg_comments', 0):,.1f}\n"
        formatted += f"Like to View Ratio: {video_averages.get('like_to_view_ratio', 0):.2%}\n"
        formatted += f"Comment to View Ratio: {video_averages.get('comment_to_view_ratio', 0):.2%}\n"
        formatted += f"Overall Engagement Rate: {video_averages.get('engagement_rate', 0):.2%}\n"

        # Format duration in minutes and seconds
        avg_duration = video_averages.get('avg_duration_seconds', 0)
        minutes = int(avg_duration // 60)
        seconds = int(avg_duration % 60)
        formatted += f"Average Video Duration: {minutes}m {seconds}s\n"


    # Recent videos
    recent_videos = metrics.get('recent_videos', [])
    if recent_videos:
        formatted += "\n=== RECENT VIDEOS ===\n"
        for i, video in enumerate(recent_videos[:5], 1):  # Show only top 5 videos
            formatted += f"{i}. {video.get('title', 'Unknown')}\n"
            formatted += f"   Published: {video.get('published_at', 'Unknown')}\n"
            formatted += f"   URL: {video.get('video_url', 'Unknown')}\n"
            formatted += f"   Thumbnail: {video.get('thumbnail_url', 'Unknown')}\n"
            formatted += f"   Views: {video.get('views', 0):,}\n"
            formatted += f"   Likes: {video.get('likes', 0):,}\n"
            formatted += f"   Comments: {video.get('comments', 0):,}\n\n"

    return formatted


def format_search_results(channels):
    """
    Format search results for display

    Args:
        channels (list): List of channel information dictionaries

    Returns:
        str: Formatted search results string
    """
    if not channels:
        return "No channels found"

    formatted = "\n=== SEARCH RESULTS ===\n"
    formatted += f"Found {len(channels)} channels:\n\n"

    for i, channel in enumerate(channels, 1):
        # Format the published date
        published_date = channel.get('published_at', 'Unknown')
        if published_date != 'Unknown':
            try:
                # Convert ISO format to more readable format
                dt = datetime.datetime.fromisoformat(published_date.replace('Z', '+00:00'))
                published_date = dt.strftime('%Y-%m-%d')
            except:
                pass  # Keep original format if conversion fails

        # Truncate description
        description = channel.get('description', '')
        if len(description) > 100:
            description = description[:97] + '...'

        formatted += f"{i}. {channel.get('title', 'Unknown')}\n"
        formatted += f"   Channel ID: {channel.get('channel_id', 'N/A')}\n"
        formatted += f"   Created: {published_date}\n"
        formatted += f"   Description: {description}\n"
        formatted += f"   Thumbnail: {channel.get('thumbnail', 'N/A')}\n"
        formatted += f"   Profile Picture: {channel.get('profile_picture_url', 'N/A')}\n\n"

    return formatted


def analyze_youtube_channel(channel_id=None, username=None, handle=None, days_ago=None, start_date=None, end_date=None, extract_links=True, headless=True, verbose=True):
    """
    Analyze a YouTube channel and display metrics

    Args:
        channel_id (str, optional): The YouTube channel ID
        username (str, optional): The YouTube username
        handle (str, optional): The YouTube handle
        days_ago (int, optional): Only include videos from the last X days
        start_date (str, optional): Only include videos published after this date (format: YYYY-MM-DD)
        end_date (str, optional): Only include videos published before this date (format: YYYY-MM-DD)
        extract_links (bool): Whether to extract external links using Playwright
        headless (bool): Whether to run browser in headless mode when extracting links
        verbose (bool, optional): Whether to print status messages. Defaults to True.

    Returns:
        dict: The raw data and metrics
    """
    identifier = channel_id or username or handle

    # Prepare date filter message
    date_filter_msg = ""
    if days_ago:
        date_filter_msg = f"(last {days_ago} days)"
    elif start_date and end_date:
        date_filter_msg = f"(from {start_date} to {end_date})"
    elif start_date:
        date_filter_msg = f"(from {start_date})"
    elif end_date:
        date_filter_msg = f"(until {end_date})"

    if verbose:
        if date_filter_msg:
            print(f"Retrieving data for YouTube channel: {identifier} {date_filter_msg}")
        else:
            print(f"Retrieving data for YouTube channel: {identifier}")

    data = retrieve_youtube_data(channel_id, username, handle, days_ago, start_date, end_date, verbose=verbose)

    if not data or 'items' not in data or not data['items']:
        if verbose:
            print(f"Error: Could not retrieve data for {identifier}")
        return None

    metrics = extract_account_metrics(data)

    # Calculate detailed video averages
    if 'video_stats' in data and 'items' in data['video_stats']:
        videos = data['video_stats']['items']
        video_averages = calculate_video_averages(videos)
        metrics['video_averages'] = video_averages

    # Extract links using Playwright if requested
    channel_links = None
    if extract_links and PLAYWRIGHT_AVAILABLE:
        if verbose:
            print("\n=== EXTRACTING CHANNEL LINKS USING PLAYWRIGHT ===")
        try:
            channel_links = get_channel_links_playwright(channel_id, username, handle, headless=headless, verbose=verbose)

            if channel_links and channel_links.get('links'):
                # Add links to metrics
                metrics['external_links'] = channel_links.get('links', [])

                # Print links if verbose
                if verbose:
                    print("\nExternal Links:")
                    for link in channel_links.get('links', []):
                        if 'direct_url' in link and link['direct_url'] != link['url']:
                            print(f"- {link['text']}: {link['direct_url']} (YouTube redirect)")
                        else:
                            print(f"- {link['text']}: {link['url']}")
            else:
                if verbose:
                    print("No external links found")
                metrics['external_links'] = []
        except Exception as e:
            if verbose:
                print(f"Error extracting links: {e}")
            metrics['external_links'] = []
    else:
        # If Playwright is not available or links extraction is not requested
        metrics['external_links'] = []

    if verbose:
        print(format_metrics(metrics))

    # Return the raw data and metrics for further processing if needed
    return {
        'raw_data': data,
        'metrics': metrics,
        'channel_links': channel_links
    }


def analyze_from_json_data(json_data):
    """
    Analyze YouTube metrics from a provided JSON data string

    Args:
        json_data (str or dict): The JSON data string or dictionary

    Returns:
        dict: The raw data and metrics
    """
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError:
            print("Error: Invalid JSON data provided")
            return None
    else:
        data = json_data

    metrics = extract_account_metrics(data)

    # Calculate detailed video averages
    if 'video_stats' in data and 'items' in data['video_stats']:
        videos = data['video_stats']['items']
        video_averages = calculate_video_averages(videos)
        metrics['video_averages'] = video_averages

    print(format_metrics(metrics))

    return {
        'raw_data': data,
        'metrics': metrics
    }


def analyze_videos_by_time_period(channel_id=None, username=None, handle=None, days_ago=None, start_date=None, end_date=None):
    """
    Analyze videos from a specific time period

    Args:
        channel_id (str, optional): The YouTube channel ID
        username (str, optional): The YouTube username
        handle (str, optional): The YouTube handle
        days_ago (int, optional): Only include videos from the last X days
        start_date (str, optional): Only include videos published after this date (format: YYYY-MM-DD)
        end_date (str, optional): Only include videos published before this date (format: YYYY-MM-DD)

    Returns:
        dict: Analysis results for the specified time period
    """
    # Prepare header message based on date filters
    if days_ago:
        header = f"\n=== ANALYZING VIDEOS FROM THE LAST {days_ago} DAYS ==="
        time_period_msg = f"the last {days_ago} days"
    elif start_date and end_date:
        header = f"\n=== ANALYZING VIDEOS FROM {start_date} TO {end_date} ==="
        time_period_msg = f"the period {start_date} to {end_date}"
    elif start_date:
        header = f"\n=== ANALYZING VIDEOS FROM {start_date} ONWARDS ==="
        time_period_msg = f"the period from {start_date} onwards"
    elif end_date:
        header = f"\n=== ANALYZING VIDEOS UNTIL {end_date} ==="
        time_period_msg = f"the period until {end_date}"
    else:
        header = "\n=== ANALYZING ALL VIDEOS ==="
        time_period_msg = "all time"

    print(header)
    result = analyze_youtube_channel(
        channel_id=channel_id,
        username=username,
        handle=handle,
        days_ago=days_ago,
        start_date=start_date,
        end_date=end_date
    )

    if result:
        print(f"\nChecking video count for {time_period_msg}:")
        check_analyzed_videos_count(result['raw_data'])

    return result


def check_analyzed_videos_count(data):
    """
    Check how many videos are being analyzed from the YouTube data

    Args:
        data (dict): The YouTube API response data

    Returns:
        int: The number of videos being analyzed
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except json.JSONDecodeError:
            print("Error: Invalid JSON data provided")
            return 0

    # Get total video count from channel statistics
    total_videos = 0
    if 'items' in data and data['items']:
        channel = data['items'][0]
        statistics = channel.get('statistics', {})
        total_videos = int(statistics.get('videoCount', 0))

    # Get count of videos being analyzed
    analyzed_count = 0
    if 'video_stats' in data and 'items' in data['video_stats']:
        analyzed_count = len(data['video_stats']['items'])

    print(f"Total videos on channel: {total_videos}")
    print(f"Videos being analyzed: {analyzed_count}")

    if analyzed_count < total_videos:
        print(f"Note: Only analyzing {analyzed_count} out of {total_videos} videos")
        print("This is due to YouTube API limitations (max 50 videos per request)")

    return analyzed_count


def search_youtube_channels(query, max_results=5):
    """
    Search for YouTube channels based on a query string

    Args:
        query (str): The search query (e.g., "ai news")
        max_results (int, optional): Maximum number of results to return. Defaults to 5.

    Returns:
        list: List of channel information dictionaries
    """


    try:
        # Initialize the YouTube API client
        youtube = build('youtube', 'v3', developerKey=API_KEY)

        # Search for channels
        print(f"Searching for YouTube channels with query: '{query}'")
        search_request = youtube.search().list(
            part="snippet",
            q=query,
            type="channel",
            maxResults=max_results
        )
        search_response = search_request.execute()

        # Process search results
        channels = []
        for item in search_response.get('items', []):
            channel_id = item['snippet']['channelId']

            # Get more details about the channel
            channel_request = youtube.channels().list(
                part="snippet,statistics,contentDetails",
                id=channel_id
            )
            channel_response = channel_request.execute()

            if channel_response.get('items'):
                channel_details = channel_response['items'][0]
                snippet = channel_details['snippet']
                statistics = channel_details.get('statistics', {})

                # Get thumbnail URLs (different sizes available)
                thumbnails = snippet.get('thumbnails', {})
                profile_picture_url = thumbnails.get('high', {}).get('url',
                                     thumbnails.get('medium', {}).get('url',
                                     thumbnails.get('default', {}).get('url', 'N/A')))

                channels.append({
                    'channel_id': channel_id,
                    'title': snippet.get('title', 'Unknown'),
                    'description': snippet.get('description', ''),
                    'published_at': snippet.get('publishedAt', 'Unknown'),
                    'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', 'N/A'),
                    'profile_picture_url': profile_picture_url,
                    'subscriber_count': statistics.get('subscriberCount', 'N/A'),
                    'video_count': statistics.get('videoCount', 'N/A'),
                    'view_count': statistics.get('viewCount', 'N/A')
                })

        return channels

    except HttpError as e:
        print(f"YouTube API Error: {e}")
        return []
    except Exception as e:
        print(f"Error searching for channels: {e}")
        return []


def analyze_search_results(channels, days_ago=None, start_date=None, end_date=None, extract_links=True, headless=True, verbose=True):
    """
    Analyze multiple channels from search results

    Args:
        channels (list): List of channel information dictionaries
        days_ago (int, optional): Only include videos from the last X days
        start_date (str, optional): Only include videos published after this date (format: YYYY-MM-DD)
        end_date (str, optional): Only include videos published before this date (format: YYYY-MM-DD)
        extract_links (bool): Whether to extract external links using Playwright
        headless (bool): Whether to run browser in headless mode when extracting links
        verbose (bool, optional): Whether to print status messages. Defaults to True.

    Returns:
        dict: Dictionary mapping channel IDs to analysis results
    """
    results = {}

    if verbose:
        print(f"\n=== ANALYZING {len(channels)} CHANNELS FROM SEARCH RESULTS ===")

    for i, channel in enumerate(channels, 1):
        channel_id = channel.get('channel_id')
        title = channel.get('title', 'Unknown')

        if verbose:
            print(f"\n[{i}/{len(channels)}] Analyzing channel: {title} (ID: {channel_id})")

        # Analyze the channel
        result = analyze_youtube_channel(
            channel_id=channel_id,
            days_ago=days_ago,
            start_date=start_date,
            end_date=end_date,
            extract_links=extract_links,
            headless=headless,
            verbose=verbose
        )

        if result:
            results[channel_id] = result

    return results


def export_to_json(results, query=None, filename=None):
    """
    Export YouTube analysis results to a JSON file

    Args:
        results (dict): Dictionary mapping channel IDs to analysis results
        query (str, optional): The search query used to find the channels
        filename (str, optional): Custom filename for the JSON export

    Returns:
        str: Path to the exported JSON file
    """
    if not results:
        print("No results to export")
        return None

    # Create a clean data structure for JSON export
    export_data = {
        "query": query if query else "direct_export",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "channels": {}
    }

    # Process each channel's data
    for channel_id, result in results.items():
        metrics = result.get('metrics', {})

        # Add channel data to export
        export_data["channels"][metrics.get('channel_info', {}).get('title', channel_id)] = {
            "channel_info": metrics.get('channel_info', {}),
            "video_metrics": metrics.get('video_metrics', {}),
            "video_averages": metrics.get('video_averages', {}),
            "external_links": metrics.get('external_links', []),
            "recent_videos": metrics.get('recent_videos', [])
        }

    # Generate filename with timestamp if not provided
    if not filename:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"youtube_analysis_{timestamp}.json"
    elif not filename.endswith('.json'):
        filename = f"{filename}.json"

    # Write to file
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        print(f"\nData exported to {filename}")
        return filename
    except Exception as e:
        print(f"Error exporting data to JSON: {e}")
        return None


def calculate_video_averages(videos):
    """
    Calculate detailed average statistics for a list of YouTube videos.

    Args:
        videos (list): List of video data from YouTube API

    Returns:
        dict: Dictionary containing average statistics and metrics
    """
    if not videos:
        return {
            "count": 0,
            "avg_views": 0,
            "avg_likes": 0,
            "avg_comments": 0,
            "engagement_rate": 0,
            "max_views": 0,
            "min_views": 0,
            "avg_duration_seconds": 0,
            "like_to_view_ratio": 0,
            "comment_to_view_ratio": 0
        }

    # Initialize counters
    total_views = 0
    total_likes = 0
    total_comments = 0
    total_duration_seconds = 0
    view_counts = []

    # Process each video
    for video in videos:
        statistics = video.get('statistics', {})
        content_details = video.get('contentDetails', {})

        # Extract view count
        view_count = int(statistics.get('viewCount', 0))
        view_counts.append(view_count)
        total_views += view_count

        # Extract like count
        total_likes += int(statistics.get('likeCount', 0))

        # Extract comment count
        total_comments += int(statistics.get('commentCount', 0))

        # Extract duration if available
        duration = content_details.get('duration', '')
        if duration:
            try:
                # Convert ISO 8601 duration to seconds
                # Example: PT5M13S (5 minutes, 13 seconds)
                duration_seconds = 0

                # Extract hours
                if 'H' in duration:
                    hours_part = duration.split('H')[0].split('T')[1]
                    duration_seconds += int(hours_part) * 3600
                    duration = duration.split('H')[1]
                else:
                    duration = duration.split('T')[1]

                # Extract minutes
                if 'M' in duration:
                    minutes_part = duration.split('M')[0]
                    duration_seconds += int(minutes_part) * 60
                    duration = duration.split('M')[1]

                # Extract seconds
                if 'S' in duration:
                    seconds_part = duration.split('S')[0]
                    duration_seconds += int(seconds_part)

                total_duration_seconds += duration_seconds
            except Exception:
                # Skip if duration parsing fails
                pass

    # Calculate averages
    count = len(videos)
    avg_views = total_views / count if count > 0 else 0
    avg_likes = total_likes / count if count > 0 else 0
    avg_comments = total_comments / count if count > 0 else 0
    avg_duration_seconds = total_duration_seconds / count if count > 0 else 0

    # Calculate engagement metrics
    engagement_rate = (total_likes + total_comments) / total_views if total_views > 0 else 0
    like_to_view_ratio = total_likes / total_views if total_views > 0 else 0
    comment_to_view_ratio = total_comments / total_views if total_views > 0 else 0

    # Find max and min views
    max_views = max(view_counts) if view_counts else 0
    min_views = min(view_counts) if view_counts else 0

    return {
        "count": count,
        "avg_views": avg_views,
        "avg_likes": avg_likes,
        "avg_comments": avg_comments,
        "engagement_rate": engagement_rate,
        "max_views": max_views,
        "min_views": min_views,
        "avg_duration_seconds": avg_duration_seconds,
        "like_to_view_ratio": like_to_view_ratio,
        "comment_to_view_ratio": comment_to_view_ratio
    }

def run_youtube_analysis(query):
    """
    Run a complete YouTube analysis based on a search query.
    This will search for channels matching the query, then analyze the top 5 channels.

    Args:
        query (str): The search query for YouTube channels

    Returns:
        dict: Dictionary mapping channel IDs to analysis results
    """
    print("YouTube Metrics Collection Tool")
    print("=" * 50)

    # Set default parameters
    max_results = 5
    extract_links = True
    headless = True
    days_ago = None  # Get all videos

    # Check if Playwright is available
    if not PLAYWRIGHT_AVAILABLE:
        print("Playwright is not available. External links will not be extracted.")
        print("To enable this feature, install Playwright: pip install playwright")
        print("Then run: playwright install")
        extract_links = False

    # Search for channels
    print(f"\nSearching for YouTube channels with query: '{query}'")
    channels = search_youtube_channels(query, max_results=max_results)

    if not channels:
        print("No channels found matching your search query.")
        return {}

    # Print search results
    print(format_search_results(channels))

    # Analyze all channels from search results
    results = analyze_search_results(
        channels,
        days_ago=days_ago,
        extract_links=extract_links,
        headless=headless
    )

    # Calculate and add video averages for each channel
    for channel_id, result in results.items():
        if result and 'raw_data' in result and 'video_stats' in result['raw_data']:
            videos = result['raw_data']['video_stats'].get('items', [])
            video_averages = calculate_video_averages(videos)

            # Add the video averages to the result
            if 'metrics' not in result:
                result['metrics'] = {}
            result['metrics']['video_averages'] = video_averages

    if results:
        print("\n=== ANALYSIS COMPLETE ===")
        print(f"Analyzed {len(results)} channels matching '{query}'")
        print("Channel metrics and social media handles have been extracted")
        print("Video average statistics have been calculated")

        if extract_links:
            print("External links have been extracted from the channel pages using Playwright")

        # Export results to JSON
        json_file = export_to_json(results, query)
        if json_file:
            print(f"Results exported to JSON file: {json_file}")
    else:
        print("\n=== ANALYSIS FAILED ===")
        print("Could not retrieve data for any channels")

    return results


def main():
    """
    Main function to handle command-line arguments and run the appropriate analysis
    """
    parser = argparse.ArgumentParser(description='YouTube Channel Analyzer')

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search for and analyze YouTube channels')
    search_parser.add_argument('query', help='Search query for YouTube channels')
    search_parser.add_argument('--max-results', type=int, default=5, help='Maximum number of search results to analyze')

    # Date filtering options
    date_group = search_parser.add_argument_group('date filtering options (use only one)')
    date_group.add_argument('--days', type=int, help='Only include videos from the last X days')
    date_group.add_argument('--start-date', help='Only include videos published after this date (format: YYYY-MM-DD)')
    date_group.add_argument('--end-date', help='Only include videos published before this date (format: YYYY-MM-DD)')
    date_group.add_argument('--date-range', nargs=2, metavar=('START_DATE', 'END_DATE'),
                           help='Only include videos published between these dates (format: YYYY-MM-DD)')

    search_parser.add_argument('--no-links', action='store_true', help='Disable extraction of external links')
    search_parser.add_argument('--visible', action='store_true', help='Run browser in visible mode (not headless)')
    search_parser.add_argument('--output', help='Custom filename for JSON export')

    # Channel command
    channel_parser = subparsers.add_parser('channel', help='Analyze a specific YouTube channel')
    channel_group = channel_parser.add_mutually_exclusive_group(required=True)
    channel_group.add_argument('--id', help='YouTube channel ID')
    channel_group.add_argument('--username', help='YouTube username')
    channel_group.add_argument('--handle', help='YouTube handle (with or without @)')

    # Date filtering options
    date_group = channel_parser.add_argument_group('date filtering options (use only one)')
    date_group.add_argument('--days', type=int, help='Only include videos from the last X days')
    date_group.add_argument('--start-date', help='Only include videos published after this date (format: YYYY-MM-DD)')
    date_group.add_argument('--end-date', help='Only include videos published before this date (format: YYYY-MM-DD)')
    date_group.add_argument('--date-range', nargs=2, metavar=('START_DATE', 'END_DATE'),
                           help='Only include videos published between these dates (format: YYYY-MM-DD)')

    channel_parser.add_argument('--no-links', action='store_true', help='Disable extraction of external links')
    channel_parser.add_argument('--visible', action='store_true', help='Run browser in visible mode (not headless)')
    channel_parser.add_argument('--output', help='Custom filename for JSON export')

    # Links command
    links_parser = subparsers.add_parser('links', help='Extract links from a YouTube channel')
    links_parser.add_argument('url', help='YouTube channel URL')
    links_parser.add_argument('--visible', action='store_true', help='Run browser in visible mode (not headless)')
    links_parser.add_argument('--output', help='Output file path (JSON)')

    # Parse arguments
    args = parser.parse_args()

    # If no command is provided, show help
    if not args.command:
        parser.print_help()
        return

    # Handle search command
    if args.command == 'search':
        # Set parameters
        max_results = args.max_results
        extract_links = not args.no_links
        headless = not args.visible

        # Handle date filtering options
        days_ago = args.days
        start_date = args.start_date
        end_date = args.end_date

        # Handle date range if provided
        if args.date_range:
            start_date, end_date = args.date_range

        # Search for channels
        print(f"Searching for YouTube channels with query: '{args.query}'")
        channels = search_youtube_channels(args.query, max_results=max_results)

        if not channels:
            print("No channels found matching your search query.")
            return

        # Print search results
        print(format_search_results(channels))

        # Analyze all channels from search results
        results = analyze_search_results(
            channels,
            days_ago=days_ago,
            start_date=start_date,
            end_date=end_date,
            extract_links=extract_links,
            headless=headless
        )

        # Export results to JSON
        if results:
            json_file = export_to_json(results, args.query, args.output)
            if json_file:
                print(f"Results exported to JSON file: {json_file}")

    # Handle channel command
    elif args.command == 'channel':
        # Set parameters
        channel_id = args.id
        username = args.username
        handle = args.handle
        extract_links = not args.no_links
        headless = not args.visible

        # Handle date filtering options
        days_ago = args.days
        start_date = args.start_date
        end_date = args.end_date

        # Handle date range if provided
        if args.date_range:
            start_date, end_date = args.date_range

        # Analyze the channel
        result = analyze_youtube_channel(
            channel_id=channel_id,
            username=username,
            handle=handle,
            days_ago=days_ago,
            start_date=start_date,
            end_date=end_date,
            extract_links=extract_links,
            headless=headless
        )

        # Export results to JSON if requested
        if result and args.output:
            results = {result['raw_data']['items'][0]['id']: result}
            json_file = export_to_json(results, filename=args.output)
            if json_file:
                print(f"Results exported to JSON file: {json_file}")

    # Handle links command
    elif args.command == 'links':
        try:
            result = get_channel_links(args.url, headless=not args.visible)

            # Process links to extract direct URLs
            if result['links']:
                for link in result['links']:
                    # Extract the direct URL from YouTube redirect URLs
                    direct_url = extract_direct_url(link['url'])
                    link['direct_url'] = direct_url

            # Print results
            print(f"\nChannel: {result['channel_name']}")
            print(f"Channel ID: {result['channel_id']}")
            print(f"Subscribers: {result['subscriber_count']}")

            if result['links']:
                print("\nLinks:")
                for link in result['links']:
                    if 'direct_url' in link and link['direct_url'] != link['url']:
                        print(f"- {link['text']}: {link['direct_url']} (YouTube redirect)")
                    else:
                        print(f"- {link['text']}: {link['url']}")
            else:
                print("\nNo links found on this channel's about page.")

            # Save to file if specified
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"\nResults saved to {args.output}")

        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    main()