#!/bin/bash

# Variables - Replace these with your specific values
export AWS_ACCOUNT_ID="615299736125"  # Target account for import
export IMPORT_JOB_ID="615299736125-agency-360-qs-no-dep-import"
#export IMPORT_JOB_ID="615299736125-agency-360-qs-all-dep-import"
export REGION="us-east-1"
export S3_BUCKET_NAME="agency360"
export S3_FILE_PATH="agency360-no-deps.qs"
#export S3_FILE_PATH="agency360-all-dep.qs"

# Step 0: Verify AWS credentials
echo "Verifying AWS credentials..."
aws sts get-caller-identity

if [ $? -ne 0 ]; then
  echo "Failed to verify AWS credentials. Please make sure you're logged in."
  exit 1
fi

# Start the import job
aws quicksight start-asset-bundle-import-job \
    --aws-account-id $AWS_ACCOUNT_ID \
    --asset-bundle-import-job-id $IMPORT_JOB_ID \
    --asset-bundle-import-source "{\"S3Uri\": \"s3://$S3_BUCKET_NAME/$S3_FILE_PATH\"}" \
    --failure-action DO_NOTHING \
    --region $REGION

if [ $? -ne 0 ]; then
  echo "Failed to start the asset bundle import job."
  exit 1
fi

# Poll the import job status
job_status="IN_PROGRESS"
while [ "$job_status" != "SUCCESSFUL" ] && [ "$job_status" != "FAILED" ]
do
  sleep 8
  result=$(aws quicksight describe-asset-bundle-import-job \
              --aws-account-id $AWS_ACCOUNT_ID \
              --asset-bundle-import-job-id $IMPORT_JOB_ID \
              --region $REGION)
  job_status=$(echo $result | jq -r '.JobStatus')
  echo "Current Import Job Status: $job_status"
done

# Check if import was successful
if [ "$job_status" = "SUCCESSFUL" ]; then
  echo "Import completed successfully!"
else
  echo "Import failed. Getting detailed error information..."
  aws quicksight describe-asset-bundle-import-job \
    --aws-account-id $AWS_ACCOUNT_ID \
    --asset-bundle-import-job-id $IMPORT_JOB_ID \
    --include-errors \
    --region $REGION
  
  # Check if the S3 file exists
  echo "Verifying S3 file exists..."
  aws s3 ls s3://$S3_BUCKET_NAME/$S3_FILE_PATH
  if [ $? -ne 0 ]; then
    echo "ERROR: The specified file does not exist in S3 bucket!"
  fi
fi