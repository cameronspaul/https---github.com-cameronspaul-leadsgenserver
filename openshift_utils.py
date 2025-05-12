"""
Utility functions for handling OpenShift-specific configurations and workarounds
"""
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger('openshift_utils')

def configure_playwright_for_openshift():
    """
    Configure Playwright to work in an OpenShift environment.
    
    This function sets the necessary environment variables and checks
    if Playwright is available and properly configured.
    
    Returns:
        bool: True if Playwright is available and configured, False otherwise
    """
    # Check if Playwright should be disabled
    if os.environ.get('DISABLE_PLAYWRIGHT', '').lower() == 'true':
        logger.info("Playwright is explicitly disabled via DISABLE_PLAYWRIGHT environment variable")
        return False
    
    try:
        from playwright.sync_api import sync_playwright
        
        # Set Playwright browser path to a location that works in OpenShift
        if not os.environ.get('PLAYWRIGHT_BROWSERS_PATH'):
            os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/ms-playwright'
            logger.info("Set PLAYWRIGHT_BROWSERS_PATH to /ms-playwright")
        
        # Test if Playwright can be initialized
        logger.info("Testing Playwright initialization...")
        with sync_playwright() as playwright:
            try:
                browser = playwright.chromium.launch(headless=True)
                browser.close()
                logger.info("Playwright is working correctly")
                return True
            except Exception as e:
                logger.error(f"Failed to launch Playwright browser: {str(e)}")
                return False
    
    except ImportError:
        logger.warning("Playwright is not installed")
        return False
    except Exception as e:
        logger.error(f"Error configuring Playwright: {str(e)}")
        return False

def check_memory_limits():
    """
    Check the available memory and log warnings if it's below recommended thresholds.
    
    Returns:
        bool: True if memory is sufficient, False otherwise
    """
    try:
        import psutil
        
        # Get available memory in MB
        available_memory_mb = psutil.virtual_memory().available / (1024 * 1024)
        
        if available_memory_mb < 200:  # Less than 200MB available
            logger.warning(f"Very low memory available: {available_memory_mb:.2f}MB. Application may crash.")
            return False
        elif available_memory_mb < 500:  # Less than 500MB available
            logger.warning(f"Low memory available: {available_memory_mb:.2f}MB. Performance may be affected.")
            return True
        else:
            logger.info(f"Sufficient memory available: {available_memory_mb:.2f}MB")
            return True
    
    except ImportError:
        logger.warning("psutil not installed, cannot check memory limits")
        return True
    except Exception as e:
        logger.error(f"Error checking memory limits: {str(e)}")
        return True

def initialize_openshift_environment():
    """
    Initialize the environment for running in OpenShift.
    
    This function performs all necessary checks and configurations
    to ensure the application runs properly in OpenShift.
    
    Returns:
        dict: A dictionary with configuration status
    """
    config = {
        'playwright_available': False,
        'memory_sufficient': True,
        'environment': 'openshift' if os.environ.get('OPENSHIFT_BUILD_NAME') else 'other'
    }
    
    # Check if running in OpenShift
    if config['environment'] == 'openshift':
        logger.info("Running in OpenShift environment")
        
        # Configure Playwright
        config['playwright_available'] = configure_playwright_for_openshift()
        
        # Check memory limits
        config['memory_sufficient'] = check_memory_limits()
    else:
        logger.info("Not running in OpenShift environment")
        
        # For non-OpenShift environments, check Playwright normally
        try:
            from playwright.sync_api import sync_playwright
            config['playwright_available'] = True
        except ImportError:
            config['playwright_available'] = False
    
    return config
