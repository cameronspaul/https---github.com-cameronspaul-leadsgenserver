# Deploying YouTube Analyzer API on Red Hat OpenShift

This guide provides instructions for deploying the YouTube Analyzer API on Red Hat OpenShift.

## Prerequisites

1. OpenShift CLI (`oc`) installed and configured
2. Access to an OpenShift cluster
3. A YouTube API key
4. Git repository with your code

## Deployment Options

There are two ways to deploy this application:

1. **Automated deployment** using the provided script
2. **Manual deployment** by applying each configuration file individually

## Option 1: Automated Deployment

1. Make the deployment script executable:
   ```bash
   chmod +x deploy-to-openshift.sh
   ```

2. Edit the script to set your variables:
   ```bash
   # Open the script
   nano deploy-to-openshift.sh
   
   # Update these variables
   PROJECT_NAME="youtube-analyzer"  # Your OpenShift project name
   GIT_REPO="https://github.com/yourusername/youtube-analyzer.git"  # Your Git repo URL
   YOUTUBE_API_KEY="your-youtube-api-key"  # Your YouTube API key
   ```

3. Log in to your OpenShift cluster:
   ```bash
   oc login --server=https://your-openshift-cluster:6443
   ```

4. Run the deployment script:
   ```bash
   ./deploy-to-openshift.sh
   ```

## Option 2: Manual Deployment

1. Log in to your OpenShift cluster:
   ```bash
   oc login --server=https://your-openshift-cluster:6443
   ```

2. Create a new project:
   ```bash
   oc new-project youtube-analyzer
   ```

3. Update the configuration files with your specific values:
   - In `openshift/secret.yaml`: Replace `YOUR_YOUTUBE_API_KEY` with your actual YouTube API key
   - In `openshift/buildconfig.yaml`: Replace `YOUR_GIT_REPOSITORY_URL` with your Git repository URL

4. Create the ImageStream:
   ```bash
   oc apply -f openshift/imagestream.yaml
   ```

5. Create the BuildConfig and start the build:
   ```bash
   oc apply -f openshift/buildconfig.yaml
   oc start-build youtube-analyzer-api --follow
   ```

6. Create the Secret, Deployment, Service, and Route:
   ```bash
   oc apply -f openshift/secret.yaml
   oc apply -f openshift/deployment.yaml
   oc apply -f openshift/service.yaml
   oc apply -f openshift/route.yaml
   ```

7. Get the route URL to access your application:
   ```bash
   oc get route youtube-analyzer-api
   ```

## Handling Playwright in OpenShift

The Dockerfile is configured to install Playwright and its dependencies in a way that works with OpenShift's security constraints. The key points are:

1. Installing system dependencies required by Playwright browsers
2. Setting the `PLAYWRIGHT_BROWSERS_PATH` environment variable to a system-wide location
3. Installing Playwright browsers with the `--with-deps` flag

## Troubleshooting

### Insufficient Memory

If you encounter memory issues (the application crashes due to memory limits), you can adjust the resource limits in `openshift/deployment.yaml`:

```yaml
resources:
  requests:
    memory: "512Mi"  # Increase this value
    cpu: "100m"
  limits:
    memory: "1Gi"    # Increase this value
    cpu: "500m"
```

### Playwright Installation Issues

If Playwright is not working correctly:

1. Check the pod logs:
   ```bash
   oc logs -f deployment/youtube-analyzer-api
   ```

2. You might need to disable the `extract_links` feature if Playwright cannot be installed properly:
   ```bash
   # Add this environment variable to the deployment.yaml
   - name: DISABLE_PLAYWRIGHT
     value: "true"
   ```

3. Then modify your code to check for this environment variable and disable Playwright functionality accordingly.

### Security Constraints

OpenShift has strict security constraints. If you encounter permission issues:

1. You might need to add a Security Context Constraint (SCC) to your service account:
   ```bash
   oc adm policy add-scc-to-user anyuid -z default
   ```

   Note: This is not recommended for production environments. It's better to adapt your application to run with restricted permissions.

## Scaling the Application

To scale the application to multiple replicas:

```bash
oc scale deployment youtube-analyzer-api --replicas=3
```

## Updating the Application

When you make changes to your code:

1. Push the changes to your Git repository
2. Start a new build:
   ```bash
   oc start-build youtube-analyzer-api
   ```

The deployment will automatically update with the new image once the build completes.
