#!/bin/bash

# AWS Elastic Beanstalk Deployment Script
# This script automates the deployment process for beginners

set -e  # Exit on any error

echo "🚀 Starting AWS Deployment for Amazon Recommender System"
echo "=================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    print_error "AWS CLI is not installed. Please install it first."
    echo "Run: curl \"https://awscli.amazonaws.com/AWSCLIV2.pkg\" -o \"AWSCLIV2.pkg\" && sudo installer -pkg AWSCLIV2.pkg -target /"
    exit 1
fi

# Check if EB CLI is installed
if ! command -v eb &> /dev/null; then
    print_warning "EB CLI is not installed. Installing it now..."
    pip install awsebcli
    print_status "EB CLI installed successfully"
fi

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker Desktop first."
    exit 1
fi

# Check if AWS credentials are configured
if ! aws sts get-caller-identity &> /dev/null; then
    print_error "AWS credentials are not configured."
    echo "Please run 'aws configure' and provide your AWS credentials."
    exit 1
fi

print_status "All prerequisites are met!"

# Get AWS account ID and region
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
if [ -z "$AWS_REGION" ]; then
    AWS_REGION="us-east-1"
    print_warning "No region configured, using us-east-1"
fi

echo "AWS Account ID: $AWS_ACCOUNT_ID"
echo "AWS Region: $AWS_REGION"

# Test Docker build locally first
print_status "Testing Docker build locally (this may take 5-10 minutes for first build)..."
print_warning "Building Docker image, please wait..."

# Build with timeout and proper error handling
if timeout 600 docker build -t amazon-recommender-test . ; then
    print_status "Docker build successful"
    docker rmi amazon-recommender-test > /dev/null 2>&1 || true
else
    build_exit_code=$?
    if [ $build_exit_code -eq 124 ]; then
        print_error "Docker build timed out (10 minutes). This might be due to slow internet connection."
        print_warning "Try running 'docker build -t test .' manually to see detailed output."
    else
        print_error "Docker build failed with exit code: $build_exit_code"
        print_warning "Try running 'docker build -t test .' manually to see detailed output."
    fi
    exit 1
fi

# Check if EB is already initialized
if [ ! -f ".elasticbeanstalk/config.yml" ]; then
    print_status "Initializing Elastic Beanstalk application..."
    eb init -p docker amazon-recommender-system --region $AWS_REGION
else
    print_status "Elastic Beanstalk already initialized"
fi

# Ask user for environment name
read -p "Enter environment name (default: production-env): " ENV_NAME
ENV_NAME=${ENV_NAME:-production-env}

# Check if environment exists
if eb list | grep -q "$ENV_NAME"; then
    print_status "Environment '$ENV_NAME' exists. Deploying update..."
    eb deploy $ENV_NAME
else
    print_status "Creating new environment '$ENV_NAME'..."
    eb create $ENV_NAME --timeout 20
fi

print_status "Deployment completed successfully!"
print_status "Your application is now live on AWS!"

# Get the application URL
APP_URL=$(eb status $ENV_NAME | grep "CNAME" | awk '{print $2}')
if [ ! -z "$APP_URL" ]; then
    echo ""
    echo "🌐 Your application is available at: http://$APP_URL"
    echo "🌐 You can also open it with: eb open $ENV_NAME"
else
    print_warning "Could not retrieve application URL. Use 'eb open $ENV_NAME' to access your app."
fi

echo ""
echo "📊 Useful commands:"
echo "  eb logs $ENV_NAME          - View application logs"
echo "  eb health $ENV_NAME        - Check application health"
echo "  eb open $ENV_NAME          - Open application in browser"
echo "  eb terminate $ENV_NAME     - Terminate environment (to save costs)"
echo ""
print_status "Deployment script completed!"