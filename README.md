## GitHub User Contribution Activity Audit

This script analyzes user contribution activity across GitHub organizations by tracking commits, issues, and pull requests across all repositories and branches.  
Based on these contributions, it determines each user’s **last recorded activity** and classifies users as **Active** or **Inactive** using a configurable inactivity threshold.  
The script generates detailed, per-repository CSV reports for auditing and analysis.


This project is available both as:
- ✅ **A GitHub Action**
- 🐍 **A standalone Python script (optional local usage)**

---

## 🚀 GitHub Action (Marketplace)

This project is available as a **GitHub Action**, allowing you to generate detailed user activity reports automatically without local setup.

## How It Works

- Reads organization names, inactivity threshold, and authentication details from environment variables.
- Retrieves all members of each configured GitHub organization.
- Fetches all non-fork repositories within the organization.
- Enumerates all branches for each repository.
- Collects user activity across:
  - Commits (per branch)
  - Issues (created)
  - Pull requests (created)
- Aggregates activity per user to determine:
  - Total commits, issues, and PRs
  - Most recent activity timestamp
- Classifies users as:
  - **Active** – last activity within the configured inactivity threshold
  - **Inactive** – User has no recorded commits, issues, or pull requests,
or their most recent activity is older than the configured threshold.
- Generates a consolidated CSV report with per-repository user activity details.
- Implements retry logic, timeouts, and rate-limit delays to ensure reliable execution against the GitHub GraphQL API.

## Usage

```yml
- name: Run User Contribution Activity Report
      uses: CanarysAutomations/User-Contribution-Activity@v1
      with:
        github_token: ${{ secrets.ORG_AUDIT_TOKEN }}
        org_names: org-name
        days_inactive_threshold: 90

  # Uploads the CSV report of user contribution activity
  - name: Upload contribution activity report
        uses: actions/upload-artifact@v4
        with:
          name: users-contribution-activity-report
          path: "*.csv"

```


### Example workflow

```yaml
name: User Contribution Activity Audit

on:
  workflow_dispatch:
  schedule:
    - cron: "0 2 1 * *"

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - name: Run User Contribution Activity Report
        uses: CanarysAutomations/User-Contribution-Activity@v1
        with:
          github_token: ${{ secrets.ORG_AUDIT_TOKEN }}
          org_names: org-name
          days_inactive_threshold: 90

      - name: Upload contribution activity report
        uses: actions/upload-artifact@v4
        with:
          name: users-contribution-activity-report
          path: "*.csv"

```

## 🔐 Required Token Permissions

The token used with this action must have the following scopes:

- `read:org – to list organization members`

- `repo – to analyze repository activity`


## 🔧 GitHub Action Inputs

| Name | Required	| Default |	Description |
|---|---|---|---|
| `github_token` |	Yes |	–	 |GitHub token with `read:org` and repository read access |
| `org_names` |	Yes |	–	| Comma-separated GitHub organization names |
| `days_inactive_threshold` |	No |	60 |	Days to consider a user inactive |

**Note:**
`days_inactive_threshold` specifies the number of days without contribution activity (commits, issues, or pull requests) after which a user is marked as Inactive. If not provided, the default value of 60 days is used.


## Sample Output

### Repository: demo-repository
| Username           | Commits | Issues | PRs | Last Activity              | Status   |
|--------------------|---------|--------|-----|----------------------------|----------|
| Sandeep-U-D        | 4       | 1      | 0   | 2025-07-15T04:01:00Z       | Active   |
| nikhilgowda-135    | 1       | 2      | 0   | 2025-07-29T06:34:53Z       | Active   |
| niranjanakoni      | 0       | 0      | 0   | N/A                        | Inactive |
| praveensh-git      | 0       | 0      | 0   | N/A                        | Inactive |
| raghav-s23         | 0       | 0      | 0   | N/A                        | Inactive |


## 🐍 A standalone Python script (optional local usage)

## Description

The script uses the GitHub GraphQL API to:
- Retrieve all members from one or more GitHub organizations
- Fetch all repositories (excluding forks) from each organization
- Analyze all branches in each repository
- Track commits, issues, and pull requests for each user
- Determine user activity status based on a configurable inactivity threshold
- Generate separate timestamped CSV reports for each organization

## Prerequisites

- Python 3.x
- Required Python packages:
  - `requests`
  - `python-dotenv`

## Installation

1. Install the required packages:
```bash
pip install requests python-dotenv
```

2. Create a `.env` file in the same directory with the following variables:
```
GITHUB_TOKEN=your-github-personal-access-token
ORG_NAMES=org1,org2,org3
DAYS_INACTIVE_THRESHOLD=60
```

## Configuration

### Environment Variables

- **GITHUB_TOKEN**: Your GitHub Personal Access Token
  - Required scopes: `repo`, `read:org`, `read:user`
  - Note: This script uses GraphQL API, so ensure the token has appropriate permissions
- **ORG_NAMES**: Comma-separated list of GitHub organization names to analyze
  - Example: `myorg1,myorg2,myorg3`
- **DAYS_INACTIVE_THRESHOLD**: Number of days to consider a user inactive (default: 60)
  - Users with no activity in this period will be marked as "Inactive"

## Usage

Run the script:
```bash
python users_contribution_activity.py
```

## Output

The script generates a timestamped CSV file for each organization (e.g., `myorg_user_activity_20250124_143022.csv`).

### CSV Format

The output is organized by repository with the following structure:

```
Repository: repo-name
Username, Commits, Issues, PRs, Last Activity, Status
user1, 45, 12, 8, 2025-01-15T10:30:00Z, Active
user2, 0, 0, 0, N/A, Inactive
...

Repository: another-repo
Username, Commits, Issues, PRs, Last Activity, Status
...
```

### Columns

- **Username**: GitHub username of the organization member
- **Commits**: Total number of commits by the user in the repository (across all branches)
- **Issues**: Total number of issues created by the user
- **PRs**: Total number of pull requests created by the user
- **Last Activity**: Most recent activity timestamp (latest of commit/issue/PR)
- **Status**: "Active" or "Inactive" based on the configured threshold

## Features

- ✅ Supports multiple organizations in a single run
- ✅ Analyzes all branches in each repository
- ✅ Tracks three types of activity: commits, issues, and pull requests
- ✅ Automatic pagination handling for large datasets
- ✅ Uses efficient GraphQL API for faster data retrieval
- ✅ Configurable inactivity threshold
- ✅ Timestamped output files
- ✅ Shows all organization members, even those with no activity
- ✅ Real-time progress indicators
- ✅ UTF-8 encoding support
- ✅ Built-in rate limiting delays (2 seconds between requests)

## Activity Status Logic

- **Active**: User has activity within the configured threshold period
  - Example: If threshold is 60 days, any activity in the last 60 days marks the user as Active
- **Inactive**: User has no activity within the threshold period, or no activity at all

## Performance Notes

- This script can take significant time to complete for large organizations
- Time estimate: ~1-5 minutes per repository, depending on size
- The script processes all branches in each repository
- GraphQL API is used for efficiency, but rate limits still apply
- Built-in 2-second delay between requests to prevent rate limiting

## GraphQL API Rate Limits

- 5,000 points per hour for authenticated requests
- Different queries consume different point values
- The script includes delays to stay within limits
- Complex queries (commit history) consume more points

## Error Handling

The script handles:
- GraphQL query failures with detailed error messages
- Missing or null data gracefully
- Empty repositories or branches
- Users with no activity (shows as "N/A")
- Timezone conversions for accurate date comparisons

## Use Cases

This script is useful for:
- Identifying dormant or inactive organization members
- Auditing user contributions across repositories
- Planning user access reviews
- Understanding team activity patterns
- Compliance and security audits
- Identifying users who may no longer need access

## Output Analysis

To analyze the results:
1. Open the generated CSV file in Excel or a text editor
2. Filter by "Status" column to find inactive users
3. Sort by "Last Activity" to see most recent contributors
4. Review activity counts to understand contribution levels
5. Use data for access reviews or team planning

## Notes

- All organization members are included in the output, regardless of activity level
- Forks are excluded from repository analysis
- The script fetches complete activity history (not limited by time)
- Commit activity is aggregated across all branches
- Debug output shows issue processing in real-time
- Separate CSV files are generated for each organization

## Troubleshooting

**Script runs slowly:**
- This is normal for large organizations with many repositories
- Consider running during off-peak hours
- The script must process all branches and all history

**"GraphQL query failed" error:**
- Check that your token has the required scopes
- Verify the token hasn't expired
- Ensure organization names are spelled correctly

**Users missing from report:**
- Verify they are organization members (not outside collaborators)
- Check that they have a GitHub account (not deleted)

## Permissions Required

- Read access to organization membership
- Read access to all repositories
- Token with `repo` and `read:org` scopes
