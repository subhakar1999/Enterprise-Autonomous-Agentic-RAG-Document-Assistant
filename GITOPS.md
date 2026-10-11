# GitOps for Vercel

The repository includes `.github/workflows/vercel-gitops.yml`.

## Delivery flow

```text
Feature branch → Pull request → tests → Vercel preview deployment
                                     ↓
                           review and approval
                                     ↓
                     merge to main → tests → production deployment
```

The preview job runs only for pull requests created inside this repository. This prevents secrets from being exposed to untrusted fork pull requests.

## One-time setup

1. Create a GitHub repository and push this project to it.
2. In Vercel, create/link a project for the repository. From a trusted local terminal, run:

   ```powershell
   npm install --global vercel
   vercel link
   ```

3. Open `.vercel/project.json` locally and copy its `orgId` and `projectId` values. Do not commit `.vercel`.
4. In GitHub, open **Repository → Settings → Secrets and variables → Actions** and add these repository secrets:

   | Secret | Value |
   | --- | --- |
   | `VERCEL_TOKEN` | A Vercel access token with access to the target project |
   | `VERCEL_ORG_ID` | The `orgId` from `.vercel/project.json` |
   | `VERCEL_PROJECT_ID` | The `projectId` from `.vercel/project.json` |

5. No model or database secrets are required for the extractive Vercel demo.
6. In GitHub, protect the `main` branch and require the **Test** status check and pull-request review before merging.

## Important

Use either this GitHub Actions workflow or Vercel’s built-in Git integration as the system that deploys the application. If both are enabled, each push can create duplicate deployments. This workflow is the appropriate choice when you want the repository workflow to be the audited deployment authority.

## Rollback

Revert the production commit through a pull request and merge it into `main`. The workflow tests and redeploys the previously working version. This makes the Git history the source of truth for production state.
