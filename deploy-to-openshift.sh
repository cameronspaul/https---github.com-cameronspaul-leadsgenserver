#!/bin/bash

# Exit on error
set -e

# Variables - replace these with your actual values
PROJECT_NAME="youtube-analyzer"
GIT_REPO="YOUR_GIT_REPOSITORY_URL"
YOUTUBE_API_KEY="YOUR_YOUTUBE_API_KEY"

# Check if logged in to OpenShift
echo "Checking OpenShift login status..."
oc whoami > /dev/null || { echo "Not logged in to OpenShift. Please run 'oc login' first."; exit 1; }

# Create a new project if it doesn't exist
echo "Creating project $PROJECT_NAME if it doesn't exist..."
oc new-project $PROJECT_NAME || oc project $PROJECT_NAME

# Update the secret with the actual API key
echo "Creating/updating YouTube API secret..."
sed -i "s|YOUR_YOUTUBE_API_KEY|$YOUTUBE_API_KEY|g" openshift/secret.yaml
oc apply -f openshift/secret.yaml

# Update the BuildConfig with the actual Git repository URL
echo "Creating/updating BuildConfig..."
sed -i "s|YOUR_GIT_REPOSITORY_URL|$GIT_REPO|g" openshift/buildconfig.yaml
oc apply -f openshift/imagestream.yaml
oc apply -f openshift/buildconfig.yaml

# Start the build
echo "Starting build..."
oc start-build youtube-analyzer-api --follow

# Apply the deployment, service, and route
echo "Deploying application..."
oc apply -f openshift/deployment.yaml
oc apply -f openshift/service.yaml
oc apply -f openshift/route.yaml

# Get the route URL
echo "Deployment completed. The application will be available at:"
oc get route youtube-analyzer-api -o jsonpath='{.spec.host}'
echo ""

# Restore the template files
echo "Restoring template files..."
sed -i "s|$YOUTUBE_API_KEY|YOUR_YOUTUBE_API_KEY|g" openshift/secret.yaml
sed -i "s|$GIT_REPO|YOUR_GIT_REPOSITORY_URL|g" openshift/buildconfig.yaml

echo "Deployment process completed!"
