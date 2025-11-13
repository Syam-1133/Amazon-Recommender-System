# 🔐 GitHub Secrets Setup Guide

## Required GitHub Secrets

To enable automated deployment, you need to add these secrets to your GitHub repository:

### 1. Go to Your GitHub Repository
- Navigate to: `https://github.com/Syam-1133/Amazon-Recommender-System`
- Click on **Settings** tab
- Click on **Secrets and variables** → **Actions**

### 2. Add the following secrets:

#### `AWS_ACCESS_KEY_ID`
```
Your AWS Access Key ID
Example: AKIAIOSFODNN7EXAMPLE
```

#### `AWS_SECRET_ACCESS_KEY`
```
Your AWS Secret Access Key
Example: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

#### `AWS_REGION` (Optional)
```
us-east-1
```

### 3. How to Get AWS Credentials:

1. **Login to AWS Console**
2. **Go to IAM (Identity and Access Management)**
3. **Create a new user or use existing**
4. **Attach policies:**
   - `AWSElasticBeanstalkFullAccess`
   - `AWSElasticBeanstalkService`
   - `IAMReadOnlyAccess`

5. **Create Access Key:**
   - Go to user → Security credentials
   - Create access key → CLI
   - Save the Access Key ID and Secret Access Key

### 4. Test Credentials:
```bash
aws configure
aws sts get-caller-identity
```

## 🚀 Deployment Methods Available:

1. **GitHub Actions** (Automated)
2. **Manual EB CLI** 
3. **AWS Console**
4. **deploy_to_aws.sh script**