# Deploy CSS Changes

The CSS has been updated to match PostHog's style. To deploy these changes:

## Quick Deploy

Run this command from the `frontend` directory:

```bash
cd /Users/navyasharma/Documents/dev/PeterHolmes/frontend
export AWS_PROFILE=voobie  # or your AWS profile name
./deploy-to-s3.sh
```

## If the script can't find the bucket

If the script fails to find the S3 bucket automatically, you can deploy manually:

### Step 1: Find the S3 bucket name

```bash
aws cloudformation describe-stacks \
  --stack-name peterholmes-stack \
  --region eu-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucket`].OutputValue' \
  --output text \
  --profile voobie
```

### Step 2: Upload files to S3

Replace `YOUR_BUCKET_NAME` with the bucket name from Step 1:

```bash
cd /Users/navyasharma/Documents/dev/PeterHolmes/frontend
aws s3 sync . s3://YOUR_BUCKET_NAME/ \
  --exclude "*.sh" \
  --exclude "*.md" \
  --exclude ".git/*" \
  --exclude ".DS_Store" \
  --delete \
  --region eu-west-2 \
  --profile voobie
```

### Step 3: Invalidate CloudFront cache

Get the distribution ID:

```bash
aws cloudformation describe-stacks \
  --stack-name peterholmes-stack \
  --region eu-west-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' \
  --output text \
  --profile voobie
```

Then invalidate the cache (replace `DISTRIBUTION_ID`):

```bash
aws cloudfront create-invalidation \
  --distribution-id DISTRIBUTION_ID \
  --paths "/*" \
  --profile voobie
```

## Test the changes

After deployment, visit: **https://dzpnzmm4q40pg.cloudfront.net**

The new PostHog-style UI should be live! You may need to do a hard refresh (Cmd+Shift+R on Mac, Ctrl+Shift+R on Windows) to see the changes if CloudFront cache hasn't cleared yet.


