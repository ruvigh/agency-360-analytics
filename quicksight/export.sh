#!/bin/bash

# Variables - Replace these with your specific values
export AWS_ACCOUNT_ID="615299736125"  # Source account for export
export EXPORT_JOB_ID="$AWS_ACCOUNT_ID-qs-agency360-no-dep-export"
export REGION="ap-southeast-1"  # E.g., us-east-1
export S3_BUCKET_NAME="observability360-apac-sg-moe"
export S3_FOLDER_PATH="quicksight"
export DASHBOARD_ID="d8010740-c7a5-4cde-a0fc-19dcde7e2be0"
export ANALYSIS_ID="752a8cb3-d9b2-44e0-b0a2-113d582a4243"
export LOCAL_BUNDLE_PATH="$HOME/project/agency360/agency-360-analytics/quicksight/quicksight-export.qs"

# Step 0: Verify AWS credentials
echo "Verifying AWS credentials..."
aws sts get-caller-identity

if [ $? -ne 0 ]; then
  echo "Failed to verify AWS credentials. Please make sure you're logged in."
  exit 1
fi

# Construct the Dashboard and Analysis ARNs
dashboard_arn="arn:aws:quicksight:$REGION:$AWS_ACCOUNT_ID:dashboard/$DASHBOARD_ID"
analysis_arn="arn:aws:quicksight:$REGION:$AWS_ACCOUNT_ID:analysis/$ANALYSIS_ID"

# Start the export job
echo "Starting QuickSight asset bundle export job..."
aws quicksight start-asset-bundle-export-job \
    --aws-account-id $AWS_ACCOUNT_ID \
    --asset-bundle-export-job-id $EXPORT_JOB_ID \
    --resource-arns "[\"$analysis_arn\"]" \
    --include-permissions \
    --export-format QUICKSIGHT_JSON \
    --region $REGION

# Poll the export job status
job_status="IN_PROGRESS"
while [ "$job_status" != "SUCCESSFUL" ] && [ "$job_status" != "FAILED" ]
do
  sleep 7
  result=$(aws quicksight describe-asset-bundle-export-job \
              --aws-account-id $AWS_ACCOUNT_ID \
              --asset-bundle-export-job-id $EXPORT_JOB_ID \
              --region $REGION)
  job_status=$(echo $result | jq -r '.JobStatus')
  echo "Current Export Job Status: $job_status"
done

# Check if export was successful
if [ "$job_status" = "SUCCESSFUL" ]; then
  echo "Export completed successfully!"
  
  # Get the download URL
  download_url=$(echo $result | jq -r '.DownloadUrl')

  # Download the export bundle
  echo "Downloading the export bundle..."
  wget -O $LOCAL_BUNDLE_PATH "$download_url"

  if [ $? -ne 0 ]; then
    echo "Failed to download the export bundle."
    exit 1
  fi

  # Upload the bundle to S3
  echo "Uploading the export bundle to S3..."
  aws s3 cp $LOCAL_BUNDLE_PATH s3://$S3_BUCKET_NAME/$S3_FOLDER_PATH/quicksight-export.qs

  if [ $? -ne 0 ]; then
    echo "Failed to upload the export bundle to S3."
    exit 1
  fi

  echo "Export bundle uploaded to S3: s3://$S3_BUCKET_NAME/$S3_FOLDER_PATH/quicksight-export.qs"
else
  echo "Export failed. Getting detailed error information..."
  
  # Get detailed error information
  aws quicksight describe-asset-bundle-export-job \
    --aws-account-id $AWS_ACCOUNT_ID \
    --asset-bundle-export-job-id $EXPORT_JOB_ID \
    --region $REGION

  exit 1
fi